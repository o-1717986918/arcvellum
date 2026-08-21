"""Freshness and current-content checks for chapter delivery artifacts."""

from __future__ import annotations

from pathlib import Path

from ...foundation.display_cleaner import scalar_from_yaml_text
from ...release_fingerprint import release_candidate_fingerprint
from ...task_paths import relative_path


DELIVERY_KEYS = ("novel", "screenplay", "video_prompt_pack")


def chapter_workspace_is_fresh(
    root: Path,
    chapter_id: str,
    outputs: list[Path],
) -> bool:
    return outputs_are_fresh(outputs, chapter_formal_drafts(root, chapter_id))


def export_package_is_fresh(root: Path, chapter_id: str, manifest: Path) -> bool:
    sources = [
        root / "plot" / "chapters" / f"{chapter_id}.json",
        root / "drafts" / "chapters" / f"{chapter_id}.md",
        *chapter_formal_drafts(root, chapter_id),
    ]
    return outputs_are_fresh([manifest], sources)


def missing_export_outputs(root: Path, payload: dict[str, object]) -> list[str]:
    outputs = payload.get("outputs")
    outputs = outputs if isinstance(outputs, dict) else {}
    required = [outputs.get(key) for key in DELIVERY_KEYS]
    for group_name in ("docx", "docx_layout_plans", "docx_inspections"):
        group = outputs.get(group_name)
        group = group if isinstance(group, dict) else {}
        required.extend(group.get(key) for key in DELIVERY_KEYS)
    return [str(item) for item in required if not item or not (root / str(item)).exists()]


def published_release_is_current(
    root: Path,
    chapter_id: str,
    latest_path: Path,
    manifest: Path,
    latest: dict[str, object],
    payload: dict[str, object],
) -> tuple[bool, bool]:
    approval = payload.get("approval")
    approval = approval if isinstance(approval, dict) else {}
    approved = str(payload.get("approved_export_fingerprint") or "").strip().lower()
    current = release_candidate_fingerprint(root, chapter_id).lower()
    content_bound = bool(approved) and approved == current
    passed = all((
        latest_path.exists(),
        manifest.exists(),
        str(payload.get("status") or "").strip().lower() == "published",
        not payload.get("allow_unapproved"),
        approval.get("decision") == "approve",
        content_bound,
        str(approval.get("subject_sha256") or "").strip().lower() == approved,
        latest.get("manifest") == relative_path(manifest, root),
    ))
    return passed, content_bound


def chapter_formal_drafts(root: Path, chapter_id: str) -> list[Path]:
    drafts: list[Path] = []
    for scene_path in sorted((root / "scenes").glob("*.yaml")):
        if scene_path.name.startswith("_"):
            continue
        text = scene_path.read_text(encoding="utf-8", errors="ignore")
        if scalar_from_yaml_text(text, "chapter_id") != chapter_id:
            continue
        scene_id = scalar_from_yaml_text(text, "scene_id") or scene_path.stem
        draft = root / "drafts" / "scenes" / f"{scene_id}.md"
        if draft.is_file():
            drafts.append(draft)
    return drafts


def outputs_are_fresh(outputs: list[Path], sources: list[Path]) -> bool:
    existing_outputs = [path for path in outputs if path.is_file()]
    existing_sources = [path for path in sources if path.is_file()]
    if len(existing_outputs) != len(outputs):
        return False
    if not existing_sources:
        return True
    oldest_output = min(path.stat().st_mtime_ns for path in existing_outputs)
    newest_source = max(path.stat().st_mtime_ns for path in existing_sources)
    return oldest_output >= newest_source


__all__ = [
    "chapter_formal_drafts",
    "chapter_workspace_is_fresh",
    "export_package_is_fresh",
    "missing_export_outputs",
    "outputs_are_fresh",
    "published_release_is_current",
]
