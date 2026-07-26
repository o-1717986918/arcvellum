"""One source-selection contract shared by prompt and sandbox materialization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..contracts import TaskPackage
from .task_program import compact_task_references


@dataclass(frozen=True)
class AgentContextSelection:
    source_paths: tuple[str, ...]
    reference_paths: tuple[str, ...]
    operational_paths: tuple[str, ...]
    visible_paths: tuple[str, ...]

    @property
    def requested_context_paths(self) -> tuple[str, ...]:
        return _unique((*self.reference_paths, *self.source_paths))

    def copied_prompt_paths(
        self,
        copied_paths: Iterable[str],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        copied = set(_unique(copied_paths))
        sources = tuple(path for path in self.source_paths if path in copied)
        references = tuple(path for path in self.reference_paths if path in copied)
        return sources, references


def select_agent_context(task: TaskPackage) -> AgentContextSelection:
    agent_sources = task.payload.get("agent_source_paths")
    sources = (
        tuple(str(item) for item in agent_sources)
        if isinstance(agent_sources, list)
        else tuple(task.source_paths)
    )
    references = compact_task_references(task)
    operational = (
        *task.expected_outputs,
        *task.core_managed_outputs,
        "project.yaml",
        "workflow/studio/user_directions.md",
    )
    return AgentContextSelection(
        source_paths=_unique(sources),
        reference_paths=_unique(references),
        operational_paths=_unique(operational),
        visible_paths=_unique((*references, *sources, *operational)),
    )


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).replace("\\", "/")
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return tuple(result)
