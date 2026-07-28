"""Materialize an exact Context Ledger after the Agent workspace exists."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..contracts import TaskPackage
from ..observability.context_ledger import (
    ContextLedger,
    ContextLedgerEntry,
    context_ledger_id,
)
from ..observability.redaction import redact_preview
from ..orchestration.truth_partition import TruthPartition
from .context_selection import AgentContextSelection
from .execution_context import (
    ContextVisibilityTier,
    ExecutionContextEnvelope,
    SummaryReference,
)


LEDGER_FILENAME = "context-ledger.json"
MACHINE_CONTEXT_PATHS = (
    "AGENT_TASK.md",
    "TASK_CONTEXT.json",
    "_task/task.json",
    "_task/task.agent_tasks.md",
    "_task/execution_contract.json",
    "_task/capability_manifest.json",
    "_task/resource_claim.json",
)


def materialize_runtime_context_ledger(
    task: TaskPackage,
    *,
    run_root: Path,
    workspace: Path,
    run_id: str,
    selection: AgentContextSelection,
    prompt_source_paths: tuple[str, ...],
    prompt_reference_paths: tuple[str, ...],
    prompt_path: Path,
    execution_context: ExecutionContextEnvelope,
) -> ContextLedger:
    entries = _ledger_entries(
        task,
        workspace=workspace,
        selection=selection,
        prompt_source_paths=prompt_source_paths,
        prompt_reference_paths=prompt_reference_paths,
        execution_context=execution_context,
    )
    assembled_sha256 = hashlib.sha256(prompt_path.read_bytes()).hexdigest()
    identity_sha256 = _context_identity_sha256(
        assembled_sha256,
        entries,
        plan_id=str(task.payload.get("creative_plan_id") or ""),
        execution_context_digest=execution_context.context_digest,
    )
    ledger = ContextLedger(
        ledger_id=context_ledger_id(
            project_root_hash=_project_root_hash(task.project_root),
            session_id=f"worker-run:{run_id}",
            operation_id=task.task_id,
            assembled_sha256=assembled_sha256,
            identity_sha256=identity_sha256,
        ),
        project_root_hash=_project_root_hash(task.project_root),
        session_id=f"worker-run:{run_id}",
        operation_id=task.task_id,
        plan_id=str(task.payload.get("creative_plan_id") or ""),
        entries=tuple(entries),
        assembled_sha256=assembled_sha256,
        execution_context_digest=execution_context.context_digest,
    )
    (run_root / LEDGER_FILENAME).write_text(
        json.dumps(ledger.as_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return ledger


def _ledger_entries(
    task: TaskPackage,
    *,
    workspace: Path,
    selection: AgentContextSelection,
    prompt_source_paths: tuple[str, ...],
    prompt_reference_paths: tuple[str, ...],
    execution_context: ExecutionContextEnvelope,
) -> list[ContextLedgerEntry]:
    selected = _selected_paths(
        workspace,
        selection,
        prompt_source_paths,
        prompt_reference_paths,
    )
    requested = _requested_paths(selection, execution_context)
    summaries = {
        item.source_ref: item
        for item in execution_context.summary_references
    }
    return [
        _path_entry(
            workspace,
            source_ref,
            included=_included(source_ref, selected, execution_context),
            purpose=(
                "digest-bound summary reference"
                if source_ref in summaries
                else _purpose_for(task, selection, source_ref)
            ),
            visibility_tier=_visibility_tier(
                source_ref,
                selected,
                execution_context,
            ),
            summary=summaries.get(source_ref),
        )
        for source_ref in requested
    ]


def _selected_paths(
    workspace: Path,
    selection: AgentContextSelection,
    prompt_source_paths: tuple[str, ...],
    prompt_reference_paths: tuple[str, ...],
) -> set[str]:
    selected = {*prompt_source_paths, *prompt_reference_paths}
    selected.update(
        path
        for path in selection.operational_paths
        if (workspace / Path(path)).exists()
    )
    selected.update(
        path
        for path in MACHINE_CONTEXT_PATHS
        if (workspace / Path(path)).exists()
    )
    return selected


def _requested_paths(
    selection: AgentContextSelection,
    execution_context: ExecutionContextEnvelope,
) -> tuple[str, ...]:
    return _unique(
        (
            *execution_context.must_inline,
            *execution_context.exact_on_demand,
            *execution_context.summary_reference_paths,
            *execution_context.excluded,
            *selection.requested_context_paths,
            *selection.operational_paths,
            *MACHINE_CONTEXT_PATHS,
        )
    )


def _included(
    source_ref: str,
    selected: set[str],
    execution_context: ExecutionContextEnvelope,
) -> bool:
    tier = execution_context.tier_for(source_ref)
    return source_ref in selected or tier in {
        ContextVisibilityTier.MUST_INLINE,
        ContextVisibilityTier.EXACT_ON_DEMAND,
        ContextVisibilityTier.SUMMARY_REFERENCE,
    }


def _visibility_tier(
    source_ref: str,
    selected: set[str],
    execution_context: ExecutionContextEnvelope,
) -> ContextVisibilityTier:
    tier = execution_context.tier_for(source_ref)
    if tier is not None:
        return tier
    return (
        ContextVisibilityTier.EXACT_ON_DEMAND
        if source_ref in selected
        else ContextVisibilityTier.EXCLUDED
    )


def _path_entry(
    workspace: Path,
    source_ref: str,
    *,
    included: bool,
    purpose: str,
    visibility_tier: ContextVisibilityTier,
    summary: SummaryReference | None,
) -> ContextLedgerEntry:
    path = workspace / Path(source_ref)
    if summary is not None:
        digest = summary.source_sha256
        byte_count = 0
        character_count = len(summary.summary)
        preview = redact_preview(summary.summary)
        note = "digest_bound_summary_reference"
    else:
        digest, byte_count, character_count, preview = _path_metadata(path)
        note = "" if included else "missing_or_not_materialized"
    return ContextLedgerEntry(
        source_ref=source_ref,
        title=Path(source_ref).name or source_ref,
        purpose=purpose,
        partition=_partition_for(source_ref).value,
        byte_count=byte_count,
        character_count=character_count,
        sha256=digest,
        included=included,
        truncated=False,
        limit=None,
        unit="characters",
        preview=preview,
        note=note,
        visibility_tier=visibility_tier.value,
    )


def _purpose_for(
    task: TaskPackage,
    selection: AgentContextSelection,
    source_ref: str,
) -> str:
    if source_ref in task.core_managed_outputs:
        return "CLI protected task contract"
    if source_ref in task.expected_outputs:
        return "existing allowed output baseline"
    if source_ref in selection.reference_paths:
        return "operating reference"
    if source_ref in selection.source_paths:
        return "task source"
    if source_ref == "project.yaml":
        return "work project identity"
    if source_ref == "workflow/studio/user_directions.md":
        return "current user direction"
    return "machine task control"


def _path_metadata(path: Path) -> tuple[str, int, int, str]:
    if not path.exists():
        return _sha256(b""), 0, 0, ""
    if path.is_file():
        content = path.read_bytes()
        text = content.decode("utf-8", errors="replace")
        return _sha256(content), len(content), len(text), redact_preview(text)
    files = sorted(item for item in path.rglob("*") if item.is_file())
    manifest = {
        item.relative_to(path).as_posix(): _sha256(item.read_bytes())
        for item in files
    }
    serialized = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    byte_count = sum(item.stat().st_size for item in files)
    character_count = sum(
        len(item.read_text(encoding="utf-8", errors="replace"))
        for item in files
    )
    preview = redact_preview(", ".join(manifest) or "(empty directory)")
    return _sha256(serialized), byte_count, character_count, preview


def _partition_for(source_ref: str) -> TruthPartition:
    normalized = source_ref.replace("\\", "/")
    if normalized.startswith(("drafts/scenes/", "releases/")):
        return TruthPartition.HISTORICAL
    if normalized.startswith(("characters/state", "characters/relations", "memory/")):
        return TruthPartition.CURRENT_STATE
    if normalized.startswith(("canon/", "style/", "characters/", "project.yaml")):
        return TruthPartition.STABLE_KNOWLEDGE
    if normalized.startswith(("plot/", "scenes/", "workflow/studio/user_directions")):
        return TruthPartition.FUTURE_INTENT
    return TruthPartition.EVIDENCE


def _project_root_hash(root: Path) -> str:
    normalized = str(root.resolve()).replace("\\", "/").lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _context_identity_sha256(
    prompt_sha256: str,
    entries: list[ContextLedgerEntry],
    *,
    plan_id: str,
    execution_context_digest: str,
) -> str:
    payload = {
        "prompt_sha256": prompt_sha256,
        "plan_id": plan_id,
        "execution_context_digest": execution_context_digest,
        "entries": [item.as_dict() for item in entries],
    }
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item).replace("\\", "/") for item in values))
