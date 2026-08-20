"""Stable task-package, completion, and semantic-contract API."""

from ..tasking.agent_tasks.writer import (
    agent_task_completion_status,
    write_agent_completion_marker,
)
from ..tasking.gates import branch_selection_status
from ..tasking.registry import issue_next_task
from ..tasking.semantic_contracts import (
    semantic_artifact_definition,
    semantic_artifact_errors,
    semantic_artifact_relative_path,
    semantic_artifact_template,
    validated_branch_proposal_ids,
)

__all__ = [
    "agent_task_completion_status",
    "branch_selection_status",
    "issue_next_task",
    "semantic_artifact_definition",
    "semantic_artifact_errors",
    "semantic_artifact_relative_path",
    "semantic_artifact_template",
    "validated_branch_proposal_ids",
    "write_agent_completion_marker",
]
