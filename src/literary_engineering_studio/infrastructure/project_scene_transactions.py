"""Real-project adapters for the lean scene-transaction kernel."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

from literary_engineering_studio_engine.public.projects import atomic_write_batch
from literary_engineering_studio_engine.public.literary import (
    RhythmDirective,
    SceneCommitPlan,
    SceneExecutionMode,
    SceneFacts,
    SceneRisk,
    SceneRiskLevel,
    StyleMountRef,
    active_style_evidence_paths,
    active_style_mount_snapshot_payload,
    build_scene_brief,
    character_field_value,
    character_slug,
    load_scene_facts,
    load_scene_mapping,
    read_character_text,
)

from ..application.scene_transaction import PreparedScene, SceneCommitReceipt
from ..orchestration.risk import SceneRiskFacts, build_scene_risk_profile


_SCENE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_CORE_CANON = (
    "canon/world_rules.yaml",
    "canon/forbidden_changes.yaml",
    "canon/timeline.yaml",
    "canon/facts.json",
)


class ProjectSceneBriefProvider:
    """Project formal facts -> bounded, immutable scene brief."""

    def prepare(
        self,
        project_root: Path,
        scene_id: str,
        mode: SceneExecutionMode,
    ) -> PreparedScene:
        del mode
        root = project_root.expanduser().resolve()
        scene_path = _scene_path(root, scene_id)
        if not scene_path.is_file():
            raise FileNotFoundError(f"formal scene not found: scenes/{scene_id}.yaml")
        if (root / "drafts" / "scenes" / f"{scene_id}.md").exists():
            raise FileExistsError(
                f"formal scene prose already exists: drafts/scenes/{scene_id}.md"
            )
        facts = load_scene_facts(scene_path)
        if facts.scene_id != scene_id:
            raise ValueError(
                f"scene identity mismatch: requested {scene_id}, file declares {facts.scene_id}"
            )
        mapping = load_scene_mapping(scene_path)
        rhythm_entry = _rhythm_entry(root, facts.scene_id)
        source_refs = _source_refs(root, facts)
        incoming = _incoming_handoff(root, facts, source_refs)
        obligations = _chapter_obligations(root, facts.chapter_id)
        style = active_style_mount_snapshot_payload(root)
        profile = build_scene_risk_profile(_risk_facts(facts.scene_id, mapping))
        brief = build_scene_brief(
            facts,
            risk=SceneRisk(
                SceneRiskLevel.from_compatible_value(profile.level),
                profile.reasons,
            ),
            scene_function=_scene_function(mapping, rhythm_entry),
            canon_constraints=facts.canon_refs,
            incoming_handoff=incoming,
            chapter_obligations=obligations,
            rhythm=_rhythm_directive(mapping, rhythm_entry),
            style_mount=StyleMountRef(
                style_id=str(style.get("style_id") or ""),
                revision=str(style.get("version_id") or style.get("digest") or ""),
            ),
            source_refs=source_refs,
        )
        return PreparedScene(
            brief=brief,
            base_revision=scene_input_revision(root, facts.scene_id, source_refs),
        )


class AtomicProjectSceneCommitter:
    """Commit prose and semantic delta as one idempotent project operation."""

    def __init__(self, project_root: Path):
        self._root = project_root.expanduser().resolve()

    def commit(self, plan: SceneCommitPlan) -> SceneCommitReceipt:
        _scene_path(self._root, plan.scene_id)
        prose_path = self._root / "drafts" / "scenes" / f"{plan.scene_id}.md"
        delta_path = self._root / "workflow" / "scene_deltas" / f"{plan.scene_id}.json"
        receipt_path = self._root / "workflow" / "scene_commits" / f"{plan.scene_id}.json"
        existing = _read_json(receipt_path)
        if existing:
            return _existing_receipt(existing, plan)
        if prose_path.exists() or delta_path.exists():
            raise FileExistsError(
                f"scene has unowned formal output: {plan.scene_id}; recover or migrate it before lean commit"
            )

        facts = load_scene_facts(_scene_path(self._root, plan.scene_id))
        refs = _source_refs(self._root, facts)
        current_revision = scene_input_revision(self._root, plan.scene_id, refs)
        if current_revision != plan.base_revision:
            raise RuntimeError(
                f"scene source revision changed: {plan.base_revision[:12]} -> {current_revision[:12]}"
            )

        delta_payload = {
            "schema": "arcvellum/scene-delta/v2",
            "transaction_id": plan.transaction_id,
            "scene_id": plan.scene_id,
            **plan.scene_delta.to_dict(),
        }
        prose_digest = _sha256_text(plan.prose)
        delta_digest = _canonical_digest(delta_payload)
        committed_revision = _canonical_digest(
            {
                "base_revision": plan.base_revision,
                "prose_sha256": prose_digest,
                "delta_sha256": delta_digest,
            }
        )
        written_refs = (
            _rel(prose_path, self._root),
            _rel(delta_path, self._root),
            _rel(receipt_path, self._root),
        )
        receipt_payload = {
            "schema": "arcvellum/scene-commit/v2",
            "transaction_id": plan.transaction_id,
            "scene_id": plan.scene_id,
            "base_revision": plan.base_revision,
            "committed_revision": committed_revision,
            "prose_sha256": prose_digest,
            "delta_sha256": delta_digest,
            "review_decision": plan.review_decision.value if plan.review_decision else "deferred",
            "steward_approved": plan.steward_approved,
            "written_refs": list(written_refs),
        }
        atomic_write_batch(
            {
                prose_path: plan.prose.rstrip() + "\n",
                delta_path: _json_text(delta_payload),
                receipt_path: _json_text(receipt_payload),
            }
        )
        return SceneCommitReceipt(
            transaction_id=plan.transaction_id,
            scene_id=plan.scene_id,
            committed_revision=committed_revision,
            written_refs=written_refs,
        )


def scene_input_revision(root: Path, scene_id: str, source_refs: Iterable[str]) -> str:
    """Digest only inputs that can change the literary decision for this scene."""

    resolved = root.expanduser().resolve()
    inputs: list[dict[str, str]] = []
    for reference in sorted(dict.fromkeys(str(item) for item in source_refs)):
        path = (resolved / reference).resolve()
        if not path.is_relative_to(resolved) or not path.is_file():
            continue
        inputs.append({"ref": reference, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return _canonical_digest({"scene_id": scene_id, "inputs": inputs})


def known_scene_refs(brief) -> set[str]:
    """Return the prepared semantic namespace accepted by deterministic verify."""

    refs = set(brief.source_refs) | set(brief.canon_constraints) | set(brief.chapter_obligations)
    for participant in brief.participants:
        refs.update(
            {
                participant,
                f"character/{character_slug(participant)}",
                f"characters/{character_slug(participant)}.yaml",
            }
        )
    return {item for item in refs if item}


def _scene_path(root: Path, scene_id: str) -> Path:
    if not _SCENE_ID.fullmatch(scene_id):
        raise ValueError(f"unsafe scene id: {scene_id!r}")
    return root / "scenes" / f"{scene_id}.yaml"


def _source_refs(root: Path, facts: SceneFacts) -> tuple[str, ...]:
    refs: list[str] = [f"scenes/{facts.scene_id}.yaml"]
    refs.extend(_character_sources(root, facts.participants))
    refs.extend(reference for reference in facts.canon_refs if _safe_file(root, reference))
    refs.extend(reference for reference in _CORE_CANON if (root / reference).is_file())
    refs.extend(_rel(path, root) for path in active_style_evidence_paths(root))
    for reference in (
        "plot/rhythm_plan.json",
        "plot/word_budget/word_budget.json",
        f"plot/chapter_obligations/{facts.chapter_id}.json" if facts.chapter_id else "",
    ):
        if reference and (root / reference).is_file():
            refs.append(reference)
    previous = _previous_scene_id(root, facts)
    if previous:
        for reference in (
            f"workflow/scene_deltas/{previous}.json",
            f"workflow/scene_commits/{previous}.json",
        ):
            if (root / reference).is_file():
                refs.append(reference)
    return tuple(dict.fromkeys(refs))


def _character_sources(root: Path, participants: Iterable[str]) -> list[str]:
    wanted = {str(item).strip() for item in participants if str(item).strip()}
    wanted |= {character_slug(item) for item in wanted}
    found: list[str] = []
    characters = root / "characters"
    for path in sorted((*characters.glob("*.yaml"), *characters.glob("*.yml"))):
        if path.name.startswith("_"):
            continue
        text = read_character_text(path)
        aliases = {path.stem, character_slug(path.stem)}
        for field in ("character_id", "name"):
            value = character_field_value(text, field)
            if value:
                aliases.update((value, character_slug(value)))
        if aliases & wanted:
            found.append(_rel(path, root))
    return found


def _incoming_handoff(root: Path, facts: SceneFacts, refs: tuple[str, ...]) -> tuple[str, ...]:
    if facts.incoming_pressure:
        return (facts.incoming_pressure,)
    delta_ref = next((item for item in refs if item.startswith("workflow/scene_deltas/")), "")
    delta = _read_json(root / delta_ref) if delta_ref else {}
    values = delta.get("next_handoff") if isinstance(delta, dict) else None
    return _strings(values)


def _previous_scene_id(root: Path, current: SceneFacts) -> str:
    rows: list[tuple[float, str]] = []
    for path in sorted((root / "scenes").glob("*.yaml")):
        facts = load_scene_facts(path)
        order = float(facts.timeline_order) if facts.timeline_order is not None else float("inf")
        rows.append((order, facts.scene_id))
    ordered = [scene_id for _, scene_id in sorted(rows, key=lambda item: (item[0], item[1]))]
    try:
        index = ordered.index(current.scene_id)
    except ValueError:
        return ""
    return ordered[index - 1] if index > 0 else ""


def _chapter_obligations(root: Path, chapter_id: str) -> tuple[str, ...]:
    payload = _read_json(root / "plot" / "chapter_obligations" / f"{chapter_id}.json")
    if not payload:
        return ()
    return _strings(payload.get("obligation_ids") or payload.get("promise_ids"))


def _rhythm_entry(root: Path, scene_id: str) -> dict[str, Any]:
    payload = _read_json(root / "plot" / "rhythm_plan.json")
    for entry in payload.get("entries") or []:
        if isinstance(entry, dict) and str(entry.get("scene_id") or "") == scene_id:
            return entry
    return {}


def _scene_function(mapping: dict[str, Any], fallback: dict[str, Any]) -> str:
    rhythm = mapping.get("narrative_rhythm")
    local = rhythm if isinstance(rhythm, dict) else {}
    values = _strings(local.get("scene_function") or fallback.get("scene_function"))
    return " / ".join(values)


def _rhythm_directive(mapping: dict[str, Any], fallback: dict[str, Any]) -> RhythmDirective:
    value = mapping.get("narrative_rhythm")
    local = value if isinstance(value, dict) else {}
    return RhythmDirective(
        pace=str(local.get("pace") or fallback.get("pace") or "").strip(),
        detail=str(local.get("detail") or local.get("density") or fallback.get("detail") or "").strip(),
        scene_turn=str(local.get("scene_turn") or fallback.get("scene_turn") or "").strip(),
        reader_effect=str(local.get("reader_effect") or fallback.get("reader_effect") or "").strip(),
    )


def _risk_facts(scene_id: str, mapping: dict[str, Any]) -> SceneRiskFacts:
    rhythm = mapping.get("narrative_rhythm")
    curve = rhythm.get("tension_curve") if isinstance(rhythm, dict) else {}
    peak = _integer(curve.get("peak")) if isinstance(curve, dict) else 0
    climax = _integer(mapping.get("climax_weight")) or (4 if peak >= 5 else 2 if peak == 4 else 0)
    return SceneRiskFacts(
        scene_id=scene_id,
        canon_change=_integer(mapping.get("canon_change")),
        character_state_change=_integer(mapping.get("character_state_change")),
        new_asset_risk=_integer(mapping.get("new_asset_risk")),
        branch_ambiguity=_integer(mapping.get("branch_ambiguity")),
        climax_weight=climax,
        continuity_debt=_integer(mapping.get("continuity_debt")),
        style_novelty=_integer(mapping.get("style_novelty")),
    )


def _safe_file(root: Path, reference: str) -> bool:
    path = (root / reference).resolve()
    return path.is_relative_to(root) and path.is_file()


def _existing_receipt(payload: dict[str, Any], plan: SceneCommitPlan) -> SceneCommitReceipt:
    if str(payload.get("transaction_id") or "") != plan.transaction_id:
        raise RuntimeError(f"scene already committed by another transaction: {plan.scene_id}")
    if str(payload.get("prose_sha256") or "") != _sha256_text(plan.prose):
        raise RuntimeError(f"idempotent scene replay changed prose: {plan.scene_id}")
    return SceneCommitReceipt(
        transaction_id=plan.transaction_id,
        scene_id=plan.scene_id,
        committed_revision=str(payload.get("committed_revision") or ""),
        written_refs=tuple(str(item) for item in payload.get("written_refs") or ()),
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid project JSON: {path}") from exc
    return value if isinstance(value, dict) else {}


def _strings(value: Any) -> tuple[str, ...]:
    values = value if isinstance(value, (list, tuple)) else [value]
    return tuple(str(item).strip() for item in values if str(item or "").strip())


def _integer(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.rstrip().encode("utf-8")).hexdigest()


def _canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


__all__ = [
    "AtomicProjectSceneCommitter",
    "ProjectSceneBriefProvider",
    "known_scene_refs",
    "scene_input_revision",
]
