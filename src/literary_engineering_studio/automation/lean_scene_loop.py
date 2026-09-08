"""One-state-at-a-time Autopilot coordinator for lean scene transactions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Protocol

from literary_engineering_studio_engine.foundation.atomic_io import atomic_write_text
from literary_engineering_studio_engine.literary.scene.facts import (
    load_scene_facts,
    load_scene_mapping,
)
from literary_engineering_studio_engine.literary.scene.transaction import (
    CreativeResult,
    ReviewDecision,
    SceneExecutionMode,
    SceneTransactionStatus,
)

from ..application.chapter_checkpoint import (
    ChapterCheckpointService,
    ProjectPlanBundle,
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
    ) -> None:
        self.project = project_root.expanduser().resolve()
        self.data_root = data_root.expanduser().resolve()
        self.service = service
        self.repository = repository
        self.revision_runtime = revision_runtime
        self.checkpoints = checkpoints or ChapterCheckpointService()

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
        scene_id = transaction.scene_id
        status = transaction.status
        if status is SceneTransactionStatus.PREPARED:
            return self._step("created", self.service.create(transaction.transaction_id))
        if status is SceneTransactionStatus.CREATING:
            return self._step("resumed", self.service.resume(transaction.transaction_id))
        if status is SceneTransactionStatus.VERIFYING:
            return self._step(
                "verified",
                self.service.verify(
                    transaction.transaction_id,
                    known_refs=known_scene_refs(transaction.brief),
                ),
            )
        if status is SceneTransactionStatus.REVIEWING:
            return self._step("reviewed", self.service.review_if_required(transaction.transaction_id))
        if status is SceneTransactionStatus.REVISION_NEEDED:
            if transaction.creative_result is None or transaction.verification is None:
                return self._blocked(transaction, "revision inputs are incomplete")
            if transaction.revision_attempts >= transaction.policy.max_revision_attempts:
                return self._blocked(transaction, "automatic scene revision budget is exhausted")
            revised = self.revision_runtime.revise_scene(
                transaction.transaction_id,
                transaction.brief,
                transaction.creative_result,
                transaction.verification,
                transaction.review,
                attempt=transaction.revision_attempts + 1,
            )
            return self._step(
                "revised",
                self.service.accept_revision(transaction.transaction_id, revised),
            )
        if status is SceneTransactionStatus.COMMITTABLE:
            if transaction.policy.steward_approval_required and not steward_approved:
                return LeanSceneStep(
                    "approval-required",
                    scene_id=scene_id,
                    transaction_id=transaction.transaction_id,
                    transaction_status=status.value,
                    message="high-risk scene commit requires delegated or human approval",
                    waiting_human=True,
                )
            committed = self.service.commit(
                transaction.transaction_id,
                steward_approved=steward_approved,
            )
            return self._step("committed", committed, committed=True)
        if status is SceneTransactionStatus.BLOCKED:
            if transaction.review is not None and transaction.review.decision is ReviewDecision.ESCALATE:
                return self._blocked(transaction, transaction.last_error or "review escalated")
            return self._step("resumed", self.service.resume(transaction.transaction_id))
        if status is SceneTransactionStatus.CANCELLED:
            return self._blocked(transaction, "scene transaction was cancelled")
        return self._blocked(transaction, f"unsupported scene transaction status: {status.value}")

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
        chapters: dict[str, list[str]] = {}
        for scene_id in self._ordered_scene_ids():
            facts = load_scene_facts(self.project / "scenes" / f"{scene_id}.yaml")
            chapters.setdefault(facts.chapter_id or "unassigned", []).append(scene_id)
        for chapter_id, scene_ids in chapters.items():
            transactions = [
                self.repository.latest_for_scene(str(self.project), item)
                for item in scene_ids
            ]
            if not transactions or any(
                item is None or item.status is not SceneTransactionStatus.COMMITTED
                for item in transactions
            ):
                continue
            digest = _checkpoint_digest(transactions)
            target = self._checkpoint_path(chapter_id)
            current = _read_json(target)
            if current.get("input_digest") == digest:
                if current.get("status") == "revision-required":
                    return LeanSceneStep(
                        "chapter-blocked",
                        message=str(current.get("summary") or "chapter checkpoint requires revision"),
                        blocked=True,
                    )
                continue
            facts = load_chapter_planning_facts(self.project, chapter_id)
            bundle = ProjectPlanBundle(
                chapter=facts,
                story_spine_ref="plot/story_architecture.candidate.json",
                word_budget_ref="plot/word_budget/word_budget.json",
                scene_inventory_ref="plot/candidates/scenes/word_budget_scene_inventory.md",
                obligation_ref=f"plot/chapter_obligations/{chapter_id}.json",
            )
            outcomes = tuple(
                scene_outcome_from_transaction(
                    item,
                    rhythm=self._chapter_rhythm(item),
                )
                for item in transactions
                if item is not None
            )
            evaluation = self.checkpoints.evaluate(bundle, outcomes)
            summary = (
                evaluation.revision_plan[0]
                if evaluation.revision_plan
                else "chapter checkpoint passed"
            )
            payload = {
                "schema": "arcvellum/chapter-checkpoint/v2",
                "input_digest": digest,
                **asdict(evaluation),
                "summary": summary,
            }
            atomic_write_text(
                target,
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            )
            return LeanSceneStep(
                "chapter-checkpoint",
                message=summary,
                blocked=not evaluation.may_continue,
            )
        return None

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

    def _checkpoint_path(self, chapter_id: str) -> Path:
        project_id = hashlib.sha256(str(self.project).encode("utf-8")).hexdigest()[:16]
        return (
            self.data_root
            / "lean-kernel"
            / project_id
            / "chapter-checkpoints"
            / f"{chapter_id}.json"
        )

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


def _checkpoint_digest(transactions) -> str:
    values = [
        item.commit_receipt.committed_revision
        for item in transactions
        if item is not None and item.commit_receipt is not None
    ]
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


__all__ = ["LeanSceneRunCoordinator", "LeanSceneStep"]
