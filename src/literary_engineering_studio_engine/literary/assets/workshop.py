"""Listing and formally gated promotion of Agent-authored candidate assets."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.prompting.agents.schema import validate_payload
from .promotion import (
    commit_promotion,
    file_sha256,
    require_promotion_eligibility,
)
from .registry import (
    ASSET_CANDIDATE_DIRS,
    ASSET_SCHEMA_NAMES,
    ASSET_TYPES,
    PROMOTABLE_GROUPS,
)


@dataclass(frozen=True)
class AssetPromotionResult:
    project_root: Path
    candidate_path: Path
    manifest_path: Path
    report_path: Path
    output_paths: tuple[Path, ...]
    status: str


def list_asset_candidates(project_root: Path, asset_type: str = "") -> list[dict[str, object]]:
    root = project_root.resolve()
    selected = [_normalize_asset_type(asset_type)] if asset_type else list(ASSET_CANDIDATE_DIRS)
    items: list[dict[str, object]] = []
    seen: set[Path] = set()
    for item_type in selected:
        folder = root / ASSET_CANDIDATE_DIRS[item_type]
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.json")):
            if path in seen:
                continue
            seen.add(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            items.append(
                {
                    "asset_type": payload.get("asset_type", item_type),
                    "candidate_id": payload.get("candidate_id", path.stem),
                    "path": _rel_str(path, root),
                    "status": payload.get("candidate_status", ""),
                    "title": _candidate_title(payload),
                    "created_at": payload.get("created_at", ""),
                }
            )
    return items


def promote_candidate_asset(
    project_root: Path,
    candidate: str | Path,
    *,
    group: str = "",
    approval_run_id: str = "",
    allow_unapproved: bool = False,
) -> AssetPromotionResult:
    root = project_root.resolve()
    candidate_path = _resolve_candidate(root, candidate)
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    # Candidate filenames are allocated by the workflow.  Treat them, rather
    # than model-authored metadata, as the authority for promotion identity.
    inferred_type = _infer_type_from_path(root, candidate_path)
    asset_type = _normalize_asset_type(inferred_type or str(payload.get("asset_type") or ""))
    candidate_id = candidate_path.stem
    payload["asset_type"] = asset_type
    payload["candidate_id"] = candidate_id
    if group:
        _validate_group(group, asset_type)
    schema_name = ASSET_SCHEMA_NAMES[asset_type]
    errors, _warnings = validate_payload(payload, schema_name)
    if errors:
        raise ValueError(f"candidate schema validation failed: {len(errors)} errors")
    require_promotion_eligibility(
        root,
        candidate_path,
        asset_type=asset_type,
        approval_run_id=approval_run_id or candidate_id,
        allow_unapproved=allow_unapproved,
    )
    output_paths, manifest_path, report_path = commit_promotion(
        root,
        candidate_path,
        asset_type=asset_type,
        payload=payload,
        approval_run_id=approval_run_id or candidate_id,
        allow_unapproved=allow_unapproved,
        writer=_write_promoted_asset,
        report_renderer=_render_promotion,
        timestamp=_now,
    )
    return AssetPromotionResult(root, candidate_path, manifest_path, report_path, output_paths, "promoted")


def _normalize_asset_type(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "background": "background-story",
        "background_story": "background-story",
        "relationships": "relationship",
        "world-rules": "world",
        "chapter": "chapter-plan",
        "scenes": "scene-list",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in ASSET_SCHEMA_NAMES:
        raise ValueError(f"unknown asset type: {value}. valid: {', '.join(ASSET_TYPES)}")
    return normalized


def _write_promoted_asset(root: Path, asset_type: str, payload: dict[str, Any]) -> list[Path]:
    if asset_type == "character":
        character_id = _safe_id(str(payload.get("character_id") or "agent_character"))
        path = root / "characters" / f"{character_id}.yaml"
        path.write_text(_render_yaml(payload, exclude={"schema", "candidate_id", "asset_type", "agent_run_dir", "schema_validation", "candidate_status", "created_at", "risks", "source_paths", "promotion_notes"}), encoding="utf-8")
        return [path]
    if asset_type == "background-story":
        character_id = _safe_id(str(payload.get("target_character_id") or "agent_character"))
        path = root / "characters" / f"{character_id}.yaml"
        existing = path.read_text(encoding="utf-8") if path.exists() else f"character_id: {character_id}\nname: \"\"\nrole: \"\"\n"
        block = {
            "background_story": {
                "summary": payload.get("summary", ""),
                "formative_events": payload.get("formative_events", []),
                "hidden_wound": payload.get("hidden_wound", ""),
                "desire": payload.get("desire", ""),
                "fear": payload.get("fear", ""),
                "shame_or_secret": payload.get("shame_or_secret", ""),
                "behavior_influences": payload.get("behavior_influences", []),
                "reveal_policy": payload.get("reveal_policy", "implicit_only"),
            }
        }
        path.write_text(_replace_top_level_block(existing, "background_story", _render_yaml(block)), encoding="utf-8")
        return [path]
    if asset_type == "relationship":
        path = root / "plot" / "relationship_graph.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return [path]
    if asset_type == "world":
        path = root / "canon" / "world_rules.yaml"
        promoted = {
            "world_name": payload.get("world_name", ""),
            "rules": _literary_world_entries(payload.get("core_rules")),
            "constraints": _literary_world_entries(payload.get("constraints")),
            "power_sources": payload.get("power_sources", []),
            "social_order": payload.get("social_order", []),
            "taboos": payload.get("taboos", []),
            "history_pressure": payload.get("history_pressure", []),
            "open_questions": payload.get("open_questions", []),
        }
        path.write_text(_render_yaml(promoted), encoding="utf-8")
        return [path]
    if asset_type == "location":
        path = root / "canon" / "locations.yaml"
        path.write_text(_render_yaml({"locations": [_public_payload(payload)]}), encoding="utf-8")
        return [path]
    if asset_type == "organization":
        path = root / "canon" / "organizations.yaml"
        path.write_text(_render_yaml({"organizations": [_public_payload(payload)]}), encoding="utf-8")
        return [path]
    path = root / "plot" / "outline.md"
    path.write_text(_render_outline(payload), encoding="utf-8")
    outputs = [path]
    for scene in payload.get("scene_list", []) or []:
        if not isinstance(scene, dict):
            continue
        scene_id = _safe_id(str(scene.get("scene_id") or "scene_candidate"))
        scene_path = root / "scenes" / f"{scene_id}.yaml"
        scene_payload = {
            "scene_id": scene_id,
            "chapter_id": scene.get("chapter_id", "chapter_0001"),
            "location": scene.get("location", ""),
            "participants": scene.get("participants", []),
            "scene_goal": scene.get("goal", ""),
            "conflict": scene.get("conflict", ""),
            "input_state": [],
            "output_state": [],
            "review": {"status": "planned"},
        }
        scene_path.write_text(_render_yaml(scene_payload), encoding="utf-8")
        outputs.append(scene_path)
    return outputs


def _public_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"schema", "candidate_id", "asset_type", "agent_run_dir", "schema_validation", "candidate_status", "created_at", "risks", "source_paths", "promotion_notes"}
    }


def _literary_world_entries(value: Any) -> list[Any]:
    values = value if isinstance(value, list) else []
    return [item for item in values if not _world_workflow_metadata(item)]


def _world_workflow_metadata(value: Any) -> bool:
    if isinstance(value, dict):
        entry_id = str(value.get("id") or "").strip().casefold()
        if entry_id in {"candidate_not_confirmed", "candidate-status", "promotion-status"}:
            return True
    text = json.dumps(value, ensure_ascii=False).casefold()
    signatures = (
        "本候选资产",
        "写入正式 canon 前",
        "未经 schema 审查",
        "candidate_status",
        "ready_for_review",
    )
    return any(signature.casefold() in text for signature in signatures)


def _render_yaml(data: dict[str, Any], indent: int = 0, exclude: set[str] | None = None) -> str:
    lines: list[str] = []
    excluded = exclude or set()
    for key, value in data.items():
        if key in excluded:
            continue
        prefix = " " * indent
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_render_yaml(value, indent + 2).rstrip())
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            if not value:
                lines[-1] += " []"
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{prefix}  -")
                    lines.append(_render_yaml(item, indent + 4).rstrip())
                else:
                    lines.append(f"{prefix}  - {_yaml_scalar(item)}")
        else:
            lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")
    return "\n".join(lines).rstrip() + "\n"


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _replace_top_level_block(existing: str, key: str, rendered_block: str) -> str:
    lines = existing.splitlines()
    output: list[str] = []
    index = 0
    replaced = False
    while index < len(lines):
        line = lines[index]
        if line.startswith(f"{key}:"):
            output.extend(rendered_block.rstrip().splitlines())
            replaced = True
            index += 1
            while index < len(lines) and (lines[index].startswith(" ") or not lines[index].strip()):
                index += 1
            continue
        output.append(line)
        index += 1
    if not replaced:
        if output and output[-1].strip():
            output.append("")
        output.extend(rendered_block.rstrip().splitlines())
    return "\n".join(output).rstrip() + "\n"


def _render_outline(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload.get('title', '候选大纲')}",
        "",
        "## Premise",
        "",
        str(payload.get("premise", "")),
        "",
        "## Central Conflict",
        "",
        str(payload.get("central_conflict", "")),
        "",
        "## Acts",
        "",
    ]
    for item in payload.get("acts", []) or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Chapters", ""])
    for item in payload.get("chapters", []) or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Scene List", ""])
    for item in payload.get("scene_list", []) or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Foreshadowing", ""])
    for item in payload.get("foreshadowing", []) or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def _render_promotion(data: dict[str, Any]) -> str:
    lines = [
        f"# Candidate Asset Promotion：{data.get('candidate_id', '')}",
        "",
        f"- Type：`{data.get('asset_type', '')}`",
        f"- Status：`{data.get('status', '')}`",
        f"- Approval Run：`{data.get('approval_run_id', '')}`",
        f"- Allow Unapproved：`{str(data.get('allow_unapproved', '')).lower()}`",
        "",
        "## Outputs",
        "",
    ]
    for item in data.get("outputs", []) or []:
        lines.append(f"- `{item}`")
    return "\n".join(lines) + "\n"


def _resolve_candidate(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.exists():
        return path.resolve()
    if not path.is_absolute():
        direct = (root / path).resolve()
        if direct.exists():
            return direct
    candidate_id = str(value)
    for folder in ASSET_CANDIDATE_DIRS.values():
        candidate = root / folder / f"{candidate_id}.json"
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(f"candidate asset not found: {value}")


def _infer_type_from_path(root: Path, path: Path) -> str:
    rel = _rel_str(path, root)
    for asset_type, folder in ASSET_CANDIDATE_DIRS.items():
        if rel.startswith(folder.as_posix()):
            return asset_type
    return "character"


def _validate_group(group: str, asset_type: str) -> None:
    normalized = group.strip().lower()
    if normalized not in PROMOTABLE_GROUPS:
        raise ValueError(f"unknown promotion group: {group}")
    if asset_type not in PROMOTABLE_GROUPS[normalized]:
        raise ValueError(f"{asset_type} cannot be promoted through {group} group")


def _candidate_title(payload: dict[str, Any]) -> str:
    return str(
        payload.get("name")
        or payload.get("title")
        or payload.get("world_name")
        or payload.get("summary")
        or payload.get("candidate_id")
        or "candidate asset"
    )


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", value.strip()).strip("_")
    return cleaned or "asset"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
