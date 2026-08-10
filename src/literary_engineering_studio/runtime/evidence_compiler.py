"""Compile authorized context tiers into Prompt v3 evidence."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Iterable

from .execution_context import ExecutionContextEnvelope
from .prompt_program import OnDemandEvidence, PromptEvidence


@dataclass(frozen=True)
class EvidenceCompilation:
    inline: tuple[PromptEvidence, ...]
    exact_on_demand: tuple[OnDemandEvidence, ...]
    dropped_path_count: int
    dropped_digest_count: int
    dropped_characters: int

    def safe_metrics(self) -> dict[str, int]:
        return {
            "inline_count": len(self.inline),
            "exact_on_demand_count": len(self.exact_on_demand),
            "dropped_path_count": self.dropped_path_count,
            "dropped_digest_count": self.dropped_digest_count,
            "dropped_characters": self.dropped_characters,
        }


def compile_evidence(
    workspace: Path,
    envelope: ExecutionContextEnvelope,
) -> EvidenceCompilation:
    root = workspace.resolve()
    seen_paths: set[str] = set()
    seen_digests: set[str] = set()
    inline: list[PromptEvidence] = []
    dropped_paths = dropped_digests = dropped_characters = 0
    for source_ref in envelope.must_inline:
        normalized = _normalized_path(source_ref)
        if normalized in seen_paths:
            dropped_paths += 1
            continue
        body = _read_authorized_text(root, normalized)
        source_digest = _sha256(body)
        if source_digest in seen_digests:
            dropped_digests += 1
            dropped_characters += len(body)
            continue
        seen_paths.add(normalized)
        seen_digests.add(source_digest)
        role, fidelity = _evidence_role(normalized, envelope.task_kind)
        inline.append(
            PromptEvidence(
                evidence_id=f"E{len(inline) + 1:03d}",
                source_ref=normalized,
                source_sha256=source_digest,
                projection_sha256=source_digest,
                role=role,
                tier="must_inline",
                fidelity=fidelity,
                body=body,
            )
        )
    summaries = list(envelope.summary_references)
    for summary in summaries:
        normalized = _normalized_path(summary.source_ref)
        if normalized in seen_paths or summary.summary_sha256 in seen_digests:
            dropped_paths += int(normalized in seen_paths)
            dropped_digests += int(summary.summary_sha256 in seen_digests)
            dropped_characters += len(summary.summary)
            continue
        seen_paths.add(normalized)
        seen_digests.add(summary.summary_sha256)
        inline.append(
            PromptEvidence(
                evidence_id=f"E{len(inline) + 1:03d}",
                source_ref=normalized,
                source_sha256=summary.source_sha256,
                projection_sha256=summary.summary_sha256,
                role="summary",
                tier="summary_reference",
                fidelity="summary",
                body=summary.summary,
            )
        )
    exact = tuple(
        OnDemandEvidence(
            evidence_id=f"D{index:03d}",
            source_ref=normalized,
            source_sha256=_sha256(_read_authorized_text(root, normalized)),
            role=_evidence_role(normalized, envelope.task_kind)[0],
            reason="仅在首轮证据不足以完成一项具体判断时读取",
        )
        for index, normalized in enumerate(
            _unique(_normalized_path(item) for item in envelope.exact_on_demand),
            start=1,
        )
    )
    return EvidenceCompilation(
        inline=tuple(inline),
        exact_on_demand=exact,
        dropped_path_count=dropped_paths,
        dropped_digest_count=dropped_digests,
        dropped_characters=dropped_characters,
    )


def _evidence_role(path: str, task_kind: str) -> tuple[str, str]:
    lowered = path.casefold()
    if "candidate" in lowered or "/draft" in lowered or lowered.startswith("drafts/"):
        return ("candidate" if task_kind == "review" else "drafting_material", "lossless")
    if lowered.startswith("style/") or "style" in lowered:
        return "mounted_style", "lossless"
    if lowered.startswith("characters/"):
        return "character_state", "lossless"
    if lowered.startswith("canon/"):
        return "canon", "structured"
    if lowered.startswith("scenes/"):
        return "scene", "structured"
    if "context.json" in lowered or "lint" in lowered or "budget" in lowered:
        return "deterministic_evidence", "structured"
    if "context_packet" in lowered:
        return "context_packet", "recovery"
    if lowered.endswith(".agent_tasks.md"):
        return "task_sidecar", "recovery"
    return "project_evidence", "structured"


def _read_authorized_text(root: Path, relative: str) -> str:
    path = (root / Path(relative)).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"prompt evidence escapes workspace: {relative}")
    if not path.is_file():
        raise ValueError(f"prompt evidence is missing: {relative}")
    data = path.read_bytes()
    if b"\x00" in data:
        raise ValueError(f"prompt evidence is not text: {relative}")
    return data.decode("utf-8")


def _normalized_path(value: str) -> str:
    normalized = str(value).replace("\\", "/").strip().lstrip("./")
    if not normalized:
        raise ValueError("prompt evidence path is empty")
    return normalized


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = ["EvidenceCompilation", "compile_evidence"]
