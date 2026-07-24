"""Atomic storage and input normalization for frontend-safe project interaction."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path

from ...display_cleaner import read_json_file, truncate_text

UI_OVERRIDES_SCHEMA = "literary-engineering-workbench/ui-overrides/v0.1"

USER_NOTE_SCHEMA = "literary-engineering-workbench/user-note/v0.1"

HUMAN_CHOICE_SCHEMA = "literary-engineering-workbench/human-choice/v0.1"

TARGET_TYPES = {"project", "drafts", "characters", "world", "scenes", "branches", "style", "reviews", "word_budget", "canon_patches"}

DIRECT_EDIT_FIELDS = {
    "display_title",
    "display_summary",
    "tags",
    "note",
    "display_name",
    "importance_label",
    "word_count_target",
    "word_count_min",
    "word_count_max",
    "preferred_style_id",
}

DECISION_TYPES = {
    "branch_selection",
    "style_mount",
    "asset_approval",
    "release_approval",
    "canon_patch_approval",
    "word_budget_direction",
    "revision_direction",
    "cross_asset_alignment",
    "state_patch_confirmation",
    "general_project_choice",
}

def _safe_mapping(value: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, raw in value.items():
        safe_key = _safe_token(str(key), "target key")
        result[safe_key] = truncate_text(str(raw), 240)
    return result

def _safe_options(options: list[object]) -> list[dict[str, str]]:
    cleaned = []
    for item in options[:20]:
        if not isinstance(item, dict):
            continue
        option_id = truncate_text(str(item.get("id") or item.get("label") or ""), 120)
        if not option_id:
            continue
        cleaned.append(
            {
                "id": option_id,
                "label": truncate_text(str(item.get("label") or option_id), 120),
                "summary": truncate_text(str(item.get("summary") or ""), 500),
            }
        )
    return cleaned

def _safe_value(value: object) -> object:
    if isinstance(value, str):
        return truncate_text(value, 4000)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [truncate_text(str(item), 240) for item in value[:40]]
    return truncate_text(str(value), 1000)

def _safe_token(value: str, label: str) -> str:
    token = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", token):
        raise ValueError(f"invalid {label}")
    if ".." in token:
        raise ValueError(f"invalid {label}")
    return token

def _safe_target_id(value: str) -> str:
    target = value.strip().replace("/", "__").replace("\\", "__")
    target = re.sub(r"[^A-Za-z0-9_.-]", "_", target)
    target = re.sub(r"_+", "_", target).strip("._-")
    return target[:120]

def _safe_approval_target(value: str) -> str:
    target = value.strip()
    if not target or len(target) > 128 or ".." in target or any(char in target for char in "/\\"):
        raise ValueError("invalid approval target")
    if any(ord(char) < 32 for char in target):
        raise ValueError("invalid approval target")
    return target

def _safe_choice_id(value: str) -> str:
    choice_id = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", choice_id) or ".." in choice_id:
        raise ValueError("invalid choice_id")
    return choice_id

def _stable_choice_id(choice: dict[str, object]) -> str:
    identity = {
        "route": choice.get("route") or "",
        "decision_type": choice.get("decision_type") or "",
        "target": choice.get("target") or {},
        "task_step": choice.get("task_step") or "",
        "next_action": choice.get("next_action") or "",
        "source_paths": choice.get("source_paths") or [],
        "options": choice.get("options") or [],
    }
    digest = hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]
    decision_type = _safe_target_id(str(choice.get("decision_type") or "general")) or "general"
    return _safe_choice_id(f"choice.{decision_type}.{digest}")

def _resolved_choice_ids(root: Path) -> set[str]:
    folder = root / "workflow" / "human_choices"
    if not folder.is_dir():
        return set()
    resolved: set[str] = set()
    for path in folder.glob("choice.*.json"):
        payload = read_json_file(path)
        if payload.get("consumed") is True:
            resolved.add(str(payload.get("choice_id") or path.stem))
    return resolved

def _make_id(prefix: str, *parts: str) -> str:
    joined = ".".join(_safe_target_id(str(part)) for part in parts if str(part).strip())
    return _safe_choice_id(f"{prefix}.{joined}.{_stamp()}")

def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
