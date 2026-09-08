"""Pure contracts for the lean scene-transaction kernel.

These objects describe literary intent and verified model output. Runtime paths,
task receipts, hashes, and persistence metadata belong to Studio adapters.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class SceneExecutionMode(str, Enum):
    DRAFT = "draft"
    STANDARD = "standard"
    PUBLICATION = "publication"
    STRICT_V1 = "strict-v1"


class SceneTransactionStatus(str, Enum):
    READY = "ready"
    PREPARED = "prepared"
    CREATING = "creating"
    VERIFYING = "verifying"
    REVIEWING = "reviewing"
    REVISION_NEEDED = "revision-needed"
    COMMITTABLE = "committable"
    COMMITTED = "committed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class SceneRiskLevel(str, Enum):
    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"

    @classmethod
    def from_compatible_value(cls, value: str | Enum) -> "SceneRiskLevel":
        """Map strict-v1 risk names without importing the Studio scorer."""

        raw = str(getattr(value, "value", value)).strip().lower()
        aliases = {"compact": cls.LOW, "deep": cls.HIGH}
        if raw in aliases:
            return aliases[raw]
        return cls(raw)


class ReviewDecision(str, Enum):
    PASS = "pass"
    REVISE = "revise"
    ESCALATE = "escalate"


class IssueSeverity(str, Enum):
    WARNING = "warning"
    HARD = "hard"


@dataclass(frozen=True)
class LengthTarget:
    target_hanzi: int = 0
    soft_min: int = 0
    soft_max: int = 0


@dataclass(frozen=True)
class RhythmDirective:
    pace: str = ""
    detail: str = ""
    scene_turn: str = ""
    reader_effect: str = ""


@dataclass(frozen=True)
class StyleMountRef:
    style_id: str = ""
    revision: str = ""


@dataclass(frozen=True)
class SceneRisk:
    level: SceneRiskLevel
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class SceneBrief:
    scene_id: str
    objective: str
    scene_function: str
    participants: tuple[str, ...]
    canon_constraints: tuple[str, ...]
    incoming_handoff: tuple[str, ...]
    chapter_obligations: tuple[str, ...]
    rhythm: RhythmDirective
    length: LengthTarget
    style_mount: StyleMountRef
    risk: SceneRisk
    source_refs: tuple[str, ...] = ()
    viewpoint: str = ""
    location: str = ""
    external_conflict: str = ""
    internal_conflict: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))


@dataclass(frozen=True)
class ChangeProposal:
    """One model-proposed semantic change with human-readable evidence."""

    target_ref: str
    summary: str
    evidence: str = ""
    operation: str = "update"
    attributes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SceneDelta:
    character_changes: tuple[ChangeProposal, ...] = ()
    canon_candidates: tuple[ChangeProposal, ...] = ()
    continuity_changes: tuple[ChangeProposal, ...] = ()
    promise_updates: tuple[ChangeProposal, ...] = ()
    reader_question_updates: tuple[ChangeProposal, ...] = ()
    next_handoff: tuple[str, ...] = ()
    new_asset_candidates: tuple[ChangeProposal, ...] = ()

    def proposals(self) -> tuple[ChangeProposal, ...]:
        return (
            self.character_changes
            + self.canon_candidates
            + self.continuity_changes
            + self.promise_updates
            + self.reader_question_updates
            + self.new_asset_candidates
        )

    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))


@dataclass(frozen=True)
class CreativeResult:
    prose: str
    decision_summary: str
    scene_delta: SceneDelta
    decision_trace: tuple[str, ...] = ()
    escalation_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))


@dataclass(frozen=True)
class VerificationIssue:
    code: str
    severity: IssueSeverity
    message: str
    evidence: str = ""


@dataclass(frozen=True)
class VerificationReport:
    scene_id: str
    body_hanzi: int
    issues: tuple[VerificationIssue, ...] = ()

    @property
    def hard_failures(self) -> tuple[VerificationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is IssueSeverity.HARD)

    @property
    def warnings(self) -> tuple[VerificationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is IssueSeverity.WARNING)

    @property
    def can_commit(self) -> bool:
        return not self.hard_failures

    def to_dict(self) -> dict[str, Any]:
        payload = _json_value(asdict(self))
        payload["can_commit"] = self.can_commit
        return payload


@dataclass(frozen=True)
class ReviewResult:
    decision: ReviewDecision
    summary: str = ""
    revision_instructions: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    @property
    def passes(self) -> bool:
        return self.decision is ReviewDecision.PASS


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


__all__ = [
    "ChangeProposal",
    "CreativeResult",
    "IssueSeverity",
    "LengthTarget",
    "ReviewDecision",
    "ReviewResult",
    "RhythmDirective",
    "SceneBrief",
    "SceneDelta",
    "SceneExecutionMode",
    "SceneRisk",
    "SceneRiskLevel",
    "SceneTransactionStatus",
    "StyleMountRef",
    "VerificationIssue",
    "VerificationReport",
]
