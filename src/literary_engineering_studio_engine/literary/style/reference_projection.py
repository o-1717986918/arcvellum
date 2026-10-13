"""Deterministic, version-bound reference selection for prose generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from literary_engineering_studio_engine.foundation.resources import engine_root
from .snapshot import active_style_mount_snapshot_payload, active_style_prompt_path


REFERENCE_INDEX_SCHEMA = "arcvellum/style-reference-index/v1"
SELECTOR_VERSION = "scene-reference-selector/2"
_DEFAULT_META = engine_root() / "templates/style/default-clear-plain/reference-metadata.json"


def build_reference_index(profile_text: str, corpus_text: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Pin every complete corpus block to its exact span in the mounted profile."""

    blocks = [block.strip() for block in re.split(r"\n\s*\n", corpus_text.strip()) if block.strip()]
    definitions = metadata.get("units")
    if not isinstance(definitions, list) or len(definitions) != len(blocks):
        raise ValueError("reference metadata must cover every complete corpus unit")
    units: list[dict[str, Any]] = []
    cursor = 0
    for position, (definition, block) in enumerate(zip(definitions, blocks), 1):
        if not isinstance(definition, dict) or definition.get("unit_id") != f"R{position:02d}":
            raise ValueError("reference metadata units must preserve R01... order")
        start = profile_text.find(block, cursor)
        if start < 0:
            raise ValueError(f"reference unit R{position:02d} is missing from style profile")
        end = start + len(block)
        units.append({
            "unit_id": definition["unit_id"],
            "source_digest": hashlib.sha256(block.encode("utf-8")).hexdigest(),
            "span": {"start": start, "end": end},
            "match_terms": list(definition.get("match_terms") or []),
            "technique_axes": list(definition.get("technique_axes") or []),
            **{key: definition.get(key) for key in ("narrative_modes", "voice", "register", "time_scale", "source_kind", "source_title", "source_url")},
        })
        cursor = end
    return {
        "schema": REFERENCE_INDEX_SCHEMA,
        "profile_sha256": hashlib.sha256(profile_text.encode("utf-8")).hexdigest(),
        "units": units,
    }


def build_default_reference_index(profile_text: str, corpus_text: str) -> dict[str, Any]:
    metadata = json.loads(_DEFAULT_META.read_text(encoding="utf-8"))
    index = build_reference_index(profile_text, corpus_text, metadata)
    source = _DEFAULT_META.parent / "literary-references.json"
    for row in json.loads(source.read_text(encoding="utf-8"))["units"]:
        start = profile_text.find(row["text"])
        if start < 0:
            raise ValueError("supplementary literary reference missing from profile")
        index["units"].append({**{key: value for key, value in row.items() if key != "text"},
                               "span": {"start": start, "end": start + len(row["text"])}})
    return index


def active_style_reference_catalog(project_root: Path) -> dict[str, Any]:
    """Read all full, digest-verified references for creator-directed selection."""
    prompt = active_style_prompt_path(project_root)
    snapshot = active_style_mount_snapshot_payload(project_root)
    if prompt is None or not (prompt.parent / "reference-index.json").is_file():
        return {"schema": "arcvellum/style-reference-catalog/v1", "style_mount_snapshot": snapshot, "references": []}
    profile = (prompt.parent / "style-profile.md").read_text(encoding="utf-8")
    index = json.loads((prompt.parent / "reference-index.json").read_text(encoding="utf-8"))
    validate_reference_index(profile, index)
    return {"schema": "arcvellum/style-reference-catalog/v1", "style_mount_snapshot": snapshot,
            "references": [_validated_unit(row, profile) for row in index["units"]]}


def validate_reference_index(profile: str, index: dict[str, Any]) -> None:
    if index.get("schema") != REFERENCE_INDEX_SCHEMA or hashlib.sha256(profile.encode("utf-8")).hexdigest() != index.get("profile_sha256"):
        raise ValueError("style reference index does not match its profile")
    units = index.get("units")
    if not isinstance(units, list) or not units:
        raise ValueError("style reference index has no units")
    ids: set[str] = set()
    for row in units:
        if not isinstance(row, dict) or not isinstance(row.get("unit_id"), str) or row["unit_id"] in ids:
            raise ValueError("style reference index contains duplicate or invalid unit IDs")
        ids.add(row["unit_id"])
        if not isinstance(row.get("match_terms"), list) or not isinstance(row.get("technique_axes"), list):
            raise ValueError("style reference index lacks unit metadata")
        _validated_unit(row, profile)


def recent_formal_reference_ids(project_root: Path, *, exclude_scene_id: str = "") -> tuple[str, ...]:
    """Read only successful formal prompt manifests from recent, distinct scenes."""

    candidates = project_root / "drafts" / "candidates"
    if not candidates.is_dir():
        return ()
    current_mount = active_style_mount_snapshot_payload(project_root)
    paths = sorted(candidates.glob("*.prompt.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    seen = {exclude_scene_id} if exclude_scene_id else set()
    recent: list[str] = []
    for path in paths[:40]:
        if path.stat().st_size > 2_000_000:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        scene_id = Path(str(payload.get("scene") or "")).stem
        if not scene_id or scene_id in seen or payload.get("style_mount_snapshot") != current_mount:
            continue
        seen.add(scene_id)
        selection = payload.get("style_reference_selection") or {}
        if selection.get("status") != "selected":
            continue
        recent.extend(str(row["unit_id"]) for row in selection.get("references", []) if row.get("unit_id"))
        if len(seen) >= 4 + bool(exclude_scene_id):
            break
    return tuple(recent)


def select_active_style_references(
    project_root: Path,
    scene_text: str,
    *,
    recent_unit_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Return one full primary excerpt and, only when useful, a second one."""

    prompt = active_style_prompt_path(project_root)
    snapshot = active_style_mount_snapshot_payload(project_root)
    if prompt is None:
        return {"status": "no-active-style", "selector_version": SELECTOR_VERSION, "references": []}
    index_path = prompt.parent / "reference-index.json"
    profile_path = prompt.parent / "style-profile.md"
    if not index_path.is_file() or not profile_path.is_file():
        return {"status": "legacy-unindexed", "selector_version": SELECTOR_VERSION, "style_mount_snapshot": snapshot, "references": []}
    index = json.loads(index_path.read_text(encoding="utf-8"))
    profile = profile_path.read_text(encoding="utf-8")
    validate_reference_index(profile, index)
    ranked = _ranked_units(index, profile, scene_text, recent_unit_ids)
    if not ranked:
        return {"status": "legacy-unindexed", "selector_version": SELECTOR_VERSION, "style_mount_snapshot": snapshot, "references": []}
    ranked.sort(key=lambda item: (-item[0], item[1]))
    primary = ranked[0]
    if primary[0] <= 0:
        return {
            "status": "no-scene-match",
            "selector_version": SELECTOR_VERSION,
            "style_mount_snapshot": snapshot,
            "references": [],
        }
    selected = [primary, *_supplementary_unit(primary, ranked[1:])]
    references = [
        {
            "role": "primary" if offset == 0 else "secondary",
            "unit_id": item[2]["unit_id"],
            "source_digest": item[2]["source_digest"],
            "technique_axes": item[2]["technique_axes"],
            "match_terms": item[3],
            "text": item[2]["text"],
        }
        for offset, item in enumerate(selected)
    ]
    selection = {
        "status": "selected",
        "selector_version": SELECTOR_VERSION,
        "style_mount_snapshot": snapshot,
        "references": references,
        "equal_primary_ids": [item[2]["unit_id"] for item in ranked if item[0] == primary[0]],
        "selection_note": "按作品审美与当前文学任务匹配；参考由主创自由取舍，同分表示同等相关。",
    }
    selection["digest"] = hashlib.sha256(json.dumps(selection, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return selection


def render_style_reference_selection(selection: dict[str, Any]) -> str:
    if selection.get("status") != "selected":
        return "依据作者意图与当前文学任务发展本段的语言。"
    lines = ["完整阅读以下参照，结合本段文学任务选择叙述声音、感知位置和时间尺度，发展当前作品自己的表达。"]
    for row in selection["references"]:
        label = "主参考" if row["role"] == "primary" else "辅参考"
        if row["unit_id"] in selection.get("equal_primary_ids", []) and len(selection.get("equal_primary_ids", [])) > 1:
            label = "同等相关参考（自主取舍）"
        lines.extend([
            f"### {label} {row['unit_id']}",
            f"技法轴：{'、'.join(row['technique_axes'])}。命中场景线索：{'、'.join(row['match_terms']) or '通用场景基底'}。",
            row["text"],
        ])
    return "\n\n".join(lines)


def _ranked_units(
    index: dict[str, Any], profile: str, scene_text: str, recent_unit_ids: tuple[str, ...],
) -> list[tuple[int, str, dict[str, Any], list[str]]]:
    recent = set(recent_unit_ids[-4:])
    try:
        context = json.loads(scene_text)
    except (ValueError, TypeError):
        context = {}
    aesthetic = json.dumps(context.get("aesthetic_context", {}), ensure_ascii=False) if isinstance(context, dict) else ""
    ranked = []
    for row in index.get("units", []):
        unit = _validated_unit(row, profile)
        hits = [term for term in unit["match_terms"] if term in scene_text]
        aesthetic_hits = [term for term in unit["match_terms"] if term in aesthetic]
        score = len(hits) * 4 + len(aesthetic_hits) * 6 - (2 if unit["unit_id"] in recent else 0)
        ranked.append((score, unit["unit_id"], unit, hits))
    return ranked


def _supplementary_unit(
    primary: tuple[int, str, dict[str, Any], list[str]],
    candidates: list[tuple[int, str, dict[str, Any], list[str]]],
) -> list[tuple[int, str, dict[str, Any], list[str]]]:
    for candidate in candidates:
        if candidate[0] >= max(4, primary[0] - 1) and set(candidate[2]["technique_axes"]).isdisjoint(primary[2]["technique_axes"]):
            return [candidate]
    return []


def _validated_unit(row: dict[str, Any], profile: str) -> dict[str, Any]:
    span = row.get("span") if isinstance(row.get("span"), dict) else {}
    start, end = span.get("start"), span.get("end")
    if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(profile):
        raise ValueError("invalid style reference span")
    text = profile[start:end]
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != row.get("source_digest"):
        raise ValueError("style reference digest mismatch")
    return {**row, "text": text}


__all__ = ["active_style_reference_catalog", "REFERENCE_INDEX_SCHEMA", "build_default_reference_index", "build_reference_index", "validate_reference_index", "recent_formal_reference_ids", "select_active_style_references", "render_style_reference_selection"]
