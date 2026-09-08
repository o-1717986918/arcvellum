"""Chapter-level quality checkpoint for the lean literary kernel."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from literary_engineering_studio_engine.literary.planning.narrative_rhythm import (
    analyze_narrative_rhythm_sequence,
)
from literary_engineering_studio_engine.literary.scene.transaction import (
    SceneDelta,
    SceneTransactionStatus,
)

from ..orchestration.chapter_facts import (
    ChapterFactsValidationMode,
    ChapterPlanningFacts,
    chapter_facts_violations,
)
from .scene_transaction import SceneTransaction


@dataclass(frozen=True)
class ProjectPlanBundle:
    chapter: ChapterPlanningFacts
    story_spine_ref: str
    word_budget_ref: str
    scene_inventory_ref: str
    obligation_ref: str


@dataclass(frozen=True)
class ChapterSceneOutcome:
    scene_id: str
    body_hanzi: int
    rhythm: dict[str, object]
    incoming_handoff: tuple[str, ...]
    scene_delta: SceneDelta
    style_score: float | None = None


@dataclass(frozen=True)
class ChapterCheckpointIssue:
    code: str
    severity: str
    message: str
    scene_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChapterCheckpointEvaluation:
    chapter_id: str
    status: str
    scene_count: int
    target_hanzi: int
    actual_hanzi: int
    issues: tuple[ChapterCheckpointIssue, ...]
    revision_plan: tuple[str, ...]

    @property
    def may_continue(self) -> bool:
        return self.status != "revision-required"


class ChapterCheckpointService:
    def evaluate(
        self,
        bundle: ProjectPlanBundle,
        outcomes: tuple[ChapterSceneOutcome, ...],
    ) -> ChapterCheckpointEvaluation:
        issues = list(plan_bundle_issues(bundle))
        planned_ids = tuple(_scene_id(item.scene_ref) for item in bundle.chapter.scenes)
        by_id = {item.scene_id: item for item in outcomes}
        missing = tuple(scene_id for scene_id in planned_ids if scene_id not in by_id)
        if missing:
            issues.append(
                ChapterCheckpointIssue(
                    "missing-committed-scenes",
                    "blocking",
                    "chapter checkpoint is missing committed scene outcomes",
                    missing,
                )
            )

        ordered = tuple(by_id[scene_id] for scene_id in planned_ids if scene_id in by_id)
        actual = sum(max(0, item.body_hanzi) for item in ordered)
        _append_word_issues(issues, bundle.chapter.chapter_word_target, actual, planned_ids)
        _append_rhythm_issues(issues, ordered)
        _append_handoff_issues(issues, ordered)
        _append_obligation_issues(issues, bundle.chapter, ordered)
        _append_continuity_issues(issues, ordered)
        _append_style_issues(issues, ordered)

        status = (
            "revision-required"
            if any(item.severity == "blocking" for item in issues)
            else "needs-attention"
            if issues
            else "pass"
        )
        return ChapterCheckpointEvaluation(
            chapter_id=bundle.chapter.chapter_id,
            status=status,
            scene_count=len(ordered),
            target_hanzi=bundle.chapter.chapter_word_target,
            actual_hanzi=actual,
            issues=tuple(issues),
            revision_plan=tuple(_revision_instruction(item) for item in issues),
        )


def plan_bundle_issues(bundle: ProjectPlanBundle) -> tuple[ChapterCheckpointIssue, ...]:
    issues = [
        ChapterCheckpointIssue(item.code, "blocking", item.message)
        for item in chapter_facts_violations(
            bundle.chapter,
            mode=ChapterFactsValidationMode.PRODUCTION,
        )
    ]
    for name, value in (
        ("story-spine", bundle.story_spine_ref),
        ("word-budget", bundle.word_budget_ref),
        ("scene-inventory", bundle.scene_inventory_ref),
        ("obligation", bundle.obligation_ref),
    ):
        if not value.strip():
            issues.append(
                ChapterCheckpointIssue(
                    f"missing-{name}-ref",
                    "blocking",
                    f"ProjectPlanBundle requires {name} source reference",
                )
            )
    return tuple(issues)


def scene_outcome_from_transaction(
    transaction: SceneTransaction,
    *,
    rhythm: dict[str, object],
    style_score: float | None = None,
) -> ChapterSceneOutcome:
    if transaction.status is not SceneTransactionStatus.COMMITTED:
        raise ValueError("chapter outcomes require committed scene transactions")
    if transaction.creative_result is None or transaction.verification is None:
        raise ValueError("committed scene transaction is missing verified creative output")
    return ChapterSceneOutcome(
        scene_id=transaction.scene_id,
        body_hanzi=transaction.verification.body_hanzi,
        rhythm=dict(rhythm),
        incoming_handoff=transaction.brief.incoming_handoff,
        scene_delta=transaction.creative_result.scene_delta,
        style_score=style_score,
    )


def _append_word_issues(
    issues: list[ChapterCheckpointIssue],
    target: int,
    actual: int,
    scene_ids: tuple[str, ...],
) -> None:
    if target <= 0:
        return
    ratio = actual / target
    if ratio < 0.6:
        issues.append(
            ChapterCheckpointIssue(
                "severe-chapter-length-deficit",
                "blocking",
                f"chapter reached {ratio:.0%} of its Chinese-content target",
                scene_ids,
            )
        )
    elif ratio < 0.85:
        issues.append(
            ChapterCheckpointIssue(
                "chapter-length-deficit",
                "warning",
                f"chapter reached {ratio:.0%} of its Chinese-content target",
                scene_ids,
            )
        )
    elif ratio > 1.35:
        issues.append(
            ChapterCheckpointIssue(
                "chapter-length-overrun",
                "warning",
                f"chapter reached {ratio:.0%} of its Chinese-content target",
                scene_ids,
            )
        )


def _append_rhythm_issues(
    issues: list[ChapterCheckpointIssue],
    outcomes: tuple[ChapterSceneOutcome, ...],
) -> None:
    payload = analyze_narrative_rhythm_sequence(
        [{"scene_id": item.scene_id, **item.rhythm} for item in outcomes]
    )
    for item in payload.get("issues", []):
        if not isinstance(item, dict):
            continue
        issues.append(
            ChapterCheckpointIssue(
                str(item.get("code") or "rhythm-issue"),
                str(item.get("severity") or "warning"),
                str(item.get("message") or "chapter rhythm needs attention"),
                tuple(str(value) for value in item.get("scene_ids") or ()),
            )
        )


def _append_handoff_issues(
    issues: list[ChapterCheckpointIssue],
    outcomes: tuple[ChapterSceneOutcome, ...],
) -> None:
    for previous, current in zip(outcomes, outcomes[1:]):
        if previous.scene_delta.next_handoff and not current.incoming_handoff:
            issues.append(
                ChapterCheckpointIssue(
                    "missing-scene-handoff",
                    "warning",
                    "next scene does not declare how it receives the previous handoff",
                    (previous.scene_id, current.scene_id),
                )
            )


def _append_obligation_issues(
    issues: list[ChapterCheckpointIssue],
    facts: ChapterPlanningFacts,
    outcomes: tuple[ChapterSceneOutcome, ...],
) -> None:
    touched = {
        proposal.target_ref
        for outcome in outcomes
        for proposal in outcome.scene_delta.promise_updates
    }
    missing = tuple(item for item in facts.promise_obligation_ids if item not in touched)
    if missing:
        issues.append(
            ChapterCheckpointIssue(
                "untouched-chapter-promises",
                "warning",
                "planned chapter promises have no recorded progress: " + ", ".join(missing),
            )
        )


def _append_continuity_issues(
    issues: list[ChapterCheckpointIssue],
    outcomes: tuple[ChapterSceneOutcome, ...],
) -> None:
    for outcome in outcomes:
        missing = tuple(
            proposal.target_ref
            for proposal in outcome.scene_delta.continuity_changes
            if not proposal.evidence.strip()
        )
        if missing:
            issues.append(
                ChapterCheckpointIssue(
                    "continuity-change-without-evidence",
                    "warning",
                    "continuity changes need prose evidence before chapter close",
                    (outcome.scene_id,),
                )
            )


def _append_style_issues(
    issues: list[ChapterCheckpointIssue],
    outcomes: tuple[ChapterSceneOutcome, ...],
) -> None:
    scored = tuple(item for item in outcomes if item.style_score is not None)
    if len(scored) < 2:
        return
    values = [float(item.style_score) for item in scored if item.style_score is not None]
    if max(values) - min(values) > 0.25:
        issues.append(
            ChapterCheckpointIssue(
                "chapter-style-drift",
                "warning",
                "mounted-style adherence varies sharply across the chapter",
                tuple(item.scene_id for item in scored),
            )
        )


def _revision_instruction(issue: ChapterCheckpointIssue) -> str:
    scope = f" ({', '.join(issue.scene_ids)})" if issue.scene_ids else ""
    return f"[{issue.severity}] {issue.message}{scope}"


def _scene_id(reference: str) -> str:
    return Path(reference).stem or reference


__all__ = [
    "ChapterCheckpointEvaluation",
    "ChapterCheckpointIssue",
    "ChapterCheckpointService",
    "ChapterSceneOutcome",
    "ProjectPlanBundle",
    "plan_bundle_issues",
    "scene_outcome_from_transaction",
]
