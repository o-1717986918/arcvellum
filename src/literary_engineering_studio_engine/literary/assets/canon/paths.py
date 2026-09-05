"""Canonical paths for scene-level Canon candidates and applies.

Canon paths are part of the workflow contract.  Keeping them here prevents
scene handoff, review routing, and apply code from silently describing
different files.
"""

from __future__ import annotations

from pathlib import Path


def canon_patch_path(root: Path, scene_id: str) -> Path:
    return root.resolve() / "canon" / "patches" / f"{scene_id}_canon_patch.json"


def canon_patch_report_path(root: Path, scene_id: str) -> Path:
    return canon_patch_path(root, scene_id).with_suffix(".md")


def canon_patch_task_path(root: Path, scene_id: str) -> Path:
    return canon_patch_path(root, scene_id).with_suffix(".agent_tasks.md")


def canon_patch_review_path(root: Path, scene_id: str) -> Path:
    patch = canon_patch_path(root, scene_id)
    return patch.with_name(f"{patch.stem}_review.json")


def canon_patch_id_for_scene(scene_id: str) -> str:
    return f"{scene_id}_canon_patch"


def canon_apply_manifest_path(root: Path, patch_id: str) -> Path:
    return root.resolve() / "canon" / "applied" / f"{patch_id}_apply.json"


def canon_apply_report_path(root: Path, patch_id: str) -> Path:
    return root.resolve() / "canon" / "applied" / f"{patch_id}_apply.md"


def canon_apply_manifest_for_scene(root: Path, scene_id: str) -> Path:
    return canon_apply_manifest_path(root, canon_patch_id_for_scene(scene_id))


__all__ = [
    "canon_apply_manifest_for_scene",
    "canon_apply_manifest_path",
    "canon_apply_report_path",
    "canon_patch_id_for_scene",
    "canon_patch_path",
    "canon_patch_report_path",
    "canon_patch_review_path",
    "canon_patch_task_path",
]
