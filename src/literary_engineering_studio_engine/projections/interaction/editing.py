"""Low-risk display override and user-note operations."""

from __future__ import annotations

from pathlib import Path

from ...display_cleaner import read_json_file, truncate_text
from ...project_interaction_common import (
    DIRECT_EDIT_FIELDS, TARGET_TYPES, UI_OVERRIDES_SCHEMA, USER_NOTE_SCHEMA,
    _append_jsonl, _make_id, _now, _rel, _safe_target_id, _safe_token, _safe_value, _stamp,
    _write_json_atomic,
)

def build_editable_schema(project_root: Path) -> dict[str, object]:
    root = project_root.resolve()
    return {
        "schema": "literary-engineering-workbench/editable-schema/v0.1",
        "project_root": str(root),
        "mode": "safe-display-and-choice-layer",
        "direct_fields": [
            {
                "field": "display_title",
                "label": "展示标题",
                "risk": "low",
                "writes_to": "workflow/ui_overrides.json",
            },
            {
                "field": "display_summary",
                "label": "展示摘要",
                "risk": "low",
                "writes_to": "workflow/ui_overrides.json",
            },
            {
                "field": "tags",
                "label": "标签",
                "risk": "low",
                "writes_to": "workflow/ui_overrides.json",
            },
            {
                "field": "note",
                "label": "用户备注",
                "risk": "low",
                "writes_to": "workflow/ui_overrides.json",
            },
            {
                "field": "word_count_target",
                "label": "目标字数提示",
                "risk": "medium",
                "writes_to": "workflow/ui_overrides.json",
                "requires": "rerun route-audit or word-budget before relying on it as a formal constraint",
            },
        ],
        "candidate_only_changes": [
            "角色背景故事、动机、秘密、关系变化",
            "世界规则、地点、组织、时间线",
            "正文、修订正文和章节合稿",
            "正式 canon、角色状态写回、发布 latest 指针",
        ],
        "rules": [
            "Direct edits never overwrite canon, characters, plot, drafts, reviews, approvals, task files, or releases.",
            "Fields that affect planning are saved as user intent and must be routed through CLI review before formal use.",
            "Promotion, release, state writeback, and approval still require their formal gates.",
        ],
    }

def save_display_field(
    project_root: Path,
    *,
    target_type: str,
    target_id: str,
    field: str,
    value: object,
    actor: str = "user-ui",
) -> dict[str, object]:
    root = project_root.resolve()
    target_type = _safe_token(target_type, "target_type")
    target_id = _safe_target_id(target_id)
    field = _safe_token(field, "field")
    if target_type not in TARGET_TYPES:
        raise ValueError(f"target_type must be one of: {', '.join(sorted(TARGET_TYPES))}")
    if field not in DIRECT_EDIT_FIELDS:
        raise ValueError(f"field is not frontend-editable: {field}")
    safe_value = _safe_value(value)
    path = root / "workflow" / "ui_overrides.json"
    payload = read_json_file(path)
    if not payload:
        payload = {"schema": UI_OVERRIDES_SCHEMA, "items": {}}
    items = payload.get("items") if isinstance(payload.get("items"), dict) else {}
    key = f"{target_type}:{target_id}"
    record = items.get(key) if isinstance(items.get(key), dict) else {}
    fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
    fields[field] = safe_value
    now = _now()
    record.update(
        {
            "target_type": target_type,
            "target_id": target_id,
            "fields": fields,
            "updated_at": now,
            "updated_by": actor or "user-ui",
        }
    )
    if field.startswith("word_count_"):
        record["formal_effect"] = "display-only until word-budget/route-audit validates the change"
    items[key] = record
    payload["items"] = items
    payload["updated_at"] = now
    _write_json_atomic(path, payload)
    _append_jsonl(
        root / "workflow" / "user_notes" / "edit_log.jsonl",
        {
            "schema": "literary-engineering-workbench/ui-edit-log/v0.1",
            "target_type": target_type,
            "target_id": target_id,
            "field": field,
            "actor": actor or "user-ui",
            "recorded_at": now,
            "formal_effect": record.get("formal_effect", "display-only"),
        },
    )
    return {"ok": True, "path": _rel(path, root), "key": key, "record": record}

def record_ui_note(
    project_root: Path,
    *,
    target_type: str,
    target_id: str,
    note: str,
    actor: str = "user-ui",
) -> dict[str, object]:
    root = project_root.resolve()
    target_type = _safe_token(target_type, "target_type")
    target_id = _safe_target_id(target_id)
    if target_type not in TARGET_TYPES:
        raise ValueError(f"target_type must be one of: {', '.join(sorted(TARGET_TYPES))}")
    text = truncate_text(str(note or "").strip(), 4000)
    if not text:
        raise ValueError("note must not be empty")
    now = _now()
    record = {
        "schema": USER_NOTE_SCHEMA,
        "note_id": _make_id("note", target_type, target_id),
        "target_type": target_type,
        "target_id": target_id,
        "note": text,
        "actor": actor or "user-ui",
        "recorded_at": now,
        "formal_effect": "user note only; platform agent must route material changes through candidates and review",
    }
    notes_dir = root / "workflow" / "user_notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    note_path = notes_dir / f"{record['note_id']}.json"
    _write_json_atomic(note_path, record)
    _append_jsonl(notes_dir / "index.jsonl", record)
    return {"ok": True, "note": record, "note_path": _rel(note_path, root), "index_path": "workflow/user_notes/index.jsonl"}
