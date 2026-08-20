"""Evidence port used by Prompt Program compilation."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..contracts import TaskPackage
from .evidence_compiler import EvidenceCompilation, compile_evidence
from .execution_context import ExecutionContextEnvelope


class EvidenceProvider(Protocol):
    """Provide only evidence authorized by one execution context."""

    def provide(
        self,
        task: TaskPackage,
        workspace: Path,
        envelope: ExecutionContextEnvelope,
        *,
        audience: str,
    ) -> EvidenceCompilation: ...


class ProjectEvidenceProvider:
    """Default adapter over the existing projection and evidence policy."""

    def provide(
        self,
        task: TaskPackage,
        workspace: Path,
        envelope: ExecutionContextEnvelope,
        *,
        audience: str,
    ) -> EvidenceCompilation:
        return compile_evidence(task, workspace, envelope, audience=audience)


DEFAULT_EVIDENCE_PROVIDER = ProjectEvidenceProvider()


__all__ = ["DEFAULT_EVIDENCE_PROVIDER", "EvidenceProvider", "ProjectEvidenceProvider"]
