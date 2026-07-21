"""Bounded project context for candidate-asset creation and review."""

from __future__ import annotations

from pathlib import Path


def compact_asset_context_paths(root: Path) -> list[Path]:
    """Return high-signal files without copying whole planning directories."""

    project = root.resolve()
    paths: list[Path] = [project / "project.yaml"]
    paths.extend(sorted(path for path in (project / "canon").glob("*") if path.is_file()))
    paths.extend(sorted(path for path in (project / "characters").glob("*.yaml") if path.is_file()))
    for relative in (
        "plot/outline.md",
        "plot/word_budget/word_budget.md",
        "plot/conflict_matrix.md",
        "plot/foreshadowing.csv",
        "style/active_style.yaml",
        "style/mounted/style_prompt.md",
        "style/mounted/style-profile.md",
    ):
        path = project / relative
        if path.is_file():
            paths.append(path)

    result: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen and resolved.is_file():
            result.append(resolved)
            seen.add(resolved)
    return result


def compact_asset_context_relpaths(root: Path) -> list[str]:
    project = root.resolve()
    return [path.relative_to(project).as_posix() for path in compact_asset_context_paths(project)]
