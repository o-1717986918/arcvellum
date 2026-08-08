"""Disk adapter for AO-5 chapter planning facts (W6-6D).

This adapter reads only formal project files (scene YAML, rhythm plan, word
budget, chapter obligations) and projects them into the machine-owned
``ChapterPlanningFacts`` contract.  It never creates tasks, never writes
project facts, and never activates a plan.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from .chapter_facts import ChapterPlanningFacts, ScenePlanningFact
from .project_fingerprint import planning_project_fingerprint

_YAML = YAML(typ="safe")
_EXPLICIT_RISK_FIELDS = (
    "canon_change",
    "character_state_change",
    "new_asset_risk",
    "branch_ambiguity",
    "continuity_debt",
    "style_novelty",
)


def load_chapter_planning_facts(
    root: Path,
    chapter_id: str,
) -> ChapterPlanningFacts:
    """Load deterministic chapter planning facts from a formal project."""
    root = root.resolve()
    scene_paths = _chapter_scene_paths(root, chapter_id)
    if not scene_paths:
        raise FileNotFoundError(f"no scenes found for chapter: {chapter_id}")
    rhythm_entries = _rhythm_entries(root)
    rhythm_by_scene = {entry["scene_id"]: entry for entry in rhythm_entries}
    budget_row = _chapter_budget_row(root, chapter_id)
    obligation_ids, obligation_contract_present = _obligation_contract(
        root,
        chapter_id,
    )
    scenes = tuple(
        _scene_fact(path, chapter_id, rhythm_by_scene, budget_row)
        for path in scene_paths
    )
    return ChapterPlanningFacts(
        chapter_id=chapter_id,
        scenes=scenes,
        chapter_word_target=_int_value(budget_row.get("target_words")),
        rhythm_contract_hash=_rhythm_digest(root),
        promise_obligation_ids=obligation_ids,
        obligation_contract_present=obligation_contract_present,
        base_project_revision=planning_project_fingerprint(root),
    )


def _chapter_scene_paths(root: Path, chapter_id: str) -> list[Path]:
    scene_dir = root / "scenes"
    if not scene_dir.is_dir():
        return []
    ordered: list[tuple[float, str, Path]] = []
    for path in sorted(scene_dir.glob("*.yaml")):
        payload = _scene_payload(path)
        if str(payload.get("chapter_id") or "") != chapter_id:
            continue
        timeline_order = _timeline_order(payload)
        ordered.append((timeline_order, path.stem, path))
    return [item[2] for item in sorted(ordered, key=lambda item: (item[0], item[1]))]


def _scene_fact(
    path: Path,
    chapter_id: str,
    rhythm_by_scene: dict[str, dict[str, Any]],
    budget_row: dict[str, Any],
) -> ScenePlanningFact:
    payload = _scene_payload(path)
    scene_id = str(payload.get("scene_id") or path.stem)
    rhythm = rhythm_by_scene.get(scene_id, {})
    risks = {name: _explicit_risk(payload, name) for name in _EXPLICIT_RISK_FIELDS}
    risks["climax_weight"] = _climax_weight(payload)
    return ScenePlanningFact(
        scene_ref=scene_id,
        word_target=_word_target(payload, rhythm, budget_row),
        function=_function(payload, rhythm),
        pace=_pace(rhythm),
        canon_change=risks["canon_change"],
        character_state_change=risks["character_state_change"],
        new_asset_risk=risks["new_asset_risk"],
        branch_ambiguity=risks["branch_ambiguity"],
        climax_weight=risks["climax_weight"],
        continuity_debt=risks["continuity_debt"],
        style_novelty=risks["style_novelty"],
        obligations=_scene_obligations(payload),
    )


def _scene_payload(path: Path) -> dict[str, Any]:
    try:
        payload = _YAML.load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid scene YAML: {path}") from exc
    return payload if isinstance(payload, dict) else {}


def _timeline_order(payload: dict[str, Any]) -> float:
    time_payload = payload.get("time")
    if isinstance(time_payload, dict):
        value = time_payload.get("timeline_order")
        try:
            return float(value)
        except (TypeError, ValueError):
            return float("inf")
    return float("inf")


def _word_target(
    payload: dict[str, Any],
    rhythm: dict[str, Any],
    budget_row: dict[str, Any],
) -> int:
    for source in (payload, rhythm, budget_row):
        value = _int_value(source.get("word_count_target"))
        if value:
            return value
    return _int_value(budget_row.get("avg_scene_words"))


def _explicit_risk(payload: dict[str, Any], name: str) -> int:
    value = _int_value(payload.get(name))
    return max(0, value)


def _climax_weight(payload: dict[str, Any]) -> int:
    explicit = _int_value(payload.get("climax_weight"))
    if explicit:
        return max(0, explicit)
    rhythm = payload.get("narrative_rhythm")
    if not isinstance(rhythm, dict):
        return 0
    curve = rhythm.get("tension_curve")
    if not isinstance(curve, dict):
        return 0
    peak = _int_value(curve.get("peak"))
    if peak >= 5:
        return 4
    if peak == 4:
        return 2
    return 0


def _function(payload: dict[str, Any], rhythm: dict[str, Any]) -> str:
    rhythm_block = payload.get("narrative_rhythm")
    values: list[str] = []
    if isinstance(rhythm_block, dict):
        values.extend(_string_list(rhythm_block.get("scene_function")))
    if not values:
        values.extend(_string_list(rhythm.get("scene_function")))
    return " / ".join(values)


def _pace(rhythm: dict[str, Any]) -> str:
    return str(rhythm.get("pace") or "")


def _scene_obligations(payload: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(item) for item in _string_list(payload.get("obligations")))


def _rhythm_entries(root: Path) -> list[dict[str, Any]]:
    payload = _read_json(root / "plot" / "rhythm_plan.json")
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return []
    return [item for item in entries if isinstance(item, dict)]


def _rhythm_digest(root: Path) -> str:
    payload = _read_json(root / "plot" / "rhythm_plan.json")
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("digest") or "")


def _chapter_budget_row(root: Path, chapter_id: str) -> dict[str, Any]:
    payload = _read_json(root / "plot" / "word_budget" / "word_budget.json")
    rows = payload.get("chapter_budgets") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, dict) and str(row.get("chapter_id") or "") == chapter_id:
            return row
    return {}


def _obligation_contract(
    root: Path,
    chapter_id: str,
) -> tuple[tuple[str, ...], bool]:
    path = root / "plot" / "chapter_obligations" / f"{chapter_id}.json"
    if not path.is_file():
        return (), False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (), False
    if not isinstance(payload, dict):
        return (), False
    for key in ("obligation_ids", "promise_ids"):
        ids = _string_list(payload.get(key))
        if ids:
            return tuple(ids), True
    contract = payload.get("contract")
    if isinstance(contract, dict):
        ids = _contract_obligation_ids(contract.get("obligations"))
        if ids:
            return tuple(ids), True
    return (), True


def _contract_obligation_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    for item in value:
        if isinstance(item, dict):
            item_id = item.get("id") or item.get("obligation_id")
            if item_id:
                ids.append(str(item_id))
        elif item is not None:
            ids.append(str(item))
    return ids


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]
