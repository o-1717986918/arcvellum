"""Revision identities and machine-only proof inputs for scene blueprints."""

from __future__ import annotations

import re
from pathlib import Path

from ...literary.scene.promotion.historical_context import (
    historical_revision_source_paths,
)
from ...task_paths import relative_path, resolve_project_path
from ...tasking.paths import read_json


def revision_blueprint_contract(
    root: Path,
    scene_id: str,
    current_state: str,
    candidate: str,
) -> tuple[str, str, str, tuple[str, ...]]:
    """Resolve one revision source, immutable output base, and proof closure."""

    review = f"reviews/agent/{scene_id}_scene_review"
    review_path = root / f"{review}.json"
    payload = read_json(review_path) if review_path.is_file() else {}
    source = str(
        payload.get("candidate")
        or payload.get("reviewed_candidate")
        or payload.get("draft")
        or f"{candidate}.md"
    ).replace("\\", "/")
    if Path(source).is_absolute():
        source = relative_path(Path(source), root)
    if current_state in {"static-revision", "target-length-revision"}:
        source = f"drafts/scenes/{scene_id}.md"
    revision = _next_revision_base(root, scene_id, source)
    proof = historical_revision_source_paths(
        root, scene_id, resolve_project_path(root, source)
    )
    return review, source, revision, proof


def _next_revision_base(root: Path, scene_id: str, revision_source: str) -> str:
    first = f"drafts/revisions/{scene_id}_revision"
    normalized = revision_source.replace("\\", "/")
    if not normalized.startswith("drafts/revisions/") and not (root / f"{first}.md").exists():
        return first
    highest = 1 if (root / f"{first}.md").exists() else 0
    folder = root / "drafts" / "revisions"
    pattern = re.compile(rf"^{re.escape(scene_id)}_revision_(\d+)[.]md$")
    for path in folder.glob(f"{scene_id}_revision_*.md") if folder.is_dir() else ():
        match = pattern.match(path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"drafts/revisions/{scene_id}_revision_{highest + 1:02d}"


__all__ = ["revision_blueprint_contract"]
