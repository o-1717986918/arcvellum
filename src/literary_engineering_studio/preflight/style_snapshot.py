"""Machine-owned style snapshot binding for sandbox outputs."""

from __future__ import annotations

from pathlib import Path

from literary_engineering_studio_engine.literary.style.snapshot import (
    read_artifact_style_mount_snapshot,
)


def candidate_style_snapshot(candidate_path: Path) -> dict[str, object]:
    return read_artifact_style_mount_snapshot(
        candidate_path.with_suffix(".json"),
        candidate_path.with_suffix(".prompt.json"),
    )


def prompt_style_snapshot(prompt_manifest_path: Path) -> dict[str, object]:
    return read_artifact_style_mount_snapshot(prompt_manifest_path)


__all__ = ["candidate_style_snapshot", "prompt_style_snapshot"]
