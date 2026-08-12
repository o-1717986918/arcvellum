"""Apply approved character state patches to character YAML files."""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, MutableMapping

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import YAMLError

from ....atomic_io import atomic_write_batch
from ....agent_tasks import agent_task_completion_status
from ....semantic_task_contracts import semantic_artifact_errors
from .writeback_source import has_state_changes, structured_scene_writeback


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

    semantic_errors = semantic_artifact_errors(root, "state-agent-task", scene_id)
    completion = agent_task_completion_status(patch_path.with_suffix(".agent_tasks.md"), root=root)
    if (semantic_errors or completion.get("complete") is not True) and not allow_unapproved:
        details = list(semantic_errors[:4])
        if completion.get("complete") is not True:
            details.append(f"state sidecar incomplete: {completion.get('message')}")
        raise RuntimeError("state-apply requires a completed passing state semantic review: " + "; ".join(details))

    patch_sha256 = hashlib.sha256(patch_path.read_bytes()).hexdigest()
    approval_id = approval_run_id.strip() or patch_path.stem
    approval = _find_approval(root, approval_id)
    approval_matches = _approval_matches_patch(approval, patch_sha256)
    if (approval is None or not approval_matches) and not allow_unapproved:
        detail = "missing" if approval is None else "does not match the exact state patch digest"
        raise RuntimeError(f"state-apply requires an approve record bound to {patch_path.stem}; approval is {detail}")

    applied: list[dict[str, object]] = []
    pending_writes: dict[Path, str] = {}
    total_updates = 0
    for item in payload.get("characters", []):
        if not isinstance(item, dict):
            continue
        character_file = _safe_character_file(root, item)
        original = _read(character_file)
        updated, update_count = _apply_one_character(original, item, patch_path, root)
        if updated != original:
            pending_writes[character_file] = updated
        total_updates += update_count
        applied.append(
            {
                "character_id": item.get("character_id", ""),
                "name": item.get("name", ""),
                "file": _rel(character_file, root),
                "updates": update_count,
                "changed": updated != original,
                "before_sha256": _sha256_text(original),
                "after_sha256": _sha256_text(updated),
            }
        )

    status = "applied" if approval is not None and approval_matches else "applied_internal"
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
        "approval_run_id": approval_id,
        "approval": approval or {"decision": "allow_unapproved", "run_id": "", "notes": ""},
        "approval_matches_patch": approval_matches,
        "patch_sha256": patch_sha256,
        "semantic_review": {
            "path": f"characters/state_patches/{scene_id}_state_patch_review.json",
            "status": "pass" if not semantic_errors else "missing_or_failed",
            "errors": semantic_errors,
            "completion": completion,
        },
        "allow_unresolved": allow_unresolved,
        "applied_characters": applied,
        "update_count": total_updates,
        "guardrails": [
            "只写回人物档案中的 state、arc、state.relationship_changes 和 memory_refs。",
            "不写 canon/facts.json，不确认世界观事实。",
            "重复执行时会尽量去重已有列表项。",
        ],
    }
    pending_writes[manifest_path] = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    pending_writes[report_path] = _render_report(manifest)
    atomic_write_batch(pending_writes)
    return CharacterStateApplyResult(
        project_root=root,
        patch_path=patch_path,
        manifest_path=manifest_path,
        report_path=report_path,
        scene_id=scene_id,
        applied_character_count=len(applied),
        update_count=total_updates,
        approval_run_id=approval_id if approval_matches else "",
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

    document = _load_character_yaml(text)
    state = _ensure_mapping(document, "state")
    arc = _ensure_mapping(document, "arc")
    count = _migrate_legacy_relationship_events(document, state)
    count += _extend_unique(state, "known_facts", _string_list(state_updates.get("known_facts_add")))
    count += _extend_unique(state, "resources", _string_list(state_updates.get("resources_add")))
    count += _set_scalar(state, "location", str(state_updates.get("location_note") or ""))
    count += _set_scalar(state, "health", str(state_updates.get("health_note") or ""))
    count += _extend_unique(arc, "required_trigger_events", _string_list(arc_updates.get("candidate_changes")))

    # Relationship definitions are structured records.  Narrative deltas from
    # a state patch belong in a separate event ledger; appending strings to the
    # formal relationships list corrupts the character document shape.
    count += _extend_unique(
        state,
        "relationship_changes",
        _string_list(relationship_updates.get("candidate_changes")),
    )
    count += _extend_unique(document, "memory_refs", [f"state_patch:{_rel(patch_path, root)}"])
    return _dump_character_yaml(document), count


def _migrate_legacy_relationship_events(
    document: MutableMapping[str, Any],
    state: MutableMapping[str, Any],
) -> int:
    """Move scalar relationship deltas written by older releases out of definitions."""

    relationships = document.get("relationships")
    if relationships is None:
        return 0
    if not isinstance(relationships, list):
        raise RuntimeError("character field `relationships` must be a list")
    legacy_events = [str(item).strip() for item in relationships if isinstance(item, str) and str(item).strip()]
    if not legacy_events:
        return 0
    relationships[:] = [item for item in relationships if not isinstance(item, str)]
    _extend_unique(state, "relationship_changes", legacy_events)
    return len(legacy_events)


def _load_character_yaml(text: str) -> MutableMapping[str, Any]:
    try:
        document = _yaml().load(text) or CommentedMap()
    except YAMLError as exc:
        raise RuntimeError(f"character file is not valid YAML: {exc}") from exc
    if not isinstance(document, MutableMapping):
        raise RuntimeError("character file root must be a YAML mapping")
    return document


def _dump_character_yaml(document: MutableMapping[str, Any]) -> str:
    stream = StringIO()
    _yaml().dump(document, stream)
    return stream.getvalue()


def _yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    yaml.width = 4096
    return yaml


def _ensure_mapping(parent: MutableMapping[str, Any], key: str) -> MutableMapping[str, Any]:
    value = parent.get(key)
    if value is None:
        value = CommentedMap()
        parent[key] = value
    if not isinstance(value, MutableMapping):
        raise RuntimeError(f"character field `{key}` must be a mapping")
    return value


def _extend_unique(parent: MutableMapping[str, Any], key: str, items: list[str]) -> int:
    items = _clean_items(items)
    if not items:
        return 0
    value = parent.get(key)
    if value is None:
        value = CommentedSeq()
        parent[key] = value
    if not isinstance(value, list):
        raise RuntimeError(f"character field `{key}` must be a list")
    existing = {str(item).strip() for item in value if isinstance(item, str)}
    additions = [item for item in items if item not in existing]
    value.extend(additions)
    return len(additions)


def _set_scalar(parent: MutableMapping[str, Any], key: str, value: str) -> int:
    value = value.strip()
    if not value or parent.get(key) == value:
        return 0
    parent[key] = value
    return 1


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


def _approval_matches_patch(approval: dict[str, object] | None, patch_sha256: str) -> bool:
    if not approval or not patch_sha256:
        return False
    return str(approval.get("decision") or "") == "approve" and str(approval.get("subject_sha256") or "").strip().lower() == patch_sha256.lower()


def state_patch_writeback_status(root: Path, scene_id: str) -> dict[str, object]:
    """Describe the decision-to-apply status for a scene state patch."""

    patch = root / "characters" / "state_patches" / f"{scene_id}_state_patch.json"
    apply_manifest = root / "characters" / "state_patches" / f"{scene_id}_state_apply.json"
    result: dict[str, object] = {
        "scene_id": scene_id,
        "patch": _rel(patch, root),
        "apply_manifest": _rel(apply_manifest, root),
        "status": "missing",
        "message": "state patch is missing",
    }
    if not patch.is_file():
        return result
    try:
        payload = json.loads(patch.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        result.update({"status": "invalid", "message": "state patch JSON is invalid"})
        return result
    characters = payload.get("characters") if isinstance(payload.get("characters"), list) else []
    unresolved = payload.get("unresolved_changes") if isinstance(payload.get("unresolved_changes"), list) else []
    expected_changes, expected_source = structured_scene_writeback(root, scene_id)
    if has_state_changes(expected_changes) and not characters and not unresolved:
        result.update({
            "status": "stale_source",
            "message": (
                "state patch omitted structured character or relationship changes from "
                f"{expected_source}; rerun state-evolve"
            ),
        })
        return result
    if unresolved and not characters:
        result.update({
            "status": "semantic_incomplete",
            "message": "state patch has unresolved character or relationship changes",
        })
        return result
    if not characters:
        result.update({"status": "not_required", "message": "state patch contains no durable character changes"})
        return result
    semantic_errors = semantic_artifact_errors(root, "state-agent-task", scene_id)
    completion = agent_task_completion_status(patch.with_suffix(".agent_tasks.md"), root=root)
    if semantic_errors or completion.get("complete") is not True:
        details = list(semantic_errors[:4])
        if completion.get("complete") is not True:
            details.append(f"state sidecar incomplete: {completion.get('message')}")
        result.update({"status": "semantic_incomplete", "message": "; ".join(details)})
        return result
    patch_sha256 = hashlib.sha256(patch.read_bytes()).hexdigest()
    approval_id = patch.stem
    approval = _find_approval(root, approval_id)
    if not _approval_matches_patch(approval, patch_sha256):
        result.update({
            "status": "needs_approval",
            "message": "state patch needs an approve record bound to its exact digest",
            "approval_run_id": approval_id,
            "candidate_sha256": patch_sha256,
        })
        return result
    if apply_manifest.is_file():
        try:
            applied = json.loads(apply_manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            applied = {}
        if str(applied.get("patch_sha256") or "").lower() == patch_sha256 and str(applied.get("status") or "") == "applied":
            result.update({"status": "pass", "message": "approved state patch is applied", "approval_run_id": approval_id, "candidate_sha256": patch_sha256})
            return result
    result.update({"status": "pending_apply", "message": "approved state patch is ready for state-apply", "approval_run_id": approval_id, "candidate_sha256": patch_sha256})
    return result


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


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
