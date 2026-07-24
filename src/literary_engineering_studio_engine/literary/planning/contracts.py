"""Formal per-scene word-budget contracts and deterministic adherence checks."""

from __future__ import annotations

import json
from pathlib import Path

from ...agent_tasks import agent_task_completion_status
from ...draft_text import (
    count_delivery_chars,
    count_delivery_chinese_content_chars,
    delivery_char_count_mapping,
)
from ...longform_materializer import longform_materialization_status
from ...text_counts import CHINESE_CONTENT_COUNT_UNIT, MACHINE_NONSPACE_COUNT_UNIT
from .common import _project_int, _read, _read_json, _rel, _scalar, _to_int
from .inventory import _chapter_budget_row, _scene_ids_for_chapter, _scene_word_count_target

def load_word_budget_summary(root: Path) -> dict[str, object]:
    path = root / "plot" / "word_budget" / "word_budget.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {
        "path": _rel(path, root),
        "status": payload.get("status", ""),
        "target": payload.get("target", {}),
        "totals": payload.get("totals", {}),
        "chapter_budgets": payload.get("chapter_budgets", []),
        "scene_inventory_binding": payload.get("scene_inventory_binding", {}),
        "issues": payload.get("issues", []),
    }

def scene_word_budget_contract(
    root: Path,
    scene_path: Path,
    *,
    materialization_scope: str = "full",
) -> dict[str, object]:
    """Return the hard per-scene word-budget contract for formal generation/review."""

    scope = materialization_scope.strip().lower()
    if scope not in {"full", "scene"}:
        raise ValueError("materialization_scope must be 'full' or 'scene'")
    root = root.resolve()
    scene_path = scene_path if scene_path.is_absolute() else root / scene_path
    scene_text = _read(scene_path)
    scene_id = _scalar(scene_text, "scene_id") or scene_path.stem
    chapter_id = _scalar(scene_text, "chapter_id") or "unassigned"
    scene_yaml_target = _scene_word_count_target(scene_text)
    scene_yaml_min = _to_int(_scalar(scene_text, "word_count_min"))
    scene_yaml_max = _to_int(_scalar(scene_text, "word_count_max"))
    project_text = _read(root / "project.yaml")
    project_target = int(_project_int(project_text, "target_length") or _project_int(project_text, "target_words") or 0)
    required = project_target >= 100000
    budget_path = root / "plot" / "word_budget" / "word_budget.json"
    base = {
        "schema": "literary-engineering-workbench/scene-word-budget-contract/v1",
        "scene_id": scene_id,
        "chapter_id": chapter_id,
        "required": required,
        "budget_path": _rel(budget_path, root),
        "status": "not_required",
        "message": "word budget is not required for this project scale",
        "count_unit": CHINESE_CONTENT_COUNT_UNIT,
        "machine_count_unit": MACHINE_NONSPACE_COUNT_UNIT,
        "target_words": 0,
        "min_words": 0,
        "max_words": 0,
        "target_chinese_chars": 0,
        "min_chinese_chars": 0,
        "max_chinese_chars": 0,
        "scene_yaml_target_words": scene_yaml_target,
        "scene_yaml_target_chinese_chars": scene_yaml_target,
        "derived_target_words": 0,
        "derived_target_chinese_chars": 0,
        "machine_count_mapping": {},
        "source": "",
        "alignment_status": "",
        "warnings": [],
        "tolerance": {"min_ratio": 0.85, "max_ratio": 1.25},
        "narrative_load": [],
        "budget_status": "",
    }
    if not budget_path.exists():
        if required:
            base.update(
                {
                    "status": "missing",
                    "message": "formal longform scene generation requires plot/word_budget/word_budget.json",
                }
            )
        return base
    payload = _read_json(budget_path)
    if not payload:
        base.update({"status": "invalid", "required": True, "message": "word_budget.json is not valid JSON"})
        return base
    budget_status = str(payload.get("status") or "").strip().lower()
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    if int(target.get("target_words") or totals.get("target_words") or project_target or 0) >= 100000:
        required = True
    base["required"] = required
    base["budget_status"] = budget_status
    if budget_status == "needs_expansion":
        materialized, materialization_message = longform_materialization_status(
            root,
            scene_path=scene_path if scope == "scene" else None,
        )
        if not materialized:
            base.update(
                {
                    "status": "needs_expansion",
                    "message": "word budget reports needs_expansion; process budget and scene-inventory sidecars before formal generation",
                    "materialization_status": materialization_message,
                }
            )
            return base
        base["budget_status"] = "materialized"
        base["materialization_status"] = materialization_message
    chapter_row = _chapter_budget_row(payload, chapter_id)
    if not chapter_row:
        if required:
            base.update(
                {
                    "status": "missing_chapter",
                    "message": f"word budget has no chapter row for {chapter_id}",
                }
            )
        return base
    chapter_target = _to_int(chapter_row.get("target_words"))
    scene_count = max(
        _to_int(chapter_row.get("target_scene_count")),
        _to_int(chapter_row.get("scene_count")),
        len(_scene_ids_for_chapter(root, chapter_id)),
        1,
    )
    derived_target = _to_int(chapter_row.get("avg_scene_words")) or round(chapter_target / max(scene_count, 1))
    target_words = scene_yaml_target or derived_target
    min_words = max(round(target_words * 0.85), 1) if target_words else 0
    max_words = max(round(target_words * 1.25), min_words) if target_words else 0
    if scene_yaml_target:
        min_words = scene_yaml_min or min_words
        max_words = scene_yaml_max or max_words
        if max_words and min_words > max_words:
            base.update(
                {
                    "status": "invalid",
                    "message": "scene.yaml word_count_min is greater than word_count_max",
                    "target_words": target_words,
                    "min_words": min_words,
                    "max_words": max_words,
                    "target_chinese_chars": target_words,
                    "min_chinese_chars": min_words,
                    "max_chinese_chars": max_words,
                    "source": "scene_yaml",
                    "derived_target_words": derived_target,
                    "derived_target_chinese_chars": derived_target,
                }
            )
            return base
    warnings: list[str] = []
    alignment_status = "derived_from_word_budget"
    source = "word_budget"
    if scene_yaml_target:
        source = "scene_yaml"
        if derived_target and (scene_yaml_target < round(derived_target * 0.5) or scene_yaml_target > round(derived_target * 1.8)):
            alignment_status = "manual_override_needs_review"
            warnings.append(
                f"scene.yaml word_count_target={scene_yaml_target} differs sharply from derived chapter average {derived_target}; require word-budget review confirmation"
            )
        else:
            alignment_status = "scene_yaml_aligned"
    narrative_load = chapter_row.get("required_functions") or chapter_row.get("scene_load") or [
        "mainline_action",
        "relationship_pressure",
        "information_release",
        "consequence_chain",
        "setup_or_payoff",
    ]
    if isinstance(narrative_load, dict):
        narrative_load = [str(key) for key, value in narrative_load.items() if _to_int(value) > 0]
    if not isinstance(narrative_load, list):
        narrative_load = [str(narrative_load)]
    base.update(
        {
            "status": "pass" if target_words else "invalid",
            "message": "scene Chinese-content word budget contract is ready" if target_words else "scene target Chinese-content characters could not be computed",
            "target_words": target_words,
            "min_words": min_words,
            "max_words": max_words,
            "target_chinese_chars": target_words,
            "min_chinese_chars": min_words,
            "max_chinese_chars": max_words,
            "scene_yaml_target_words": scene_yaml_target,
            "scene_yaml_target_chinese_chars": scene_yaml_target,
            "derived_target_words": derived_target,
            "derived_target_chinese_chars": derived_target,
            "machine_count_mapping": {
                "target_unit": CHINESE_CONTENT_COUNT_UNIT,
                "machine_unit": MACHINE_NONSPACE_COUNT_UNIT,
                "target_chinese_chars": target_words,
                "rough_expected_machine_chars": target_words,
                "rough_expected_machine_chars_range": [round(target_words * 0.95), round(target_words * 1.15)],
                "baseline_machine_chars_1_to_1_range": [round(target_words * 0.95), round(target_words * 1.15)],
                "mapping_basis": "pre_generation_baseline_1_to_1",
                "note": "Formal gates use Chinese content chars; machine nonspace chars are diagnostic only. This pre-generation range is a rough 1:1 Chinese-prose baseline for UI/platform displays, not a pass/fail threshold.",
            },
            "source": source,
            "alignment_status": alignment_status,
            "warnings": warnings,
            "narrative_load": [str(item) for item in narrative_load if str(item).strip()],
            "chapter_target_words": chapter_target,
            "chapter_scene_count": scene_count,
        }
    )
    return base

def ensure_scene_word_budget_ready(
    root: Path,
    scene_path: Path,
    *,
    materialization_scope: str = "full",
) -> dict[str, object]:
    """Raise when a formal scene has no usable word-budget contract."""

    contract = scene_word_budget_contract(root, scene_path, materialization_scope=materialization_scope)
    if contract.get("status") == "not_required":
        return contract
    if contract.get("status") == "pass":
        budget_task = root / "plot" / "word_budget" / "word_budget.agent_tasks.md"
        budget_review = root / "reviews" / "word_budget" / "word_budget_review.md"
        completion = agent_task_completion_status(budget_task, root=root)
        if completion.get("complete") is not True:
            raise ValueError(
                "formal scene generation requires the word-budget platform-agent task to be completed before prose: "
                f"{completion.get('message')}"
            )
        if not budget_review.exists():
            raise ValueError(
                "formal scene generation requires reviews/word_budget/word_budget_review.md before prose. "
                "The platform agent must review the word-budget to confirm the target-length to narrative-inventory mapping."
            )
        return contract
    raise ValueError(
        "formal scene generation requires a ready scene word-budget contract: "
        f"{contract.get('message')}. Run word-budget / longform-budget, handle its .agent_tasks.md sidecars, "
        "review the budgeted outline and scene inventory, then retry."
    )

def word_budget_adherence_for_body(
    root: Path,
    scene_path: Path,
    body: str,
    *,
    materialization_scope: str = "full",
) -> dict[str, object]:
    """Return deterministic cleaned-body word-budget adherence for a scene draft/candidate."""

    contract = scene_word_budget_contract(root, scene_path, materialization_scope=materialization_scope)
    clean_machine_chars = count_delivery_chars(body)
    clean_chinese_chars = count_delivery_chinese_content_chars(body)
    status = str(contract.get("status") or "")
    target_chinese_chars = _to_int(contract.get("target_chinese_chars") or contract.get("target_words"))
    mapping = delivery_char_count_mapping(body, target_chinese_chars=target_chinese_chars)
    if status == "not_required":
        conclusion = "not_required"
        message = "word budget is not required for this project scale"
    elif status != "pass":
        conclusion = "revise_required"
        message = str(contract.get("message") or "word budget contract is not ready")
    else:
        min_words = _to_int(contract.get("min_chinese_chars") or contract.get("min_words"))
        max_words = _to_int(contract.get("max_chinese_chars") or contract.get("max_words"))
        if clean_chinese_chars < min_words:
            conclusion = "under_target"
            message = f"cleaned body has {clean_chinese_chars} Chinese content chars, below min_chinese_chars={min_words}"
        elif max_words and clean_chinese_chars > max_words:
            conclusion = "over_target"
            message = f"cleaned body has {clean_chinese_chars} Chinese content chars, above max_chinese_chars={max_words}"
        else:
            conclusion = "pass"
            message = "cleaned body is within the scene Chinese-content word-budget range"
    return {
        "status": conclusion,
        "count_unit": CHINESE_CONTENT_COUNT_UNIT,
        "machine_count_unit": MACHINE_NONSPACE_COUNT_UNIT,
        "clean_body_words": clean_chinese_chars,
        "clean_body_chinese_chars": clean_chinese_chars,
        "clean_body_machine_chars": clean_machine_chars,
        "target_words": _to_int(contract.get("target_words")),
        "min_words": _to_int(contract.get("min_words")),
        "max_words": _to_int(contract.get("max_words")),
        "target_chinese_chars": target_chinese_chars,
        "min_chinese_chars": _to_int(contract.get("min_chinese_chars") or contract.get("min_words")),
        "max_chinese_chars": _to_int(contract.get("max_chinese_chars") or contract.get("max_words")),
        "formal_count_policy": "pass/fail uses clean_body_chinese_chars against target_chinese_chars/min_chinese_chars/max_chinese_chars; *_words fields are legacy aliases.",
        "machine_count_mapping": mapping,
        "narrative_load": contract.get("narrative_load", []),
        "budget_contract_status": status,
        "budget_path": contract.get("budget_path", ""),
        "message": message,
    }
