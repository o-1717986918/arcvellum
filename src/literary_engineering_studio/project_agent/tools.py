"""Allowlisted Project Agent tool mapping over existing Studio services."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import (
    ProjectAgentActionDependencies,
    ProjectAgentDependencies,
    ProjectAgentToolCall,
    ToolRisk,
)


READ_TOOLS = ("project_overview", "project_search", "creation_observe")
ACTION_TOOLS = ("project_record_direction", "creation_control")
TOOL_RISKS = {
    **{name: ToolRisk.READ for name in READ_TOOLS},
    **{name: ToolRisk.REVERSIBLE_WRITE for name in ACTION_TOOLS},
}


class ProjectAgentToolDispatcher:
    """Dispatch bounded tools and require current-message evidence for mutations."""

    def __init__(
        self,
        project_root: Path,
        dependencies: ProjectAgentDependencies,
        *,
        enabled: tuple[str, ...] = ("project_overview",),
        actions: ProjectAgentActionDependencies | None = None,
        user_message: str = "",
    ):
        self.project_root = project_root.expanduser().resolve()
        self.dependencies = dependencies
        self.actions = actions
        self.enabled = frozenset(enabled)
        self.user_message = _normalized_text(user_message)
        self._mutation_results: dict[str, Any] = {}

    def __call__(self, call: ProjectAgentToolCall):
        if call.name not in self.enabled:
            raise ValueError(f"Project Agent tool is not enabled: {call.name}")
        risk = TOOL_RISKS.get(call.name)
        if risk is None:
            raise ValueError(f"unknown Project Agent tool: {call.name}")
        read_handlers = {
            "project_overview": self.dependencies.project_overview,
            "project_search": self.dependencies.project_search,
            "creation_observe": self.dependencies.creation_observe,
        }
        handler = read_handlers.get(call.name)
        if risk is ToolRisk.READ and handler is not None:
            return handler(self.project_root, call.arguments)
        if self.actions is None:
            raise ValueError("Project Agent write actions are not configured")
        _require_explicit_intent(call.arguments, self.user_message)
        action_handlers = {
            "project_record_direction": self.actions.record_direction,
            "creation_control": self.actions.creation_control,
        }
        handler = action_handlers.get(call.name)
        if handler is None:
            raise ValueError(f"unknown Project Agent tool: {call.name}")
        key = json.dumps(
            {"name": call.name, "arguments": dict(call.arguments)},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        if key not in self._mutation_results:
            self._mutation_results[key] = handler(self.project_root, call.arguments)
        return self._mutation_results[key]


def _require_explicit_intent(arguments: Any, user_message: str) -> None:
    quote = _normalized_text(str(arguments.get("intent_quote") or ""))
    if len(quote) < 2:
        raise ValueError("Project Agent write action requires intent_quote from the current user message")
    if quote not in user_message:
        raise ValueError("Project Agent intent_quote is not present in the current user message")


def _normalized_text(value: str) -> str:
    return " ".join(value.strip().casefold().split())


__all__ = ["ACTION_TOOLS", "READ_TOOLS", "TOOL_RISKS", "ProjectAgentToolDispatcher"]
