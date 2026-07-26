"""Build bounded Planner context and its exact metadata ledger."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

from ..observability.context_ledger import (
    ContextLedger,
    ContextLedgerEntry,
    context_ledger_id,
)
from ..observability.redaction import redact_preview
from .truth_partition import TruthPartition


@dataclass(frozen=True)
class PlanningSourceDocument:
    source_ref: str
    title: str
    purpose: str
    partition: TruthPartition
    content: str
    mandatory: bool = False


@dataclass(frozen=True)
class AssembledPlanningContext:
    text: str
    ledger: ContextLedger


def assemble_planning_context(
    sources: tuple[PlanningSourceDocument, ...],
    *,
    project_root_hash: str,
    session_id: str,
    operation_id: str,
    plan_id: str = "",
    max_source_characters: int = 24_000,
    max_total_characters: int = 96_000,
) -> AssembledPlanningContext:
    _validate_request(sources, max_source_characters, max_total_characters)
    ordered_sources = _ordered_sources(sources)
    remaining = max_total_characters
    rendered: list[str] = []
    entries: list[ContextLedgerEntry] = []
    for index, source in enumerate(ordered_sources):
        future_mandatory = sum(1 for item in ordered_sources[index + 1 :] if item.mandatory)
        selected, included, truncated, source_limit = _select_content(
            source,
            remaining=remaining,
            future_mandatory=future_mandatory,
            max_source_characters=max_source_characters,
        )
        if included:
            rendered.append(_render_source(source, selected))
            remaining -= len(selected)
        entries.append(
            _ledger_entry(
                source,
                selected=selected,
                included=included,
                truncated=truncated,
                source_limit=source_limit,
            )
        )

    text = "\n\n".join(rendered)
    assembled_sha256 = _sha256(text)
    ledger = ContextLedger(
        ledger_id=context_ledger_id(
            project_root_hash=project_root_hash,
            session_id=session_id,
            operation_id=operation_id,
            assembled_sha256=assembled_sha256,
        ),
        project_root_hash=project_root_hash,
        session_id=session_id,
        operation_id=operation_id,
        plan_id=plan_id,
        entries=tuple(entries),
        assembled_sha256=assembled_sha256,
    )
    return AssembledPlanningContext(text=text, ledger=ledger)


def _validate_request(
    sources: tuple[PlanningSourceDocument, ...],
    max_source_characters: int,
    max_total_characters: int,
) -> None:
    if not sources:
        raise ValueError("planning context requires at least one source")
    if max_source_characters < 1 or max_total_characters < 1:
        raise ValueError("planning context limits must be positive")
    if len({item.source_ref for item in sources}) != len(sources):
        raise ValueError("planning context source refs must be unique")
    for source in sources:
        if not source.source_ref.strip() or not source.title.strip() or not source.purpose.strip():
            raise ValueError("planning source identity and purpose are required")


def _ordered_sources(
    sources: tuple[PlanningSourceDocument, ...],
) -> tuple[PlanningSourceDocument, ...]:
    return tuple(item for item in sources if item.mandatory) + tuple(
        item for item in sources if not item.mandatory
    )


def _select_content(
    source: PlanningSourceDocument,
    *,
    remaining: int,
    future_mandatory: int,
    max_source_characters: int,
) -> tuple[str, bool, bool, int]:
    available = max(0, remaining - future_mandatory)
    source_limit = min(max_source_characters, available)
    included = source_limit > 0
    if source.mandatory and not included:
        raise ValueError(f"mandatory planning source cannot fit the context budget: {source.source_ref}")
    selected = source.content[:source_limit] if included else ""
    return selected, included, included and len(selected) < len(source.content), source_limit


def _render_source(source: PlanningSourceDocument, selected: str) -> str:
    return "\n".join(
        (
            f"## {source.title}",
            f"source: {source.source_ref}",
            f"truth_partition: {source.partition.value}",
            f"purpose: {source.purpose}",
            "",
            selected,
        )
    )


def _ledger_entry(
    source: PlanningSourceDocument,
    *,
    selected: str,
    included: bool,
    truncated: bool,
    source_limit: int,
) -> ContextLedgerEntry:
    return ContextLedgerEntry(
        source_ref=source.source_ref,
        title=source.title,
        purpose=source.purpose,
        partition=source.partition.value,
        byte_count=len(source.content.encode("utf-8")),
        character_count=len(source.content),
        sha256=_sha256(source.content),
        included=included,
        truncated=truncated,
        limit=source_limit,
        unit="characters",
        preview=redact_preview(selected),
        note="mandatory" if source.mandatory else "",
    )
def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
