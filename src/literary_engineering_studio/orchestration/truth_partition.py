"""Truth partitions and source provenance for creative planning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class TruthPartition(str, Enum):
    HISTORICAL = "historical_truth"
    CURRENT_STATE = "current_state"
    STABLE_KNOWLEDGE = "stable_knowledge"
    FUTURE_INTENT = "future_intent"
    EVIDENCE = "evidence_and_opinion"


class AssertionKind(str, Enum):
    FACT = "fact"
    INFERENCE = "inference"
    UNCERTAINTY = "uncertainty"
    PROPOSAL = "proposal"


@dataclass(frozen=True)
class ProvenanceRef:
    source_ref: str
    digest: str
    partition: TruthPartition
    assertion_kind: AssertionKind
    purpose: str

    def __post_init__(self) -> None:
        if not self.source_ref.strip():
            raise ValueError("provenance source_ref is required")
        if not _SHA256.fullmatch(self.digest):
            raise ValueError("provenance digest must be a lowercase SHA-256")
        if not self.purpose.strip():
            raise ValueError("provenance purpose is required")
        if self.partition == TruthPartition.FUTURE_INTENT and self.assertion_kind == AssertionKind.FACT:
            raise ValueError("future intent cannot claim a fact")
        if self.assertion_kind == AssertionKind.PROPOSAL and self.partition != TruthPartition.FUTURE_INTENT:
            raise ValueError("proposals must remain in the future-intent partition")

    def as_dict(self) -> dict[str, str]:
        return {
            "source_ref": self.source_ref,
            "digest": self.digest,
            "partition": self.partition.value,
            "assertion_kind": self.assertion_kind.value,
            "purpose": self.purpose,
        }


def partition_can_satisfy_formal_gate(partition: TruthPartition) -> bool:
    """Future intent and review opinion can never prove a formal gate."""

    return partition in {
        TruthPartition.HISTORICAL,
        TruthPartition.CURRENT_STATE,
        TruthPartition.STABLE_KNOWLEDGE,
    }
