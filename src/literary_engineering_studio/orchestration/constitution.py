"""Machine-owned literary engineering constitution for plan compilation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json

from literary_engineering_studio_engine.public.orchestration import PlanNodeKind

from .contracts import to_primitive


class ConstitutionSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class ConstitutionRule:
    rule_id: str
    severity: ConstitutionSeverity
    applies_to: tuple[PlanNodeKind, ...] = ()
    requires: tuple[str, ...] = ()
    protected_resources: tuple[str, ...] = ()


@dataclass(frozen=True)
class OrchestrationConstitution:
    version: str
    rules: tuple[ConstitutionRule, ...]

    @property
    def digest(self) -> str:
        encoded = json.dumps(
            to_primitive(self),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def constitution_v1() -> OrchestrationConstitution:
    prose = (PlanNodeKind.FORMAL_PROSE, PlanNodeKind.REVISION)
    return OrchestrationConstitution(
        version="1",
        rules=(
            ConstitutionRule("prose-single-writer", ConstitutionSeverity.ERROR, applies_to=prose),
            ConstitutionRule(
                "prose-requires-contracts",
                ConstitutionSeverity.ERROR,
                applies_to=(PlanNodeKind.FORMAL_PROSE,),
                requires=(
                    "canon-context",
                    "character-state",
                    "word-budget",
                    "scene-function",
                    "rhythm-contract",
                    "bridge-contract",
                    "mounted-style",
                ),
            ),
            ConstitutionRule("no-gate-deletion", ConstitutionSeverity.ERROR),
            ConstitutionRule(
                "revision-requires-fresh-review",
                ConstitutionSeverity.ERROR,
                applies_to=(PlanNodeKind.REVISION,),
                requires=("fresh-revision-review",),
            ),
            ConstitutionRule(
                "formal-mutation-requires-patch",
                ConstitutionSeverity.ERROR,
                applies_to=(PlanNodeKind.STATE_EVOLUTION, PlanNodeKind.CANON_EVOLUTION),
                protected_resources=("canon", "character-state", "timeline", "promise-ledger"),
            ),
            ConstitutionRule("no-arbitrary-command", ConstitutionSeverity.ERROR),
            ConstitutionRule("context-broker-mandatory-sources", ConstitutionSeverity.ERROR),
            ConstitutionRule("resource-conflict-check", ConstitutionSeverity.ERROR),
            ConstitutionRule("longform-inventory-consistency", ConstitutionSeverity.ERROR),
            ConstitutionRule("subagent-cannot-author-prose", ConstitutionSeverity.ERROR, applies_to=prose),
            ConstitutionRule("planning-is-not-formal-progress", ConstitutionSeverity.ERROR),
        ),
    )
