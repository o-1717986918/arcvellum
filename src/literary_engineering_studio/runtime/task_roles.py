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

_NON_AGENT_OUTPUT_KINDS = frozenset(
    {
        "completion-evidence",
        "deterministic",
        "human-approval",
    }
)


def runtime_role_for_task(task: TaskPackage) -> str:
    """Return the least-privileged runtime profile that can execute the task."""

    contract = task.execution_contract
    if contract.execution_policy != "agent-required":
        raise ValueError("runtime role is only defined for Agent-required tasks")
    agent_role = contract.agent_role.strip()
    runtime_role = _RUNTIME_ROLE_BY_AGENT_ROLE.get(agent_role)
    if runtime_role is None:
        raise ValueError(f"unsupported formal Agent role: {agent_role or 'missing'}")

    requires_write = "write-expected-outputs" in contract.runtime_capabilities_required
    has_agent_outputs = any(
        output.kind not in _NON_AGENT_OUTPUT_KINDS for output in contract.outputs
    )
    if has_agent_outputs != requires_write:
        raise ValueError(
            "task execution contract must grant write-expected-outputs exactly when "
            "Agent-authored outputs are declared"
        )
    if requires_write:
        return "worker"
    return runtime_role
