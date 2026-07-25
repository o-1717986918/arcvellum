"""Stable, user-facing contracts for Style Atelier projections."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RightsStatus(str, Enum):
    DECLARED = "declared"
    MISSING = "missing"


class StyleVersionState(str, Enum):
    PROFILE = "profile"
    PROMPT_CANDIDATE = "prompt-candidate"
    EVALUATED = "evaluated"
    MOUNTABLE = "mountable"
    MOUNTED = "mounted"


@dataclass(frozen=True)
class RightsProjection:
    mode: str
    declaration: str

    def as_dict(self) -> dict[str, str]:
        declared = bool(self.mode.strip() and self.declaration.strip())
        return {
            "status": RightsStatus.DECLARED.value if declared else RightsStatus.MISSING.value,
            "mode": self.mode,
            "declaration": self.declaration,
        }


@dataclass(frozen=True)
class SourceProjection:
    source_id: str
    filename: str
    content_sha256: str
    character_count: int
    chunk_count: int
    imported_at: str

    def as_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "filename": self.filename,
            "content_sha256": self.content_sha256,
            "character_count": self.character_count,
            "chunk_count": self.chunk_count,
            "imported_at": self.imported_at,
        }


@dataclass(frozen=True)
class EvaluationProjection:
    evaluation_id: str
    mode: str
    overall_score: float
    risk_level: str
    style_quality_status: str
    leakage_risk_status: str
    candidate_sha256: str
    reference_sha256: str

    def as_dict(self) -> dict[str, object]:
        return {
            "evaluation_id": self.evaluation_id,
            "mode": self.mode,
            "overall_score": self.overall_score,
            "risk_level": self.risk_level,
            "style_quality_status": self.style_quality_status,
            "leakage_risk_status": self.leakage_risk_status,
            "candidate_sha256": self.candidate_sha256,
            "reference_sha256": self.reference_sha256,
        }
