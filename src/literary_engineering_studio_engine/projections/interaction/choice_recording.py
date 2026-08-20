"""Durable human-choice recording and formal evidence materialization."""

from __future__ import annotations

from pathlib import Path

from ...approval import record_workflow_approval
from ...display_cleaner import read_json_file, truncate_text
from ...project_interaction_common import (
    DECISION_TYPES,
    HUMAN_CHOICE_SCHEMA,
    _append_jsonl,
    _make_id,
    _now,
    _rel,
    _safe_choice_id,
    _safe_mapping,
    _safe_options,
    _safe_target_id,
    _safe_token,
    _write_json_atomic,
)


APPROVAL_DECISION_TYPES = {
    "asset_approval", "release_approval", "canon_patch_approval", "state_patch_confirmation",
}


def record_human_choice(project_root: Path, payload: dict[str, object]) -> dict[str, object]:
    root = project_root.resolve()
    record = _validated_record(payload)
    choices_dir = root / "workflow" / "human_choices"
    choices_dir.mkdir(parents=True, exist_ok=True)
    choice_path = choices_dir / f"{record['choice_id']}.json"
    if choice_path.exists():
        return _existing_choice_result(root, choice_path, record)
    materialized = _materialize_choice(root, record, choice_path, bool(payload.get("materialize", True)))
    record["materialized"] = materialized
    record["consumed"] = bool(materialized)
    record["status"] = "submitted" if record["consumed"] else "recorded"
    _write_json_atomic(choice_path, record)
    _append_jsonl(choices_dir / "index.jsonl", record)
    return _record_result(root, choice_path, record, duplicate=False)


def finalize_human_choice(
    project_root: Path,
    choice_id: str,
    *,
    materialized: str,
    effect: dict[str, object] | None = None,
    consumed: bool = True,
) -> dict[str, object]:
    root = project_root.resolve()
    safe_id = _safe_choice_id(choice_id)
    path = root / "workflow" / "human_choices" / f"{safe_id}.json"
    record = read_json_file(path)
    if not record:
        raise FileNotFoundError(f"human choice not found: {safe_id}")
    record["materialized"] = truncate_text(str(materialized or ""), 1000)
    record["effect"] = _safe_mapping(effect or {})
    record["consumed"] = bool(consumed)
    record["status"] = "submitted" if consumed else "recorded"
    record["finalized_at"] = _now()
    _write_json_atomic(path, record)
    return record


def materialize_branch_selection(root: Path, record: dict[str, object], choice_path: Path) -> str:
    target = record.get("target") if isinstance(record.get("target"), dict) else {}
    scene_id = _safe_target_id(str(target.get("scene_id") or target.get("target_id") or ""))
    if not scene_id:
        raise ValueError("branch selection target.scene_id is required")
    branch_dir = root / "branches" / scene_id
    manifest = branch_dir / "branch_manifest.json"
    if not manifest.exists():
        raise FileNotFoundError(f"branch manifest not found: {manifest}")
    branch_dir.mkdir(parents=True, exist_ok=True)
    path = branch_dir / "branch_selection.md"
    path.write_text(_branch_selection_markdown(root, scene_id, record, choice_path), encoding="utf-8")
    return _rel(path, root)


def materialize_approval(root: Path, record: dict[str, object]) -> str:
    selected = str(record.get("selected") or "").strip()
    if selected not in {"approve", "revise", "reject", "defer"}:
        raise ValueError("approval choice must select approve, revise, reject, or defer")
    target = record.get("target") if isinstance(record.get("target"), dict) else {}
    decision_type = str(record.get("decision_type") or "")
    run_id = _approval_run_id(root, decision_type, target)
    if not run_id:
        raise ValueError(f"{decision_type} choice does not identify its approval target")
    result = record_workflow_approval(
        root, run_id, selected, actor=str(record.get("actor") or "user-ui"),
        notes=str(record.get("rationale") or ""), subject_sha256=str(target.get("candidate_sha256") or ""),
    )
    return _rel(result.approval_path, root)


def _validated_record(payload: dict[str, object]) -> dict[str, object]:
    decision_type = _safe_token(str(payload.get("decision_type") or "general_project_choice"), "decision_type")
    if decision_type not in DECISION_TYPES:
        raise ValueError(f"decision_type must be one of: {', '.join(sorted(DECISION_TYPES))}")
    selected = truncate_text(str(payload.get("selected") or "").strip(), 200)
    if not selected:
        raise ValueError("selected must not be empty")
    choice_id = str(payload.get("choice_id") or "").strip()
    choice_id = _safe_choice_id(choice_id) if choice_id else _make_id("choice", decision_type, selected)
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    options = payload.get("options") if isinstance(payload.get("options"), list) else []
    return {
        "schema": HUMAN_CHOICE_SCHEMA, "choice_id": choice_id,
        "route": truncate_text(str(payload.get("route") or ""), 80),
        "task_id": truncate_text(str(payload.get("task_id") or ""), 140),
        "decision_type": decision_type, "target": _safe_mapping(target), "options": _safe_options(options),
        "selected": selected, "rationale": truncate_text(str(payload.get("rationale") or "").strip(), 2000),
        "actor": truncate_text(str(payload.get("actor") or "user-ui"), 80), "status": "recorded",
        "recorded_at": _now(),
        "formal_effect": "human choice evidence only; downstream route gates still validate produced artifacts",
    }


def _existing_choice_result(root: Path, path: Path, record: dict[str, object]) -> dict[str, object]:
    existing = read_json_file(path)
    same_choice = (
        str(existing.get("decision_type") or "") == record["decision_type"]
        and str(existing.get("selected") or "") == record["selected"]
        and _safe_mapping(existing.get("target") if isinstance(existing.get("target"), dict) else {}) == record["target"]
    )
    if not same_choice:
        raise ValueError("这个创作决定已经用另一项选择提交，不能静默覆盖。")
    return _record_result(root, path, existing, duplicate=True)


def _materialize_choice(root: Path, record: dict[str, object], path: Path, enabled: bool) -> str:
    if not enabled:
        return ""
    decision_type = str(record.get("decision_type") or "")
    if decision_type == "branch_selection":
        _write_json_atomic(path, record)
        return materialize_branch_selection(root, record, path)
    return materialize_approval(root, record) if decision_type in APPROVAL_DECISION_TYPES else ""


def _record_result(root: Path, path: Path, record: dict[str, object], *, duplicate: bool) -> dict[str, object]:
    return {
        "ok": True, "choice": record, "choice_path": _rel(path, root),
        "index_path": "workflow/human_choices/index.jsonl",
        "materialized": str(record.get("materialized") or ""), "duplicate": duplicate,
    }


def _approval_run_id(root: Path, decision_type: str, target: dict[str, object]) -> str:
    run_id = str(target.get("target_id") or target.get("scene_id") or "").strip()
    if decision_type == "release_approval" and run_id and not run_id.startswith("release-"):
        return f"release-{run_id}"
    if decision_type not in {"canon_patch_approval", "state_patch_confirmation"}:
        return run_id
    patch_rel = str(target.get("patch") or "").strip()
    patch = root / patch_rel if patch_rel else None
    return str(target.get("approval_run_id") or patch.stem) if patch is not None and patch.is_file() else run_id


def _branch_selection_markdown(root: Path, scene_id: str, record: dict[str, object], choice_path: Path) -> str:
    lines = [
        f"# Branch Selection：{scene_id}", "", "## 用户结构化选择", "",
        "- decision: selected", f"- selected_branch: {record.get('selected', '')}",
        f"- actor: {record.get('actor', 'user-ui')}", f"- selected_at: {record.get('recorded_at', '')}",
        f"- source_choice: {_rel(choice_path, root)}", "", "## 选择理由", "",
        str(record.get("rationale") or "用户通过前端结构化选择确认。"), "", "## 正式边界", "",
        "- 本文件只确认分支选择，不代表正文、canon、状态写回或发布已完成。",
        "- 下一步仍必须由 CLI route gate 验证 composition、generation、review 和 promotion。",
    ]
    return "\n".join(lines) + "\n"


__all__ = ["finalize_human_choice", "materialize_approval", "materialize_branch_selection", "record_human_choice"]
