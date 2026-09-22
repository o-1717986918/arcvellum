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


READ_TOOLS = (
    "workspace_catalog",
    "project_overview",
    "project_search",
    "creation_observe",
    "project_controls",
    "project_diagnose",
)
ACTION_TOOLS = (
    "project_record_direction",
    "project_decision_resolve",
    "project_quality_update",
    "project_rhythm_update",
    "project_style_mount",
    "project_asset_promote",
    "project_create",
    "project_goal_manage",
    "project_chapter_extend",
)
TOOL_RISKS = {
    **{name: ToolRisk.READ for name in READ_TOOLS},
    **{name: ToolRisk.REVERSIBLE_WRITE for name in ACTION_TOOLS},
    "project_asset_promote": ToolRisk.FORMAL_WRITE,
    "project_create": ToolRisk.FORMAL_WRITE,
    "project_chapter_extend": ToolRisk.FORMAL_WRITE,
    # Protocol compatibility only. New Agent turns use project_goal_manage.
    "creation_control": ToolRisk.REVERSIBLE_WRITE,
}


def available_read_tools(dependencies: ProjectAgentDependencies) -> tuple[str, ...]:
    return tuple(
        name for name, handler in (
            ("workspace_catalog", dependencies.workspace_catalog),
            ("project_overview", dependencies.project_overview),
            ("project_search", dependencies.project_search),
            ("creation_observe", dependencies.creation_observe),
            ("project_controls", dependencies.project_controls),
            ("project_diagnose", dependencies.project_diagnose),
        )
        if handler is not None
    )


def available_action_tools(actions: ProjectAgentActionDependencies | None) -> tuple[str, ...]:
    if actions is None:
        return ()
    return tuple(
        name for name, handler in (
            ("project_record_direction", actions.record_direction),
            ("project_decision_resolve", actions.resolve_decision),
            ("project_quality_update", actions.update_quality),
            ("project_rhythm_update", actions.update_rhythm),
            ("project_style_mount", actions.mount_style),
            ("project_asset_promote", actions.promote_asset),
            ("project_create", actions.create_project),
            ("project_goal_manage", actions.manage_goal),
            ("project_chapter_extend", actions.extend_chapter),
        )
        if handler is not None
    )


class ProjectAgentToolDispatcher:
    """Dispatch bounded tools through existing application-service ports."""

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
        # Kept in the constructor for source compatibility with D5-A callers.
        # Project Agent sessions now authorize allowlisted actions directly.
        del user_message
        self._mutation_results: dict[str, Any] = {}

    def __call__(self, call: ProjectAgentToolCall):
        if call.name not in self.enabled:
            raise ValueError(f"Project Agent tool is not enabled: {call.name}")
        risk = TOOL_RISKS.get(call.name)
        if risk is None:
            raise ValueError(f"unknown Project Agent tool: {call.name}")
        read_handlers = {
            "workspace_catalog": self.dependencies.workspace_catalog,
            "project_overview": self.dependencies.project_overview,
            "project_search": self.dependencies.project_search,
            "creation_observe": self.dependencies.creation_observe,
            "project_controls": self.dependencies.project_controls,
            "project_diagnose": self.dependencies.project_diagnose,
        }
        handler = read_handlers.get(call.name)
        if risk is ToolRisk.READ:
            if handler is None:
                raise ValueError(f"Project Agent read tool is not configured: {call.name}")
            root = self._target_root(call) if call.name != "workspace_catalog" else self.project_root
            return handler(root, call.arguments)
        if self.actions is None:
            raise ValueError("Project Agent write actions are not configured")
        action_handlers = {
            "project_record_direction": self.actions.record_direction,
            "creation_control": self.actions.creation_control,
            "project_decision_resolve": self.actions.resolve_decision,
            "project_quality_update": self.actions.update_quality,
            "project_rhythm_update": self.actions.update_rhythm,
            "project_style_mount": self.actions.mount_style,
            "project_asset_promote": self.actions.promote_asset,
            "project_create": self.actions.create_project,
            "project_goal_manage": self.actions.manage_goal,
            "project_chapter_extend": self.actions.extend_chapter,
        }
        handler = action_handlers.get(call.name)
        if handler is None:
            raise ValueError(f"Project Agent action is not configured: {call.name}")
        key = json.dumps(
            {"name": call.name, "arguments": dict(call.arguments)},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        if key not in self._mutation_results:
            root = self.project_root if call.name == "project_create" else self._target_root(call)
            self._mutation_results[key] = handler(root, call.arguments)
        return self._mutation_results[key]

    def _target_root(self, call: ProjectAgentToolCall) -> Path:
        resolver = self.dependencies.resolve_project
        if resolver is None:
            return self.project_root
        root = resolver(self.project_root, call.arguments)
        resolved = root.expanduser().resolve()
        if not (resolved / "project.yaml").is_file():
            raise ValueError("Project Agent target is not a registered work project")
        return resolved

__all__ = [
    "ACTION_TOOLS",
    "READ_TOOLS",
    "TOOL_RISKS",
    "ProjectAgentToolDispatcher",
    "available_action_tools",
    "available_read_tools",
]
