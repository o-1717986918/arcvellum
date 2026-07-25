"""Route projection of an Engine-owned style-engineering session."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...literary.style.session import (
    load_style_session,
    style_session_holdout_reference,
    style_session_source_paths,
)
from ...task_paths import relative_path, resolve_project_path


@dataclass(frozen=True)
class StyleRouteSessionContext:
    active: bool
    reference: str
    profile_command: str
    profile_sources: tuple[str, ...]
    compile_outputs: tuple[str, ...]


def build_style_route_session_context(
    root: Path,
    profile_dir: str,
) -> StyleRouteSessionContext:
    profile_path = resolve_project_path(root, profile_dir)
    session = load_style_session(profile_path)
    reference_path = (
        style_session_holdout_reference(profile_path)
        if session
        else _legacy_reference(profile_path)
    )
    reference = relative_path(reference_path, root) if reference_path is not None else ""
    base_outputs = (
        f"{profile_dir}/style-profile.md",
        f"{profile_dir}/style_metrics.json",
    )
    if not session:
        return StyleRouteSessionContext(
            False,
            reference,
            "python -m literary_engineering_studio_engine style-profile "
            "<corpus> --out-dir <profile-dir> --name <name>",
            (profile_dir,),
            base_outputs,
        )
    name = f"{session.get('author_id') or 'style'}-{session.get('profile_id') or 'profile'}"
    command = (
        f'python -m literary_engineering_studio_engine style-profile '
        f'"<project>/{profile_dir}/corpus" --out-dir "<project>/{profile_dir}" '
        f'--name "{name}"'
    )
    source_paths = (
        f"{profile_dir}/style_session.json",
        *(relative_path(path, root) for path in style_session_source_paths(profile_path)),
    )
    outputs = (
        *base_outputs,
        f"{profile_dir}/corpus_manifest.yaml",
        f"{profile_dir}/evaluation_cases/back_translation.md",
        f"{profile_dir}/evaluation_cases/outline_expansion.md",
        f"{profile_dir}/evaluation_cases/blind_review.md",
    )
    return StyleRouteSessionContext(True, reference, command, source_paths, outputs)


def _legacy_reference(profile_path: Path) -> Path | None:
    return next(
        (
            path
            for path in sorted((profile_path / "corpus").glob("*.txt"))
            if path.is_file() and path.stat().st_size > 0
        ),
        None,
    )
