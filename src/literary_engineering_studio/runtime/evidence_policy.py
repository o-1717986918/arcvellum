"""Task-aware evidence placement for Prompt Program v3."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..contracts import TaskPackage


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
    if (
        audience == "tool-worker"
        and task_kind == "prose"
        and lowered.startswith("memory/context_packets/scene_")
        and lowered.endswith(".md")
    ):
        return EvidencePolicyDecision(
            EvidenceDisposition.INLINE, "prose-context-packet"
        )
    if role == "recovery":
        return EvidencePolicyDecision(
            EvidenceDisposition.ON_DEMAND
            if audience == "tool-worker"
            or task.payload.get("context_contract_required") is not True
            else EvidenceDisposition.INLINE
        )

    if audience != "tool-worker":
        return EvidencePolicyDecision(EvidenceDisposition.INLINE)

    if lowered == "style/style-profile.md" and _unmounted_style_template(body):
        return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)

    if task_kind == "prose":
        if task.current_state.casefold() in {"candidate-revision", "static-revision"}:
            return _revision_evidence_policy(task, lowered)
        if lowered in {
            "plot/outline.md",
            "branches/" + str(task.payload.get("scene_id") or "").casefold() + "/branch_selection.md",
            "references/punctuation-standard.md",
        }:
            return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)
        if lowered.endswith("_composition_review.json"):
            return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)
        if lowered.endswith("_composition.md"):
            return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)
        if lowered.endswith("/roleplay_result.json"):
            return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)
        if lowered.endswith("/branch_manifest.json"):
            return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)
        if lowered.endswith("_composition.json"):
            return EvidencePolicyDecision(
                EvidenceDisposition.INLINE, "prose-composition"
            )
        if lowered.startswith("plot/chapter_obligations/") and lowered.endswith(".json"):
            return EvidencePolicyDecision(
                EvidenceDisposition.INLINE, "prose-chapter-obligation"
            )
        if lowered == "plot/word_budget/word_budget.json":
            return EvidencePolicyDecision(
                EvidenceDisposition.INLINE, "prose-word-budget"
            )
        if lowered.startswith("scenes/") and lowered.endswith((".yaml", ".yml")):
            return EvidencePolicyDecision(EvidenceDisposition.INLINE, "prose-scene")
        if lowered == "project.yaml":
            return EvidencePolicyDecision(EvidenceDisposition.INLINE, "project-identity")

    if task.current_state.casefold() == "composition-agent-task":
        scene_id = str(task.payload.get("scene_id") or "").casefold()
        if lowered == f"drafts/compositions/{scene_id}_composition.json":
            return EvidencePolicyDecision(
                EvidenceDisposition.INLINE, "composition-review"
            )
        if lowered == f"scenes/{scene_id}.yaml":
            return EvidencePolicyDecision(
                EvidenceDisposition.INLINE, "prose-scene"
            )
        if lowered == "plot/word_budget/word_budget.json":
            return EvidencePolicyDecision(
                EvidenceDisposition.INLINE, "prose-word-budget"
            )
        if lowered.startswith("plot/chapter_obligations/") and lowered.endswith(".json"):
            return EvidencePolicyDecision(
                EvidenceDisposition.INLINE, "prose-chapter-obligation"
            )
        if lowered == "project.yaml":
            return EvidencePolicyDecision(
                EvidenceDisposition.INLINE, "project-identity"
            )
        if lowered in {
            "style/creative_quality_profile.json",
            "references/punctuation-standard.md",
        }:
            return EvidencePolicyDecision(EvidenceDisposition.INLINE)
        # The composition JSON has already consumed branch, RP, character,
        # chapter and budget inputs. Keep their exact originals available for
        # a concrete dispute, but do not replay the entire project on turn one.
        return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)

    if "asset-review" in task.task_type.casefold():
        if lowered.startswith("plot/word_budget/"):
            return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)
        if lowered in {"plot/conflict_matrix.md", "plot/foreshadowing.csv"}:
            return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)
        asset_type = str(task.payload.get("asset_type") or "").strip().casefold()
        if lowered == "characters/_template.yaml" and asset_type != "character":
            return EvidencePolicyDecision(EvidenceDisposition.ON_DEMAND)

    return EvidencePolicyDecision(EvidenceDisposition.INLINE)


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
