"""One-state-at-a-time Autopilot coordinator for lean scene transactions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Protocol

from literary_engineering_studio_engine.public.projects import atomic_write_text
from literary_engineering_studio_engine.public.literary import (
    CreativeResult,
    ReviewDecision,
    SceneExecutionMode,
    SceneTransactionStatus,
    load_creative_quality_profile,
    load_scene_facts,
    load_scene_mapping,
)

from ..application.chapter_checkpoint import (
    ChapterCheckpointService,
    ProjectPlanBundle,
    checkpoint_digest,
    checkpoint_revision_digest_from_revisions,
    checkpoint_path,
    scene_outcome_from_transaction,
)
from ..application.scene_transaction import SceneTransactionService
from ..infrastructure.project_scene_transactions import known_scene_refs
from ..orchestration.chapter_facts_io import load_chapter_planning_facts


class RevisionRuntime(Protocol):
    def revise_scene(
        self,
        transaction_id,
        brief,
        result,
        verification,
        review,
        *,
        attempt: int,
    ) -> CreativeResult: ...


class RollingPlanner(Protocol):
    def expand_next_window(self, project_root: Path) -> bool: ...


@dataclass(frozen=True)
class LeanSceneStep:
    action: str
    scene_id: str = ""
    transaction_id: str = ""
    transaction_status: str = ""
    message: str = ""
    committed: bool = False
    route_ready: bool = False
    waiting_human: bool = False
    blocked: bool = False
    chapter_id: str = ""
    author_summary: dict[str, object] | None = None


class LeanSceneRunCoordinator:
    def __init__(
        self,
        *,
        project_root: Path,
        data_root: Path,
        service: SceneTransactionService,
        repository,
        revision_runtime: RevisionRuntime,
        checkpoints: ChapterCheckpointService | None = None,
        planning: RollingPlanner | None = None,
    ) -> None:
        self.project = project_root.expanduser().resolve()
        self.data_root = data_root.expanduser().resolve()
        self.service = service
        self.repository = repository
        self.revision_runtime = revision_runtime
        self.checkpoints = checkpoints or ChapterCheckpointService()
        self.planning = planning

    def advance_one(
        self,
        *,
        mode: SceneExecutionMode,
        steward_approved: bool,
    ) -> LeanSceneStep:
        checkpoint = self._next_chapter_checkpoint()
        if checkpoint is not None:
            return checkpoint
        scene_id = self._next_scene_id()
        if not scene_id:
            if self.planning is not None and self.planning.expand_next_window(self.project):
                return LeanSceneStep("planning-window", message="next chapter scene window prepared")
            return LeanSceneStep("route-ready", route_ready=True, message="all scenes committed")
        transaction = self.repository.latest_for_scene(str(self.project), scene_id)
        if transaction is None:
            transaction = self.service.prepare(self.project, scene_id, mode=mode)
            return self._step("prepared", transaction)
        return self.advance_transaction(
            transaction.transaction_id,
            steward_approved=steward_approved,
        )

    def advance_transaction(
        self,
        transaction_id: str,
        *,
        steward_approved: bool,
    ) -> LeanSceneStep:
        """Advance one exact transaction through the production state logic."""

        transaction = self.repository.load(transaction_id)
        status = transaction.status
        regular = self._regular_stage(transaction, status)
        if regular is not None:
            return regular
        if status is SceneTransactionStatus.REVISION_NEEDED:
            return self._revise(transaction)
        if status is SceneTransactionStatus.COMMITTABLE:
            return self._commit(transaction, steward_approved)
        if status is SceneTransactionStatus.BLOCKED:
            return self._resume_blocked(transaction)
        if status is SceneTransactionStatus.CANCELLED:
            return self._blocked(transaction, "scene transaction was cancelled")
        return self._blocked(transaction, f"unsupported scene transaction status: {status.value}")

    def _regular_stage(self, transaction, status: SceneTransactionStatus) -> LeanSceneStep | None:
        if status is SceneTransactionStatus.PREPARED:
            return self._step("created", self.service.create(transaction.transaction_id))
        if status is SceneTransactionStatus.CREATING:
            return self._step("resumed", self.service.resume(transaction.transaction_id))
        if status is SceneTransactionStatus.VERIFYING:
            verified = self.service.verify(
                transaction.transaction_id,
                known_refs=known_scene_refs(transaction.brief),
                quality_profile=load_creative_quality_profile(self.project),
            )
            return self._step("verified", verified)
        if status is SceneTransactionStatus.REVIEWING:
            return self._step("reviewed", self.service.review_if_required(transaction.transaction_id))
        return None

    def _revise(self, transaction) -> LeanSceneStep:
        if transaction.creative_result is None or transaction.verification is None:
            return self._blocked(transaction, "revision inputs are incomplete")
        try:
            revised = self.revision_runtime.revise_scene(
                transaction.transaction_id,
                transaction.brief,
                transaction.creative_result,
                transaction.verification,
                transaction.review,
                attempt=transaction.revision_attempts + 1,
            )
            accepted = self.service.accept_revision(transaction.transaction_id, revised)
        except Exception as exc:
            return self._blocked(transaction, str(exc))
        return self._step("revised", accepted)

    def _commit(self, transaction, steward_approved: bool) -> LeanSceneStep:
        if transaction.policy.steward_approval_required and not steward_approved:
            return LeanSceneStep(
                "approval-required",
                scene_id=transaction.scene_id,
                transaction_id=transaction.transaction_id,
                transaction_status=transaction.status.value,
                message="high-risk scene commit requires delegated or human approval",
                waiting_human=True,
            )
        committed = self.service.commit(
            transaction.transaction_id,
            steward_approved=steward_approved,
        )
        return self._step("committed", committed, committed=True)

    def _resume_blocked(self, transaction) -> LeanSceneStep:
        if transaction.review is not None and transaction.review.decision is ReviewDecision.ESCALATE:
            return self._blocked(transaction, transaction.last_error or "review escalated")
        if "scene source revision changed:" in transaction.last_error:
            refreshed = self.service.prepare(
                self.project,
                transaction.scene_id,
                mode=transaction.mode,
            )
            return self._step("reprepared", refreshed)
        return self._step("resumed", self.service.resume(transaction.transaction_id))

    def _next_scene_id(self) -> str:
        for scene_id in self._ordered_scene_ids():
            if (self.project / "workflow" / "scene_commits" / f"{scene_id}.json").is_file():
                continue
            if (self.project / "drafts" / "scenes" / f"{scene_id}.md").is_file():
                continue
            return scene_id
        return ""

    def _ordered_scene_ids(self) -> tuple[str, ...]:
        rows: list[tuple[float, str]] = []
        for path in sorted((self.project / "scenes").glob("*.yaml")):
            facts = load_scene_facts(path)
            order = float(facts.timeline_order) if facts.timeline_order is not None else float("inf")
            rows.append((order, facts.scene_id))
        return tuple(scene_id for _, scene_id in sorted(rows, key=lambda item: (item[0], item[1])))

    def _next_chapter_checkpoint(self) -> LeanSceneStep | None:
        for chapter_id, scene_ids in self._chapter_scene_ids().items():
            transactions = self._committed_chapter_transactions(scene_ids)
            if transactions is None:
                continue
            facts = load_chapter_planning_facts(self.project, chapter_id)
            revisions = [
                item.commit_receipt.committed_revision
                for item in transactions
                if item is not None and item.commit_receipt is not None
            ]
            revision_digest = checkpoint_revision_digest_from_revisions(revisions)
            digest = checkpoint_digest(transactions, facts)
            target = checkpoint_path(self.data_root, self.project, chapter_id)
            current = _read_json(target)
            if current.get("committed_revision_digest") == revision_digest:
                if current.get("status") == "revision-required":
                    return self._existing_blocked_checkpoint(chapter_id, current)
                continue
            return self._evaluate_chapter_checkpoint(
                chapter_id, facts, transactions, target, digest, revision_digest,
            )
        return None

    def _chapter_scene_ids(self) -> dict[str, list[str]]:
        chapters: dict[str, list[str]] = {}
        for scene_id in self._ordered_scene_ids():
            facts = load_scene_facts(self.project / "scenes" / f"{scene_id}.yaml")
            chapters.setdefault(facts.chapter_id or "unassigned", []).append(scene_id)
        return chapters

    def _committed_chapter_transactions(self, scene_ids: list[str]):
        transactions = [
            self.repository.latest_for_scene(str(self.project), scene_id)
            for scene_id in scene_ids
        ]
        if not transactions or any(
            item is None or item.status is not SceneTransactionStatus.COMMITTED
            for item in transactions
        ):
            return None
        return transactions

    @staticmethod
    def _existing_blocked_checkpoint(chapter_id: str, current: dict[str, object]) -> LeanSceneStep:
        summary = current.get("author_summary")
        return LeanSceneStep(
            "chapter-blocked",
            message=str(current.get("summary") or "chapter checkpoint requires revision"),
            blocked=True,
            chapter_id=chapter_id,
            author_summary=summary if isinstance(summary, dict) else None,
        )

    def _evaluate_chapter_checkpoint(
        self, chapter_id, facts, transactions, target, digest, revision_digest,
    ) -> LeanSceneStep:
        bundle = ProjectPlanBundle(
            chapter=facts,
            story_spine_ref="plot/story_architecture.candidate.json",
            word_budget_ref="plot/word_budget/word_budget.json",
            scene_inventory_ref="plot/candidates/scenes/word_budget_scene_inventory.md",
            obligation_ref=f"plot/chapter_obligations/{chapter_id}.json",
        )
        outcomes = tuple(
            scene_outcome_from_transaction(item, rhythm=self._chapter_rhythm(item))
            for item in transactions
            if item is not None
        )
        evaluation = self.checkpoints.evaluate(bundle, outcomes)
        summary = evaluation.revision_plan[0] if evaluation.revision_plan else str(
            evaluation.author_summary.get("irreversible_change") or "本章已完成并通过检查点"
        )
        payload = {
            "schema": "arcvellum/chapter-checkpoint/v2",
            "input_digest": digest,
            "committed_revision_digest": revision_digest,
            **asdict(evaluation),
            "summary": summary,
        }
        atomic_write_text(target, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return LeanSceneStep(
            "chapter-checkpoint",
            message=summary,
            blocked=not evaluation.may_continue,
            chapter_id=chapter_id,
            author_summary=evaluation.author_summary,
        )

    def _chapter_rhythm(self, transaction) -> dict[str, object]:
        mapping = load_scene_mapping(
            self.project / "scenes" / f"{transaction.scene_id}.yaml"
        )
        value = mapping.get("narrative_rhythm")
        formal = value if isinstance(value, dict) else {}
        curve = formal.get("tension_curve")
        return {
            "pace": transaction.brief.rhythm.pace,
            "rhythm_role": str(formal.get("rhythm_role") or ""),
            "scene_function": transaction.brief.scene_function,
            "scene_turn": transaction.brief.rhythm.scene_turn,
            "reader_effect": transaction.brief.rhythm.reader_effect,
            "tension_curve": dict(curve) if isinstance(curve, dict) else {},
        }

    @staticmethod
    def _step(action, transaction, *, committed: bool = False) -> LeanSceneStep:
        return LeanSceneStep(
            action,
            scene_id=transaction.scene_id,
            transaction_id=transaction.transaction_id,
            transaction_status=transaction.status.value,
            message=transaction.last_error,
            committed=committed,
        )

    @staticmethod
    def _blocked(transaction, message: str) -> LeanSceneStep:
        return LeanSceneStep(
            "blocked",
            scene_id=transaction.scene_id,
            transaction_id=transaction.transaction_id,
            transaction_status=transaction.status.value,
            message=message,
            blocked=True,
        )


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


__all__ = ["LeanSceneRunCoordinator", "LeanSceneStep"]
