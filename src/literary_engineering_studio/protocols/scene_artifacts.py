"""Stable path predicates for versioned scene revision artifacts."""

from __future__ import annotations


def is_scene_revision_candidate_path(path: str) -> bool:
    """Return whether *path* is a prose candidate for any revision round."""

    normalized = path.replace("\\", "/")
    return normalized.endswith(".md") and _is_revision_stem(
        _artifact_stem(normalized), directory=normalized
    )


def is_scene_revision_manifest_path(path: str) -> bool:
    """Return whether *path* is the JSON manifest paired with a revision."""

    normalized = path.replace("\\", "/")
    return normalized.endswith(".json") and _is_revision_stem(
        _artifact_stem(normalized), directory=normalized
    )


def is_scene_revision_transaction_path(path: str) -> bool:
    """Return whether *path* belongs to the Agent-written revision pair."""

    return is_scene_revision_candidate_path(path) or is_scene_revision_manifest_path(path)


def _artifact_stem(path: str) -> str:
    return path.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def _is_revision_stem(stem: str, *, directory: str) -> bool:
    if not directory.startswith("drafts/revisions/"):
        return False
    prefix, marker, suffix = stem.rpartition("_revision")
    if not marker or not prefix:
        return False
    return not suffix or (suffix.startswith("_") and suffix[1:].isdigit())


__all__ = [
    "is_scene_revision_candidate_path",
    "is_scene_revision_manifest_path",
    "is_scene_revision_transaction_path",
]
