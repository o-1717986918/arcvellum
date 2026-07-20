"""Apply approved character state patches to character YAML files."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CharacterStateApplyResult:
    project_root: Path
    patch_path: Path
    manifest_path: Path
    report_path: Path
    scene_id: str
    applied_character_count: int
    update_count: int
    approval_run_id: str
    status: str


def apply_character_state_patch(
    project_root: Path,
    patch: Path | None = None,
    approval_run_id: str = "",
    allow_unapproved: bool = False,
    allow_unresolved: bool = False,
    output: Path | None = None,
    json_output: Path | None = None,
) -> CharacterStateApplyResult:
    """Apply a reviewed state patch after approval."""

    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")

    patch_path = _resolve_patch(root, patch)
    payload = json.loads(_read(patch_path))
    scene_id = str(payload.get("scene_id") or patch_path.stem.replace("_state_patch", "") or "scene")
    unresolved = payload.get("unresolved_changes", [])
    if unresolved and not allow_unresolved:
        raise RuntimeError("state patch contains unresolved changes; pass allow_unresolved=True to apply anyway")

    approval = _find_approval(root, approval_run_id)
    if approval is None and not allow_unapproved:
        raise RuntimeError("state-apply requires an approve record; pass approval_run_id or use allow_unapproved for internal writeback")

    applied: list[dict[str, object]] = []
    total_updates = 0
    for item in payload.get("characters", []):
        if not isinstance(item, dict):
            continue
        character_file = _safe_character_file(root, item)
        original = _read(character_file)
        updated, update_count = _apply_one_character(original, item, patch_path, root)
        if updated != original:
            character_file.write_text(updated, encoding="utf-8")
        total_updates += update_count
        applied.append(
            {
                "character_id": item.get("character_id", ""),
                "name": item.get("name", ""),
                "file": _rel(character_file, root),
                "updates": update_count,
                "changed": updated != original,
            }
        )

    status = "applied" if approval is not None else "applied_internal"
    applied_at = _now()
    manifest_path = _resolve(root, json_output, root / "characters" / "state_patches" / f"{scene_id}_state_apply.json")
    report_path = _resolve(root, output, root / "characters" / "state_patches" / f"{scene_id}_state_apply.md")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "literary-engineering-workbench/character-state-apply/v0.1",
        "applied_at": applied_at,
        "status": status,
        "scene_id": scene_id,
        "patch": _rel(patch_path, root),
        "approval": approval or {"decision": "allow_unapproved", "run_id": "", "notes": ""},
        "allow_unresolved": allow_unresolved,
        "applied_characters": applied,
        "update_count": total_updates,
        "guardrails": [
            "只写回人物档案中的 state、arc、relationships 和 memory_refs。",
            "不写 canon/facts.json，不确认世界观事实。",
            "重复执行时会尽量去重已有列表项。",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_report(manifest), encoding="utf-8")
    return CharacterStateApplyResult(
        project_root=root,
        patch_path=patch_path,
        manifest_path=manifest_path,
        report_path=report_path,
        scene_id=scene_id,
        applied_character_count=len(applied),
        update_count=total_updates,
        approval_run_id=str((approval or {}).get("run_id", "")),
        status=status,
    )


def _apply_one_character(text: str, patch: dict[str, Any], patch_path: Path, root: Path) -> tuple[str, int]:
    updates = patch.get("proposed_updates", {})
    state_updates = updates.get("state", {}) if isinstance(updates, dict) else {}
    arc_updates = updates.get("arc", {}) if isinstance(updates, dict) else {}
    relationship_updates = updates.get("relationships", {}) if isinstance(updates, dict) else {}
    if not isinstance(state_updates, dict):
        state_updates = {}
    if not isinstance(arc_updates, dict):
        arc_updates = {}
    if not isinstance(relationship_updates, dict):
        relationship_updates = {}

    result = text.rstrip() + "\n"
    count = 0
    result, changed = _append_nested_list(result, "state", "known_facts", _string_list(state_updates.get("known_facts_add")))
    count += changed
    result, changed = _append_nested_list(result, "state", "resources", _string_list(state_updates.get("resources_add")))
    count += changed
    result, changed = _set_nested_scalar(result, "state", "location", str(state_updates.get("location_note") or ""))
    count += changed
    result, changed = _set_nested_scalar(result, "state", "health", str(state_updates.get("health_note") or ""))
    count += changed
    result, changed = _append_nested_list(result, "arc", "required_trigger_events", _string_list(arc_updates.get("candidate_changes")))
    count += changed
    result, changed = _append_top_list(result, "relationships", _string_list(relationship_updates.get("candidate_changes")))
    count += changed
    result, changed = _append_top_list(result, "memory_refs", [f"state_patch:{_rel(patch_path, root)}"])
    count += changed
    return result, count


def _append_nested_list(text: str, section: str, key: str, items: list[str]) -> tuple[str, int]:
    items = _clean_items(items)
    if not items:
        return text, 0
    lines = text.splitlines()
    section_idx = _ensure_top_section(lines, section)
    section_end = _top_section_end(lines, section_idx)
    key_idx = _find_nested_key(lines, section_idx, section_end, key)
    if key_idx < 0:
        insert = [f"  {key}:"] + [f"    - {item}" for item in items]
        lines[section_end:section_end] = insert
        return "\n".join(lines) + "\n", len(items)

    block_end = _nested_block_end(lines, key_idx)
    existing = _existing_list_items(lines[key_idx:block_end])
    new_items = [item for item in items if item not in existing]
    if not new_items:
        return text, 0
    if block_end == key_idx + 1 or lines[key_idx].strip().endswith("[]"):
        lines[key_idx] = f"  {key}:"
        lines[key_idx + 1:key_idx + 1] = [f"    - {item}" for item in new_items]
    else:
        lines[block_end:block_end] = [f"    - {item}" for item in new_items]
    return "\n".join(lines) + "\n", len(new_items)


def _set_nested_scalar(text: str, section: str, key: str, value: str) -> tuple[str, int]:
    value = value.strip()
    if not value:
        return text, 0
    lines = text.splitlines()
    section_idx = _ensure_top_section(lines, section)
    section_end = _top_section_end(lines, section_idx)
    key_idx = _find_nested_key(lines, section_idx, section_end, key)
    new_line = f"  {key}: {_yaml_quote(value)}"
    if key_idx < 0:
        lines[section_end:section_end] = [new_line]
        return "\n".join(lines) + "\n", 1
    if lines[key_idx] == new_line:
        return text, 0
    lines[key_idx] = new_line
    return "\n".join(lines) + "\n", 1


def _append_top_list(text: str, key: str, items: list[str]) -> tuple[str, int]:
    items = _clean_items(items)
    if not items:
        return text, 0
    lines = text.splitlines()
    key_idx = _find_top_key(lines, key)
    if key_idx < 0:
        lines.extend([f"{key}:"] + [f"  - {item}" for item in items])
        return "\n".join(lines) + "\n", len(items)
    block_end = _top_list_end(lines, key_idx)
    existing = _existing_list_items(lines[key_idx:block_end])
    new_items = [item for item in items if item not in existing]
    if not new_items:
        return text, 0
    if block_end == key_idx + 1 or lines[key_idx].strip().endswith("[]"):
        lines[key_idx] = f"{key}:"
        lines[key_idx + 1:key_idx + 1] = [f"  - {item}" for item in new_items]
    else:
        lines[block_end:block_end] = [f"  - {item}" for item in new_items]
    return "\n".join(lines) + "\n", len(new_items)


def _ensure_top_section(lines: list[str], section: str) -> int:
    idx = _find_top_key(lines, section)
    if idx >= 0:
        return idx
    if lines and lines[-1].strip():
        lines.append("")
    lines.append(f"{section}:")
    return len(lines) - 1


def _find_top_key(lines: list[str], key: str) -> int:
    pattern = re.compile(rf"^{re.escape(key)}\s*:")
    for idx, line in enumerate(lines):
        if pattern.match(line):
            return idx
    return -1


def _top_section_end(lines: list[str], start: int) -> int:
    for idx in range(start + 1, len(lines)):
        if lines[idx] and not lines[idx].startswith((" ", "-")) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*:", lines[idx]):
            return idx
    return len(lines)


def _find_nested_key(lines: list[str], section_idx: int, section_end: int, key: str) -> int:
    pattern = re.compile(rf"^  {re.escape(key)}\s*:")
    for idx in range(section_idx + 1, section_end):
        if pattern.match(lines[idx]):
            return idx
    return -1


def _nested_block_end(lines: list[str], key_idx: int) -> int:
    for idx in range(key_idx + 1, len(lines)):
        line = lines[idx]
        if line and not line.startswith(" "):
            return idx
        if re.match(r"^  [A-Za-z_][A-Za-z0-9_]*\s*:", line):
            return idx
    return len(lines)


def _top_list_end(lines: list[str], key_idx: int) -> int:
    for idx in range(key_idx + 1, len(lines)):
        line = lines[idx]
        if line and not line.startswith(" "):
            return idx
    return len(lines)


def _existing_list_items(lines: list[str]) -> set[str]:
    items = set()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("-"):
            items.add(stripped.lstrip("-").strip())
    return items


def _clean_items(items: list[str]) -> list[str]:
    seen = set()
    clean = []
    for item in items:
        value = str(item).strip()
        if not value or value == "无。":
            continue
        if value not in seen:
            seen.add(value)
            clean.append(value)
    return clean


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _safe_character_file(root: Path, patch: dict[str, Any]) -> Path:
    raw = str(patch.get("file") or "")
    if not raw:
        character_id = str(patch.get("character_id") or "")
        raw = f"characters/{character_id}.yaml"
    path = Path(raw)
    if path.is_absolute():
        resolved = path.resolve()
    else:
        resolved = (root / path).resolve()
    if not _is_relative_to(resolved, root / "characters"):
        raise RuntimeError(f"character file escapes characters directory: {resolved}")
    if not resolved.exists():
        raise FileNotFoundError(f"character file not found: {resolved}")
    return resolved


def _find_approval(root: Path, approval_run_id: str = "") -> dict[str, object] | None:
    index_path = root / "workflow" / "approvals" / "index.jsonl"
    if not index_path.exists():
        return None
    records = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("decision") != "approve":
            continue
        if approval_run_id and record.get("run_id") != approval_run_id:
            continue
        records.append(record)
    if not records:
        return None
    return records[-1]


def _resolve_patch(root: Path, patch: Path | None) -> Path:
    if patch is not None:
        return _resolve(root, patch)
    patches = sorted(
        (root / "characters" / "state_patches").glob("*_state_patch.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not patches:
        raise FileNotFoundError("no state patch json found")
    return patches[0]


def _render_report(manifest: dict[str, object]) -> str:
    lines = [
        f"# Character State Apply：{manifest['scene_id']}",
        "",
        f"- 状态：`{manifest['status']}`",
        f"- Patch：`{manifest['patch']}`",
        f"- 审批 run：`{manifest['approval'].get('run_id', '') or 'n/a'}`",
        f"- 写回项数：{manifest['update_count']}",
        "",
        "## 写回人物",
        "",
    ]
    for item in manifest["applied_characters"]:
        lines.append(f"- `{item['character_id']}` {item['name']}：`{item['file']}`，updates={item['updates']}，changed={str(item['changed']).lower()}")
    lines.extend(["", "## 边界", "", _md_list(list(manifest["guardrails"]))])
    return "\n".join(lines) + "\n"


def _md_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- 无。"


def _yaml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _resolve(root: Path, value: Path | None, default: Path | None = None) -> Path:
    if value is None:
        if default is None:
            raise ValueError("default path is required when value is None")
        return default
    return value if value.is_absolute() else root / value


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
