"""Versioned model execution context compiled from one formal task package."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from ..contracts import TaskPackage
from .context_budget import TaskContextBudget
from .context_selection import AgentContextSelection
from .prompt_context import PreparedPromptContext


EXECUTION_CONTEXT_SCHEMA = "arcvellum/execution-context-envelope/v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ContextVisibilityTier(str, Enum):
    MUST_INLINE = "must_inline"
    EXACT_ON_DEMAND = "exact_on_demand"
    SUMMARY_REFERENCE = "summary_reference"
    EXCLUDED = "excluded"


@dataclass(frozen=True)
class SummaryReference:
    source_ref: str
    summary: str
    source_sha256: str
    summary_sha256: str

    def __post_init__(self) -> None:
        if not self.source_ref.strip() or not self.summary.strip():
            raise ValueError("summary reference source and text are required")
        if not _SHA256.fullmatch(self.source_sha256):
            raise ValueError("summary reference source_sha256 is invalid")
        actual = _sha256(self.summary.encode("utf-8"))
        if self.summary_sha256 != actual:
            raise ValueError("summary reference digest does not match its text")

    def as_dict(self) -> dict[str, str]:
        return {
            "source_ref": self.source_ref,
            "summary": self.summary,
            "source_sha256": self.source_sha256,
            "summary_sha256": self.summary_sha256,
        }


@dataclass(frozen=True)
class ExecutionContextEnvelope:
    task_id: str
    route: str
    current_state: str
    scene_id: str
    task_kind: str
    agent_role: str
    prompt_asset_id: str
    prompt_asset_version: str
    must_inline: tuple[str, ...]
    exact_on_demand: tuple[str, ...]
    summary_references: tuple[SummaryReference, ...]
    excluded: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    hard_constraints: tuple[str, ...]
    context_digest: str
    character_budget: int
    first_turn_visible_characters: int
    budget_mode: str
    prepared_context_sha256: str
    user_direction_sha256: str

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.agent_role.strip():
            raise ValueError("execution context task_id and agent_role are required")
        if not _SHA256.fullmatch(self.context_digest):
            raise ValueError("execution context digest is invalid")
        if not _SHA256.fullmatch(self.user_direction_sha256):
            raise ValueError("execution context user direction digest is invalid")
        if self.character_budget < 0 or self.first_turn_visible_characters < 0:
            raise ValueError("execution context character counts cannot be negative")
        _validate_disjoint_tiers(self)

    @property
    def summary_reference_paths(self) -> tuple[str, ...]:
        return tuple(item.source_ref for item in self.summary_references)

    def tier_for(self, path: str) -> ContextVisibilityTier | None:
        normalized = _normalize(path)
        for tier, paths in self.tier_paths().items():
            if normalized in paths:
                return tier
        return None

    def tier_paths(self) -> dict[ContextVisibilityTier, tuple[str, ...]]:
        return {
            ContextVisibilityTier.MUST_INLINE: self.must_inline,
            ContextVisibilityTier.EXACT_ON_DEMAND: self.exact_on_demand,
            ContextVisibilityTier.SUMMARY_REFERENCE: self.summary_reference_paths,
            ContextVisibilityTier.EXCLUDED: self.excluded,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": EXECUTION_CONTEXT_SCHEMA,
            "task_id": self.task_id,
            "route": self.route,
            "current_state": self.current_state,
            "scene_id": self.scene_id,
            "task_kind": self.task_kind,
            "agent_role": self.agent_role,
            "prompt_asset_id": self.prompt_asset_id,
            "prompt_asset_version": self.prompt_asset_version,
            "must_inline": list(self.must_inline),
            "exact_on_demand": list(self.exact_on_demand),
            "summary_references": [item.as_dict() for item in self.summary_references],
            "excluded": list(self.excluded),
            "expected_outputs": list(self.expected_outputs),
            "hard_constraints": list(self.hard_constraints),
            "context_digest": self.context_digest,
            "character_budget": self.character_budget,
            "first_turn_visible_characters": self.first_turn_visible_characters,
            "budget_mode": self.budget_mode,
            "prepared_context_sha256": self.prepared_context_sha256,
            "user_direction_sha256": self.user_direction_sha256,
        }

    def safe_projection(self) -> dict[str, Any]:
        return {
            "schema": EXECUTION_CONTEXT_SCHEMA,
            "digest": self.context_digest,
            "task_kind": self.task_kind,
            "agent_role": self.agent_role,
            "budget_mode": self.budget_mode,
            "character_budget": self.character_budget,
            "first_turn_visible_characters": self.first_turn_visible_characters,
            "tier_counts": {
                tier.value: len(paths)
                for tier, paths in self.tier_paths().items()
            },
        }


@dataclass(frozen=True)
class _ClassifiedContextPaths:
    must_inline: tuple[str, ...]
    exact_on_demand: tuple[str, ...]
    excluded: tuple[str, ...]


def build_execution_context_envelope(
    task: TaskPackage,
    *,
    workspace: Path,
    selection: AgentContextSelection,
    prepared_context: PreparedPromptContext,
    budget: TaskContextBudget | None,
    user_direction: str = "",
) -> ExecutionContextEnvelope:
    summaries = _summary_references(task.payload.get("context_summary_references"))
    _validate_summary_sources(task, summaries)
    paths = _classify_context_paths(task, selection, prepared_context, summaries)
    _validate_workspace_paths(workspace, paths.exact_on_demand)
    hard_constraints = _hard_constraints(task)
    identity = _execution_context_identity(
        task,
        workspace=workspace,
        paths=paths,
        summaries=summaries,
        hard_constraints=hard_constraints,
        prepared_context=prepared_context,
        budget=budget,
        user_direction=user_direction,
    )
    digest = _digest(identity)
    return ExecutionContextEnvelope(
        task_id=task.task_id,
        route=task.route,
        current_state=task.current_state,
        scene_id=str(task.payload.get("scene_id") or ""),
        task_kind=str(identity["task_kind"]),
        agent_role=task.execution_contract.agent_role,
        prompt_asset_id=str(identity["prompt_asset_id"]),
        prompt_asset_version=str(identity["prompt_asset_version"]),
        must_inline=paths.must_inline,
        exact_on_demand=paths.exact_on_demand,
        summary_references=summaries,
        excluded=paths.excluded,
        expected_outputs=tuple(task.expected_outputs),
        hard_constraints=hard_constraints,
        context_digest=digest,
        character_budget=int(identity["character_budget"]),
        first_turn_visible_characters=prepared_context.character_count,
        budget_mode=str(identity["budget_mode"]),
        prepared_context_sha256=prepared_context.sha256,
        user_direction_sha256=str(identity["user_direction_sha256"]),
    )


def execution_context_program_fields(
    envelope: Mapping[str, Any],
    prepared: PreparedPromptContext,
    *,
    fallback_paths: Iterable[str] = (),
) -> dict[str, str]:
    exact = _strings(envelope.get("exact_on_demand"))
    if not envelope:
        inline = set(prepared.included_paths)
        exact = [path for path in fallback_paths if path not in inline]
    summaries = (
        envelope.get("summary_references")
        if isinstance(envelope.get("summary_references"), list)
        else []
    )
    excluded = _strings(envelope.get("excluded"))
    digest = str(envelope.get("context_digest") or "")
    budget = int(envelope.get("character_budget") or 0)
    return {
        "context_identity": _context_identity_lines(digest, budget, excluded),
        "on_demand_lines": _path_lines(exact),
        "summary_reference_lines": _summary_lines(summaries),
    }


def _classify_context_paths(
    task: TaskPackage,
    selection: AgentContextSelection,
    prepared_context: PreparedPromptContext,
    summaries: tuple[SummaryReference, ...],
) -> _ClassifiedContextPaths:
    summary_paths = tuple(item.source_ref for item in summaries)
    must_inline = _unique(prepared_context.included_paths)
    exact_on_demand = _unique(
        path
        for path in prepared_context.omitted_paths
        if path not in prepared_context.unavailable_paths
        and path not in summary_paths
    )
    classified = set((*must_inline, *exact_on_demand, *summary_paths))
    excluded = _unique(
        (
            *selection.excluded_paths,
            *prepared_context.unavailable_paths,
            *(
                path
                for path in selection.requested_context_paths
                if path not in classified
            ),
        )
    )
    _validate_mandatory_paths(task, must_inline)
    return _ClassifiedContextPaths(must_inline, exact_on_demand, excluded)


def _validate_mandatory_paths(
    task: TaskPackage,
    must_inline: tuple[str, ...],
) -> None:
    declared = _strings(task.payload.get("context_must_inline_paths"))
    missing = [path for path in declared if path not in must_inline]
    if missing:
        raise ValueError(
            "execution context mandatory paths are not present in the first-turn snapshot: "
            + ", ".join(missing)
            + "。请先完成前序正式步骤（上下文准备、场景合成、长期规划义务），"
            "并确认缺失的项目资料（如 references/punctuation-standard.md）存在。"
        )


def _execution_context_identity(
    task: TaskPackage,
    *,
    workspace: Path,
    paths: _ClassifiedContextPaths,
    summaries: tuple[SummaryReference, ...],
    hard_constraints: tuple[str, ...],
    prepared_context: PreparedPromptContext,
    budget: TaskContextBudget | None,
    user_direction: str,
) -> dict[str, Any]:
    return {
        "schema": EXECUTION_CONTEXT_SCHEMA,
        "task_id": task.task_id,
        "route": task.route,
        "current_state": task.current_state,
        "scene_id": str(task.payload.get("scene_id") or ""),
        "task_kind": budget.task_kind.value if budget is not None else task.task_type,
        "agent_role": task.execution_contract.agent_role,
        "prompt_asset_id": _prompt_asset_value(task, "resolved_id"),
        "prompt_asset_version": _prompt_asset_value(task, "version"),
        "must_inline": _path_identities(workspace, paths.must_inline),
        "exact_on_demand": _path_identities(workspace, paths.exact_on_demand),
        "summary_references": [item.as_dict() for item in summaries],
        "excluded": list(paths.excluded),
        "expected_outputs": list(task.expected_outputs),
        "hard_constraints": list(hard_constraints),
        "character_budget": budget.target_inline_characters if budget is not None else 0,
        "budget_mode": budget.mode.value if budget is not None else "off",
        "prepared_context_sha256": prepared_context.sha256,
        "user_direction_sha256": _sha256(user_direction.encode("utf-8")),
    }


def _summary_references(value: object) -> tuple[SummaryReference, ...]:
    if not isinstance(value, list):
        return ()
    result: list[SummaryReference] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("context_summary_references must contain objects")
        source_ref = _normalize(item.get("source_ref") or item.get("source_path") or "")
        summary = str(item.get("summary") or "").strip()
        supplied_summary_digest = str(item.get("summary_sha256") or "")
        summary_digest = supplied_summary_digest or _sha256(summary.encode("utf-8"))
        result.append(
            SummaryReference(
                source_ref=source_ref,
                summary=summary,
                source_sha256=str(item.get("source_sha256") or ""),
                summary_sha256=summary_digest,
            )
        )
    paths = [item.source_ref for item in result]
    if len(paths) != len(set(paths)):
        raise ValueError("context_summary_references contain duplicate sources")
    return tuple(result)


def _validate_summary_sources(
    task: TaskPackage,
    summaries: tuple[SummaryReference, ...],
) -> None:
    stale: list[str] = []
    for item in summaries:
        source = task.resolve_project_path(item.source_ref)
        if not source.exists() or _path_digest(source) != item.source_sha256:
            stale.append(item.source_ref)
    if stale:
        raise ValueError(
            "summary reference source digest is missing or stale: "
            + ", ".join(stale)
        )


def _hard_constraints(task: TaskPackage) -> tuple[str, ...]:
    prompt_asset = (
        task.payload.get("prompt_asset")
        if isinstance(task.payload.get("prompt_asset"), Mapping)
        else {}
    )
    return _unique(
        (
            *_strings(task.payload.get("hard_constraints")),
            *_strings(prompt_asset.get("hard_constraints")),
            *_strings(task.payload.get("style_constraints")),
            *_strings(prompt_asset.get("style_constraints")),
        )
    )


def _prompt_asset_value(task: TaskPackage, key: str) -> str:
    prompt_asset = task.payload.get("prompt_asset")
    if not isinstance(prompt_asset, Mapping):
        return ""
    return str(prompt_asset.get(key) or "")


def _validate_disjoint_tiers(envelope: ExecutionContextEnvelope) -> None:
    owner: dict[str, ContextVisibilityTier] = {}
    for tier, paths in envelope.tier_paths().items():
        if len(paths) != len(set(paths)):
            raise ValueError(f"execution context {tier.value} contains duplicate paths")
        for path in paths:
            previous = owner.get(path)
            if previous is not None:
                raise ValueError(
                    f"execution context path belongs to multiple tiers: {path} "
                    f"({previous.value}, {tier.value})"
                )
            owner[path] = tier


def _validate_workspace_paths(workspace: Path, paths: Iterable[str]) -> None:
    missing = [path for path in paths if not (workspace / Path(path)).exists()]
    if missing:
        raise ValueError(
            "execution context exact_on_demand paths are not materialized: "
            + ", ".join(missing)
        )


def _context_identity_lines(
    digest: str,
    budget: int,
    excluded: tuple[str, ...],
) -> str:
    if not digest:
        return "- 本调用使用兼容上下文投影。"
    return (
        f"- Execution Context：`{digest}`\n"
        f"- 首轮字符预算：{budget}\n"
        f"- 排除资料：{len(excluded)} 项；它们不在本次读取权限内。"
    )


def _path_lines(paths: Iterable[str]) -> str:
    return "\n".join(f"- `{item}`" for item in paths) or "- 无"


def _summary_lines(values: list[Any]) -> str:
    return "\n".join(
        (
            f"### `{item.get('source_ref')}`\n"
            f"- source sha256: `{item.get('source_sha256')}`\n"
            f"- summary: {item.get('summary')}"
        )
        for item in values
        if isinstance(item, Mapping)
    ) or "- 无"


def _path_identities(workspace: Path, paths: Iterable[str]) -> list[dict[str, str]]:
    return [
        {"path": path, "sha256": _path_digest(workspace / Path(path))}
        for path in paths
    ]


def _path_digest(path: Path) -> str:
    if not path.exists():
        return _sha256(b"")
    if path.is_file():
        return _sha256(path.read_bytes())
    manifest = {
        item.relative_to(path).as_posix(): _sha256(item.read_bytes())
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }
    return _digest(manifest)


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return _unique(str(item) for item in value if str(item).strip())


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            normalized
            for value in values
            if (normalized := _normalize(value))
        )
    )


def _normalize(value: object) -> str:
    return str(value or "").strip().replace("\\", "/")


def _digest(value: object) -> str:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256(rendered.encode("utf-8"))


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
