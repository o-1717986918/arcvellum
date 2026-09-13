"""Thin Project Agent tool mapping over existing Studio read models."""

from __future__ import annotations

from pathlib import Path

from .contracts import ProjectAgentDependencies, ProjectAgentToolCall


class ProjectAgentReadDispatcher:
    """Dispatch declared read tools without importing API routers or project files."""

    def __init__(
        self,
        project_root: Path,
        dependencies: ProjectAgentDependencies,
        *,
        enabled: tuple[str, ...] = ("project_overview",),
    ):
        self.project_root = project_root.expanduser().resolve()
        self.dependencies = dependencies
        self.enabled = frozenset(enabled)

    def __call__(self, call: ProjectAgentToolCall):
        if call.name not in self.enabled:
            raise ValueError(f"Project Agent tool is not enabled: {call.name}")
        handlers = {
            "project_overview": self.dependencies.project_overview,
            "project_search": self.dependencies.project_search,
            "creation_observe": self.dependencies.creation_observe,
        }
        handler = handlers.get(call.name)
        if handler is None:
            raise ValueError(f"unknown Project Agent tool: {call.name}")
        return handler(self.project_root, call.arguments)

