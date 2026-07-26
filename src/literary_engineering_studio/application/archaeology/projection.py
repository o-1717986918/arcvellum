"""Path-safe read models for Project Archaeology progress and evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.agent_tasks import (
    agent_task_completion_status,
)
from literary_engineering_studio_engine.literary.ingest import reconstruction_paths
from literary_engineering_studio_engine.workflow_state import build_workflow_state

from .contracts import MODE_PRESENTATION


def project_archaeology_catalog(project_root: Path) -> dict[str, object]:
    root = project_root.resolve()
    states = _workflow_states(root)
    items = [
        _catalog_item(root, import_dir, states.get(import_dir.name, {}))
        for import_dir in _import_dirs(root)
    ]
    return {
        "schema": "arcvellum/project-archaeology-catalog/v1",
        "count": len(items),
        "imports": items,
        "recovery": _recovery_projection(root),
        "revision": _digest(items),
    }


def project_archaeology_workbench(
    project_root: Path,
    work_id: str,
) -> dict[str, object]:
    root = project_root.resolve()
    import_dir = _safe_import_dir(root, work_id)
    manifest = _read_json(import_dir / "source_manifest.json")
    if not manifest:
        raise FileNotFoundError(f"Project Archaeology import not found: {work_id}")
    state = _workflow_states(root).get(work_id, {})
    paths = reconstruction_paths(import_dir.relative_to(root))
    aggregate = _read_relative(root, _aggregate_path(manifest))
    resolution = _read_relative(root, paths["resolution"])
    reconstruction = _read_relative(root, paths["candidate"])
    review = _read_relative(root, paths["review"])
    materialization = _read_relative(root, paths["materialization"])
    payload = {
        "schema": "arcvellum/project-archaeology-workbench/v1",
        "work_id": work_id,
        "title": str(manifest.get("title") or work_id),
        "mode": _mode_projection(str(manifest.get("mode") or "")),
        "status": _state_projection(state),
        "journey": _journey(import_dir, manifest, state, paths),
        "sources": _source_projection(manifest),
        "segmentation": _segmentation_projection(manifest),
        "entities": _entity_projection(aggregate, resolution),
        "conflicts": _conflict_projection(aggregate, resolution),
        "reconstruction": _reconstruction_projection(reconstruction, review),
        "promotion_queue": _promotion_projection(materialization),
        "evidence": _evidence_projection(manifest, aggregate),
        "recovery": _import_recovery_projection(root, work_id),
    }
    payload["revision"] = _digest(payload)
    return payload


def _catalog_item(
    root: Path,
    import_dir: Path,
    state: dict[str, object],
) -> dict[str, object]:
    manifest = _read_json(import_dir / "source_manifest.json")
    return {
        "work_id": import_dir.name,
        "title": str(manifest.get("title") or import_dir.name),
        "mode": _mode_projection(str(manifest.get("mode") or "")),
        "source_count": int(manifest.get("source_count") or 0),
        "chunk_count": len(manifest.get("chunks") or []),
        "status": _state_projection(state),
        "recovery": _import_recovery_projection(root, import_dir.name),
    }


def _journey(
    import_dir: Path,
    manifest: dict[str, object],
    state: dict[str, object],
    paths: dict[str, str],
) -> list[dict[str, object]]:
    root = import_dir.parents[2]
    archaeology = manifest.get("archaeology")
    chunk_tasks = (
        archaeology.get("chunk_tasks")
        if isinstance(archaeology, dict)
        else []
    )
    chunks_complete = sum(
        1
        for item in chunk_tasks or []
        if isinstance(item, dict)
        and agent_task_completion_status(
            root / str(item.get("task_path") or ""),
            root=root,
        ).get("complete") is True
    )
    stages = [
        ("source", "源文本保全", bool(manifest), int(manifest.get("source_count") or 0)),
        ("segments", "结构分割", bool(manifest.get("chunks")), len(manifest.get("chunks") or [])),
        ("chunks", "分块理解", bool(chunk_tasks) and chunks_complete == len(chunk_tasks), chunks_complete),
        ("identity", "人物与别名", (root / paths["resolution"]).is_file(), 0),
        ("reconstruction", "项目重建", (root / paths["candidate"]).is_file(), 0),
        ("review", "分领域审查", (root / paths["review"]).is_file(), 0),
        ("archive", "候选入档", (root / paths["materialization"]).is_file(), 0),
    ]
    current = str(state.get("current_step") or "")
    return [
        {
            "id": stage_id,
            "label": label,
            "status": "complete" if complete else "active" if _stage_is_active(stage_id, current) else "waiting",
            "count": count,
        }
        for stage_id, label, complete, count in stages
    ]


def _source_projection(manifest: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "source_id": str(item.get("source_id") or ""),
            "title": str(item.get("title") or item.get("filename") or ""),
            "filename": str(item.get("original_filename") or ""),
            "media_type": str(item.get("media_type") or ""),
            "extraction_method": str(item.get("extraction_method") or ""),
            "content_sha256": str(item.get("content_hash") or ""),
            "character_count": int(item.get("character_count") or item.get("char_count") or 0),
        }
        for item in manifest.get("source_documents") or []
        if isinstance(item, dict)
    ]


def _segmentation_projection(manifest: dict[str, object]) -> dict[str, object]:
    chunks = [item for item in manifest.get("chunks") or [] if isinstance(item, dict)]
    segments = [item for item in manifest.get("segments") or [] if isinstance(item, dict)]
    return {
        "segment_count": len(segments),
        "chunk_count": len(chunks),
        "chunks": [
            {
                "chunk_id": str(item.get("chunk_id") or ""),
                "title": str(item.get("title") or item.get("label") or ""),
                "kind": str(item.get("kind") or ""),
                "evidence_count": len(item.get("evidence_refs") or []),
            }
            for item in chunks
        ],
    }


def _entity_projection(
    aggregate: dict[str, object],
    resolution: dict[str, object],
) -> dict[str, object]:
    occurrences = [
        item for item in aggregate.get("entity_occurrences") or [] if isinstance(item, dict)
    ]
    groups = [
        item for item in resolution.get("entity_groups") or [] if isinstance(item, dict)
    ]
    return {
        "occurrence_count": len(occurrences),
        "resolved_count": len(groups),
        "groups": [_entity_group_projection(item) for item in groups],
    }


def _entity_group_projection(item: dict[str, object]) -> dict[str, object]:
    return {
        "entity_id": str(item.get("entity_id") or ""),
        "display_name": str(item.get("display_name") or item.get("entity_id") or ""),
        "entity_type": str(item.get("entity_type") or ""),
        "aliases": list(item.get("aliases") or []),
        "resolution": str(item.get("resolution") or ""),
        "confidence": item.get("confidence"),
        "unknowns": list(item.get("unknowns") or []),
        "occurrence_count": len(item.get("occurrence_refs") or []),
    }


def _conflict_projection(
    aggregate: dict[str, object],
    resolution: dict[str, object],
) -> dict[str, object]:
    conflicts = [
        item for item in aggregate.get("conflicts") or [] if isinstance(item, dict)
    ]
    reviews = {
        int(item["conflict_index"]): item
        for item in resolution.get("conflict_reviews") or []
        if isinstance(item, dict) and isinstance(item.get("conflict_index"), int)
    }
    return {
        "count": len(conflicts),
        "unresolved_count": sum(1 for index in range(len(conflicts)) if _conflict_is_open(reviews, index)),
        "items": [
            _conflict_item_projection(item, index=index, review=reviews.get(index, {}))
            for index, item in enumerate(conflicts)
        ],
    }


def _conflict_is_open(
    reviews: dict[int, dict[str, object]],
    index: int,
) -> bool:
    return str(reviews.get(index, {}).get("disposition") or "") not in {
        "resolved",
        "not_applicable",
    }


def _conflict_item_projection(
    item: dict[str, object],
    *,
    index: int,
    review: dict[str, object],
) -> dict[str, object]:
    return {
        "index": index,
        "kind": str(item.get("kind") or item.get("conflict_type") or ""),
        "summary": str(item.get("summary") or item.get("message") or ""),
        "evidence_refs": list(item.get("evidence_refs") or []),
        "disposition": str(review.get("disposition") or "unreviewed"),
        "rationale": str(review.get("rationale") or ""),
    }


def _reconstruction_projection(
    reconstruction: dict[str, object],
    review: dict[str, object],
) -> dict[str, object]:
    decisions = {
        str(item.get("candidate_id") or ""): item
        for item in review.get("asset_decisions") or []
        if isinstance(item, dict)
    }
    domains = [
        item for item in review.get("domain_reviews") or [] if isinstance(item, dict)
    ]
    assets = [
        item for item in reconstruction.get("assets") or [] if isinstance(item, dict)
    ]
    return {
        "summary": dict(reconstruction.get("project_summary") or {}),
        "status": str(review.get("status") or "waiting"),
        "domains": [_domain_projection(item) for item in domains],
        "assets": [
            _reconstructed_asset_projection(item, decisions=decisions)
            for item in assets
        ],
    }


def _domain_projection(item: dict[str, object]) -> dict[str, object]:
    return {
        "domain": str(item.get("domain") or ""),
        "status": str(item.get("status") or ""),
        "blockers": list(item.get("blocking_issues") or []),
        "warnings": list(item.get("warnings") or []),
    }


def _reconstructed_asset_projection(
    item: dict[str, object],
    *,
    decisions: dict[str, dict[str, object]],
) -> dict[str, object]:
    candidate_id = str(item.get("candidate_id") or "")
    return {
        "candidate_id": candidate_id,
        "asset_type": str(item.get("asset_type") or ""),
        "confidence": item.get("confidence"),
        "recommendation": str(item.get("promotion_recommendation") or ""),
        "decision": str(decisions.get(candidate_id, {}).get("decision") or ""),
        "evidence_count": len(item.get("evidence_refs") or []),
        "unresolved_count": len(item.get("unresolved_refs") or []),
    }


def _promotion_projection(materialization: dict[str, object]) -> dict[str, object]:
    materialized = [
        item for item in materialization.get("materialized_assets") or [] if isinstance(item, dict)
    ]
    deferred = [
        item for item in materialization.get("deferred_assets") or [] if isinstance(item, dict)
    ]
    return {
        "status": str(materialization.get("status") or "waiting"),
        "ready_count": len(materialized),
        "deferred_count": len(deferred),
        "items": [
            {
                "candidate_id": str(item.get("candidate_id") or ""),
                "asset_type": str(item.get("asset_type") or ""),
                "status": "awaiting_archive_review",
            }
            for item in materialized
        ],
    }


def _evidence_projection(
    manifest: dict[str, object],
    aggregate: dict[str, object],
) -> dict[str, object]:
    evidence = manifest.get("evidence_index")
    evidence = evidence if isinstance(evidence, dict) else {}
    collections = (
        "entity_occurrences",
        "event_occurrences",
        "relation_occurrences",
        "claim_occurrences",
    )
    return {
        "revision": str(evidence.get("revision") or ""),
        "reference_count": sum(
            len(item.get("evidence_refs") or [])
            for collection in collections
            for item in aggregate.get(collection) or []
            if isinstance(item, dict)
        ),
        "aggregate_revision": str(aggregate.get("revision") or ""),
    }


def _state_projection(state: dict[str, object]) -> dict[str, object]:
    return {
        "status": str(state.get("status") or "waiting"),
        "current_step": str(state.get("current_step") or "source-manifest"),
        "next_action": str(state.get("next_action") or ""),
        "message": str(state.get("message") or ""),
        "chunk_id": str(state.get("chunk_id") or ""),
    }


def _mode_projection(mode: str) -> dict[str, str]:
    presentation = MODE_PRESENTATION.get(mode, {"label": mode, "intent": ""})
    return {"id": mode, **presentation}


def _workflow_states(root: Path) -> dict[str, dict[str, object]]:
    result = build_workflow_state(root, route="source-ingest")
    payload = _read_json(result.json_path)
    return {
        str(item.get("work_id") or ""): item
        for item in payload.get("source_ingests") or []
        if isinstance(item, dict)
    }


def _import_dirs(root: Path) -> list[Path]:
    imports = root / "sources" / "imports"
    return [
        path
        for path in sorted(imports.glob("*"))
        if path.is_dir() and not path.name.startswith(".") and (path / "source_manifest.json").is_file()
    ] if imports.is_dir() else []


def _safe_import_dir(root: Path, work_id: str) -> Path:
    if not work_id or "/" in work_id or "\\" in work_id or work_id in {".", ".."}:
        raise ValueError("work_id must be a single import identity")
    import_dir = (root / "sources" / "imports" / work_id).resolve()
    if not import_dir.is_relative_to((root / "sources" / "imports").resolve()):
        raise ValueError("Project Archaeology import leaves the project")
    return import_dir


def _recovery_projection(root: Path) -> list[dict[str, str]]:
    imports = root / "sources" / "imports"
    if not imports.is_dir():
        return []
    return [
        {
            "work_id": path.name.removeprefix(".").removesuffix(".importing").removesuffix(".backup"),
            "kind": "staging" if path.name.endswith(".importing") else "backup",
            "message": "导入曾被中断；再次导入同一作品时会先恢复稳定版本并重新建立临时事务。",
        }
        for path in sorted(imports.glob(".*"))
        if path.is_dir() and path.name.endswith((".importing", ".backup"))
    ]


def _import_recovery_projection(root: Path, work_id: str) -> dict[str, object]:
    imports = root / "sources" / "imports"
    staging = imports / f".{work_id}.importing"
    backup = imports / f".{work_id}.backup"
    return {
        "interrupted": staging.is_dir() or backup.is_dir(),
        "staging_detected": staging.is_dir(),
        "backup_detected": backup.is_dir(),
        "resume_supported": True,
    }


def _stage_is_active(stage: str, current: str) -> bool:
    mapping = {
        "source": {"source-manifest"},
        "segments": {"source-manifest"},
        "chunks": {"chunk-extraction-agent-task", "archaeology-fan-in"},
        "identity": {"archaeology-resolution-agent-task"},
        "reconstruction": {"archaeology-reconstruction-agent-task"},
        "review": {"archaeology-domain-review-agent-task"},
        "archive": {"archaeology-materialize", "ready"},
    }
    return current in mapping.get(stage, set())


def _aggregate_path(manifest: dict[str, object]) -> str:
    archaeology = manifest.get("archaeology")
    return str(archaeology.get("aggregate_path") or "") if isinstance(archaeology, dict) else ""


def _read_relative(root: Path, relative: str) -> dict[str, object]:
    if not relative:
        return {}
    target = (root / relative).resolve()
    return _read_json(target) if target.is_relative_to(root) else {}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
