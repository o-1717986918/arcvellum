"""Runtime context exposed to bounded capability handlers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from literary_engineering_studio_engine.public.projects import engine_root

from ...contracts import TaskPackage, normalize_relative_path
from .contracts import CapabilityManifest


class WebFetcher(Protocol):
    def __call__(self, url: str, *, max_bytes: int) -> tuple[str, str, str]:
        """Return final URL, content type, and decoded response text."""


@dataclass(frozen=True)
class CapabilityContext:
    task: TaskPackage
    manifest: CapabilityManifest
    run_root: Path
    workspace_root: Path | None = None
    web_fetcher: WebFetcher | None = None

    def resolve_path(self, relative: str, *, scope: str = "auto") -> Path:
        normalized = normalize_relative_path(relative)
        if scope not in {"auto", "project", "workspace", "engine"}:
            raise ValueError(f"invalid capability path scope: {scope}")
        candidates: list[Path] = []
        if scope in {"auto", "workspace"} and self.workspace_root is not None:
            candidates.append(_bounded(self.workspace_root, normalized))
        if scope in {"auto", "project"}:
            candidates.append(_bounded(self.task.project_root, normalized))
        if scope in {"auto", "engine"}:
            candidates.append(_bounded(engine_root(), normalized))
        if scope != "auto":
            return candidates[0]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]


def _bounded(root: Path, relative) -> Path:
    base = root.resolve()
    target = (base / Path(*relative.parts)).resolve()
    if not target.is_relative_to(base):
        raise ValueError("capability path escapes its declared root")
    return target
