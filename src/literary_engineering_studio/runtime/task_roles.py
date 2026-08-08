"""Fail-closed projection from formal task roles to runtime profiles."""

from __future__ import annotations

from ..contracts import TaskPackage


_RUNTIME_ROLE_BY_AGENT_ROLE = {
    "main-agent": "worker",
    "main-creative-agent": "worker",
    "creative-analysis-agent": "worker",
    "state-analyst": "worker",
    "main-review-agent": "reviewer",
    "orchestration-reviewer": "reviewer",
    "orchestration-planner": "planner",
}


def runtime_role_for_task(task: TaskPackage) -> str:
    """Return the permission-isolated runtime role for an Agent task."""

    if task.execution_contract.execution_policy != "agent-required":
        raise ValueError("runtime role is only defined for Agent-required tasks")
    agent_role = task.execution_contract.agent_role.strip()
    runtime_role = _RUNTIME_ROLE_BY_AGENT_ROLE.get(agent_role)
    if runtime_role is None:
        raise ValueError(f"unsupported formal Agent role: {agent_role or 'missing'}")
    return runtime_role
