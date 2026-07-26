"""Shared source-ingest route paths and identity helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from ...literary.ingest import SOURCE_INGEST_SCHEMA_V2
from ...task_paths import resolve_project_path


SOURCE_INGEST_SCHEMA_V1 = "literary-engineering-workbench/source-ingest/v1"
SOURCE_INGEST_SCHEMAS = {SOURCE_INGEST_SCHEMA_V1, SOURCE_INGEST_SCHEMA_V2}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def evidence_path_from_manifest(manifest: dict[str, object]) -> str:
    record = manifest.get("evidence_index")
    if isinstance(record, dict) and str(record.get("path") or "").strip():
        return str(record["path"])
    return ""


def active_chunk_plan(
    manifest: dict[str, object],
    chunk_id: str,
) -> dict[str, object]:
    archaeology = manifest.get("archaeology")
    plan = archaeology.get("chunk_tasks") if isinstance(archaeology, dict) else []
    records = [item for item in plan if isinstance(item, dict)] if isinstance(plan, list) else []
    if chunk_id:
        return next(
            (
                item
                for item in records
                if str(item.get("chunk_id") or "") == chunk_id
            ),
            {},
        )
    return records[0] if records else {}


def extraction_source_paths(
    import_dir: str,
    report: str,
    task_path: str,
    evidence_path: str,
    chunks: list[str],
    *,
    aggregate_path: str = "",
) -> list[str]:
    extraction_inputs = [aggregate_path] if aggregate_path else chunks
    return [
        "project.yaml",
        f"{import_dir}/source_manifest.json",
        report,
        task_path,
        evidence_path,
        *extraction_inputs,
    ]


def candidate_outputs_from_manifest(
    manifest: dict[str, object],
    work_id: str,
) -> dict[str, str]:
    outputs = manifest.get("candidate_outputs")
    values = outputs if isinstance(outputs, dict) else {}
    if values:
        return {
            str(key): str(value)
            for key, value in values.items()
            if str(value).strip()
        }
    return {
        "project_brief": f"sources/imports/{work_id}/extracted/project_brief.md",
        "characters": f"characters/candidates/extracted/{work_id}_characters.md",
        "world": f"canon/candidates/extracted/{work_id}_world.md",
        "outline": f"plot/candidates/extracted/{work_id}_outline.md",
        "timeline": f"plot/candidates/extracted/{work_id}_timeline.md",
        "foreshadowing": f"plot/candidates/extracted/{work_id}_foreshadowing.md",
        "style_notes": f"style/candidates/{work_id}_style_generation_notes.md",
        "review": f"reviews/source_ingest/{work_id}_extraction_review.md",
    }


def import_dir_for_task(root: Path, task: dict[str, object]) -> Path:
    work_id = str(
        task.get("work_id")
        or task.get("target_id")
        or task.get("scene_id")
        or ""
    )
    for item in [str(value) for value in task.get("source_paths") or []]:
        normalized = item.replace("\\", "/")
        if "/source_manifest.json" in f"/{normalized}":
            return resolve_project_path(root, normalized).parent
    return root / "sources" / "imports" / (work_id or "source")


def read_optional_json(path: Path) -> tuple[dict[str, object], str]:
    if not path.exists():
        return {}, f"JSON file missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON: {path.name} ({exc.msg})"
    except OSError as exc:
        return {}, str(exc)
    if not isinstance(payload, dict):
        return {}, f"JSON root is not an object: {path}"
    return payload, ""


def static_review_conclusion(path: Path) -> str:
    text = (
        path.read_text(encoding="utf-8", errors="ignore").strip()
        if path.exists()
        else ""
    )
    match = re.search(
        r"(?m)^-\s*(?:审查)?结论：\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip().lower() if match else ""
