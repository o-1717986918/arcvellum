"""One source-selection contract shared by prompt and sandbox materialization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..contracts import TaskPackage


OPERATING_REFERENCE_PATHS = {
    "SKILL.md",
    "AGENTS.md",
    "agentread.yaml",
    "references/agent-run-protocol.md",
    "references/cli-run-protocol.md",
    "references/artifact-contracts.md",
    "references/workflows.md",
}


@dataclass(frozen=True)
class AgentContextSelection:
    source_paths: tuple[str, ...]
    reference_paths: tuple[str, ...]
    operational_paths: tuple[str, ...]
    visible_paths: tuple[str, ...]
    excluded_paths: tuple[str, ...] = ()
    summary_reference_paths: tuple[str, ...] = ()

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


def compact_task_references(task: TaskPackage) -> tuple[str, ...]:
    """Remove host-operation manuals when an exact task Prompt owns protocol."""

    prompt_asset = (
        task.payload.get("prompt_asset")
        if isinstance(task.payload.get("prompt_asset"), dict)
        else {}
    )
    if task.execution_contract.execution_policy == "deterministic":
        return ()
    if prompt_asset.get("exact") is not True:
        return task.required_reading
    return tuple(
        path
        for path in task.required_reading
        if path not in OPERATING_REFERENCE_PATHS
    )


def select_agent_context(task: TaskPackage) -> AgentContextSelection:
    agent_sources = task.payload.get("agent_source_paths")
    sources = (
        tuple(str(item) for item in agent_sources)
        if isinstance(agent_sources, list)
        else tuple(task.source_paths)
    )
    references = compact_task_references(task)
    summary_paths = _summary_paths(task.payload.get("context_summary_references"))
    explicitly_excluded = _strings(task.payload.get("context_excluded_paths"))
    contract_paths = _context_contract_paths(task)
    _validate_context_tiers(contract_paths, explicitly_excluded, summary_paths)
    unavailable_inline = set((*explicitly_excluded, *summary_paths))
    # The tier contract is authoritative. A compact ``agent_source_paths`` list
    # may remove optional material, but it cannot remove files that the same
    # task declares mandatory or exact-on-demand.
    sources = tuple(
        path
        for path in _unique((*contract_paths, *sources))
        if path not in unavailable_inline
    )
    references = tuple(path for path in _unique(references) if path not in unavailable_inline)
    operational = (
        *task.expected_outputs,
        *task.core_managed_outputs,
        "project.yaml",
        "workflow/studio/user_directions.md",
    )
    visible = _unique((*references, *sources, *operational))
    excluded = _unique(
        (
            *explicitly_excluded,
            *(path for path in task.source_paths if path not in visible and path not in summary_paths),
            *(path for path in task.required_reading if path not in visible and path not in summary_paths),
        )
    )
    return AgentContextSelection(
        source_paths=sources,
        reference_paths=references,
        operational_paths=_unique(operational),
        visible_paths=visible,
        excluded_paths=excluded,
        summary_reference_paths=summary_paths,
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


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return _unique(str(item) for item in value if str(item).strip())


def _context_contract_paths(task: TaskPackage) -> tuple[str, ...]:
    return _unique(
        (
            *_strings(task.payload.get("context_must_inline_paths")),
            *_strings(task.payload.get("context_exact_on_demand_paths")),
        )
    )


def _validate_context_tiers(
    contract_paths: tuple[str, ...],
    excluded_paths: tuple[str, ...],
    summary_paths: tuple[str, ...],
) -> None:
    unavailable = set((*excluded_paths, *summary_paths))
    conflicting = tuple(path for path in contract_paths if path in unavailable)
    if conflicting:
        raise ValueError(
            "context tier contract conflicts with excluded or summary paths: "
            + ", ".join(conflicting)
        )


def _summary_paths(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return _unique(
        str(item.get("source_ref") or item.get("source_path") or "")
        for item in value
        if isinstance(item, dict)
        and str(item.get("source_ref") or item.get("source_path") or "").strip()
    )
