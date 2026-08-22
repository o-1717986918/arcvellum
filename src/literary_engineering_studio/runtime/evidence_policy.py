"""Task-aware evidence placement for Prompt Program v3."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..contracts import TaskPackage
from literary_engineering_studio_engine.public.tasking import SCENE_REVISION_STATES


class EvidenceDisposition(str, Enum):
    INLINE = "inline"
    ON_DEMAND = "on_demand"


@dataclass(frozen=True)
class EvidencePolicyDecision:
    disposition: EvidenceDisposition
    projection: str = "default"


def evidence_policy(
    task: TaskPackage,
    path: str,
    role: str,
    *,
    audience: str,
    task_kind: str,
    body: str = "",
) -> EvidencePolicyDecision:
    """Choose first-turn placement and projection without changing source truth."""

    lowered = path.casefold()
    if _is_prose_context_packet(audience, task_kind, lowered):
        return EvidencePolicyDecision(
            EvidenceDisposition.INLINE, "prose-context-packet"
        )
    if role == "recovery":
        return _recovery_policy(task, audience)
    if audience != "tool-worker":
        return EvidencePolicyDecision(EvidenceDisposition.INLINE)
    if lowered == "style/style-profile.md" and _unmounted_style_template(body):
        return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)
    decision = _task_specific_policy(task, lowered, task_kind)
    return decision or EvidencePolicyDecision(EvidenceDisposition.INLINE)


def _is_prose_context_packet(audience: str, task_kind: str, path: str) -> bool:
    return (
        audience == "tool-worker"
        and task_kind == "prose"
        and path.startswith("memory/context_packets/scene_")
        and path.endswith(".md")
    )


def _recovery_policy(task: TaskPackage, audience: str) -> EvidencePolicyDecision:
    on_demand = (
        audience == "tool-worker"
        or task.payload.get("context_contract_required") is not True
    )
    return EvidencePolicyDecision(
        EvidenceDisposition.ON_DEMAND if on_demand else EvidenceDisposition.INLINE
    )


def _task_specific_policy(
    task: TaskPackage,
    path: str,
    task_kind: str,
) -> EvidencePolicyDecision | None:
    state = task.current_state.casefold()
    if task_kind == "prose":
        return _prose_evidence_policy(task, path)
    policies = {
        "reader-experience-contract": _reader_experience_evidence_policy,
        "composition-agent-task": _composition_evidence_policy,
        "continuity-ledger-agent-task": _continuity_evidence_policy,
        "state-agent-task": _state_evidence_policy,
        "canon-patch-json": _canon_evidence_policy,
        "canon-agent-task": _canon_evidence_policy,
        "committee-agent-task": _committee_evidence_policy,
    }
    if policy := policies.get(state):
        return policy(task, path)
    return _asset_review_evidence_policy(task, path)


def _reader_experience_evidence_policy(
    _task: TaskPackage,
    path: str,
) -> EvidencePolicyDecision:
    """Keep chapter planning semantic and bounded on the first turn.

    Reader-experience planning needs the chapter inventory, not prose lint,
    lifecycle receipts, or duplicate human-readable reports.  Those sources
    remain authorized on demand for a specific dispute.
    """

    projections = {
        "project.yaml": "project-identity",
        "plot/word_budget/word_budget.json": "prose-word-budget",
    }
    if projection := projections.get(path):
        return EvidencePolicyDecision(EvidenceDisposition.INLINE, projection)
    if path.startswith("scenes/") and path.endswith((".yaml", ".yml")):
        return EvidencePolicyDecision(EvidenceDisposition.INLINE, "prose-scene")
    if path.startswith("plot/chapter_obligations/") and path.endswith(".json"):
        return EvidencePolicyDecision(
            EvidenceDisposition.INLINE,
            "prose-chapter-obligation",
        )
    if path.startswith("characters/") and path.endswith((".yaml", ".yml")):
        return EvidencePolicyDecision(EvidenceDisposition.INLINE)
    if path in {
        "plot/outline.md",
        "plot/foreshadowing.csv",
        "plot/conflict_matrix.md",
        "canon/facts.json",
        "canon/forbidden_changes.yaml",
        "canon/timeline.yaml",
        "canon/world_rules.yaml",
    }:
        return EvidencePolicyDecision(EvidenceDisposition.INLINE)
    return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)


def _committee_evidence_policy(
    _task: TaskPackage,
    path: str,
) -> EvidencePolicyDecision:
    if path == "reviews/longform/longform_audit.json":
        return EvidencePolicyDecision(
            EvidenceDisposition.INLINE,
            "committee-longform-audit",
        )
    if path in {
        "reviews/agent/canon_review.md",
        "reviews/longform/longform_audit.md",
    }:
        return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)
    return EvidencePolicyDecision(EvidenceDisposition.INLINE)


def _prose_evidence_policy(
    task: TaskPackage,
    path: str,
) -> EvidencePolicyDecision:
    if task.current_state.casefold() in SCENE_REVISION_STATES:
        return _revision_evidence_policy(task, path)
    scene_id = _scene_id(task)
    on_demand = {
        "plot/outline.md", f"branches/{scene_id}/branch_selection.md",
        "references/punctuation-standard.md",
    }
    if path in on_demand or path.endswith(
        ("_composition_review.json", "_composition.md", "/roleplay_result.json", "/branch_manifest.json")
    ):
        return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)
    projections = {
        "plot/word_budget/word_budget.json": "prose-word-budget",
        "project.yaml": "project-identity",
    }
    if projection := projections.get(path):
        return EvidencePolicyDecision(EvidenceDisposition.INLINE, projection)
    if path.endswith("_composition.json"):
        return EvidencePolicyDecision(EvidenceDisposition.INLINE, "prose-composition")
    if path.startswith("plot/chapter_obligations/") and path.endswith(".json"):
        return EvidencePolicyDecision(EvidenceDisposition.INLINE, "prose-chapter-obligation")
    if path.startswith("scenes/") and path.endswith((".yaml", ".yml")):
        return EvidencePolicyDecision(EvidenceDisposition.INLINE, "prose-scene")
    return EvidencePolicyDecision(EvidenceDisposition.INLINE)


def _composition_evidence_policy(task: TaskPackage, path: str) -> EvidencePolicyDecision:
    scene_id = _scene_id(task)
    projections = {
        f"drafts/compositions/{scene_id}_composition.json": "composition-review",
        f"scenes/{scene_id}.yaml": "prose-scene",
        "plot/word_budget/word_budget.json": "prose-word-budget",
        "project.yaml": "project-identity",
    }
    if projection := projections.get(path):
        return EvidencePolicyDecision(EvidenceDisposition.INLINE, projection)
    if path.startswith("plot/chapter_obligations/") and path.endswith(".json"):
        return EvidencePolicyDecision(EvidenceDisposition.INLINE, "prose-chapter-obligation")
    if path in {"style/creative_quality_profile.json", "references/punctuation-standard.md"}:
        return EvidencePolicyDecision(EvidenceDisposition.INLINE)
    return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)


def _continuity_evidence_policy(task: TaskPackage, path: str) -> EvidencePolicyDecision:
    scene_id = _scene_id(task)
    projections = {
        f"drafts/scenes/{scene_id}.md": "continuity-prose",
        f"scenes/{scene_id}.yaml": "continuity-scene",
    }
    if projection := projections.get(path):
        return EvidencePolicyDecision(EvidenceDisposition.INLINE, projection)
    if path in {"plot/reader_questions/ledger.json", "plot/promises/ledger.json"}:
        return EvidencePolicyDecision(EvidenceDisposition.INLINE)
    return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)


def _state_evidence_policy(task: TaskPackage, path: str) -> EvidencePolicyDecision:
    scene_id = _scene_id(task)
    projections = {
        f"characters/state_patches/{scene_id}_state_patch.json": "state-patch",
        f"drafts/scenes/{scene_id}.md": "state-prose",
        f"drafts/compositions/{scene_id}_composition.json": "state-composition",
        f"scenes/{scene_id}.yaml": "state-scene",
    }
    if projection := projections.get(path):
        return EvidencePolicyDecision(EvidenceDisposition.INLINE, projection)
    if path.startswith("characters/") and path.endswith((".yaml", ".yml")):
        return EvidencePolicyDecision(EvidenceDisposition.INLINE, "state-character")
    return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)


def _canon_evidence_policy(task: TaskPackage, path: str) -> EvidencePolicyDecision:
    scene_id = _scene_id(task)
    projections = {
        f"drafts/scenes/{scene_id}.md": "canon-prose",
        f"scenes/{scene_id}.yaml": "canon-scene",
        f"reviews/agent/{scene_id}_scene_review.json": "canon-scene-review",
        f"characters/state_patches/{scene_id}_state_patch.json": "canon-state-boundary",
    }
    if projection := projections.get(path):
        return EvidencePolicyDecision(EvidenceDisposition.INLINE, projection)
    if path == f"canon/patches/{scene_id}_canon_patch.json" or path in _CANON_SOURCES:
        return EvidencePolicyDecision(EvidenceDisposition.INLINE)
    return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)


_CANON_SOURCES = frozenset(
    {
        "canon/facts.json", "canon/forbidden_changes.yaml", "canon/locations.yaml",
        "canon/organizations.yaml", "canon/timeline.yaml", "canon/world_rules.yaml",
    }
)


def _asset_review_evidence_policy(
    task: TaskPackage,
    path: str,
) -> EvidencePolicyDecision | None:
    if "asset-review" not in task.task_type.casefold():
        return None
    asset_type = str(task.payload.get("asset_type") or "").strip().casefold()
    if (
        path.startswith("plot/word_budget/")
        or path in {"plot/conflict_matrix.md", "plot/foreshadowing.csv"}
        or (path == "characters/_template.yaml" and asset_type != "character")
    ):
        return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)
    return None


def _scene_id(task: TaskPackage) -> str:
    return str(task.payload.get("scene_id") or "").casefold()


def _revision_evidence_policy(
    task: TaskPackage,
    lowered: str,
) -> EvidencePolicyDecision:
    """Keep revision evidence exact and small enough to drive one focused edit."""

    scene_id = str(task.payload.get("scene_id") or "").casefold()
    if lowered.startswith("drafts/") and lowered.endswith(".md"):
        if lowered == str(task.payload.get("revision_source") or "").casefold():
            return EvidencePolicyDecision(EvidenceDisposition.INLINE)
        if lowered == str(task.payload.get("candidate") or "").casefold():
            return EvidencePolicyDecision(EvidenceDisposition.INLINE)
    if lowered == f"reviews/agent/{scene_id}_scene_review.json":
        return EvidencePolicyDecision(
            EvidenceDisposition.INLINE, "revision-review"
        )
    if lowered == f"scenes/{scene_id}.yaml":
        return EvidencePolicyDecision(EvidenceDisposition.INLINE, "prose-scene")
    if lowered in {
        "style/creative_quality_profile.json",
        "style/style-profile.md",
    }:
        return EvidencePolicyDecision(EvidenceDisposition.INLINE)
    # The exact review Markdown, composition trail, branch choice, budget
    # ledger and trace remain available for a specific dispute. Replaying
    # them on turn one competes with the actual prose and actionable notes.
    return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)


def _unmounted_style_template(body: str) -> bool:
    """Recognize the shipped blank profile without rejecting a sparse real style."""

    normalized = "\n".join(line.rstrip() for line in body.splitlines()).strip()
    if "# 风格 Profile 模板" not in normalized:
        return False
    value_lines = [
        line.split("：", 1)[1].strip()
        for line in normalized.splitlines()
        if line.lstrip().startswith("-") and "：" in line
    ]
    return bool(value_lines) and not any(value_lines)


__all__ = [
    "EvidenceDisposition",
    "EvidencePolicyDecision",
    "evidence_policy",
]
