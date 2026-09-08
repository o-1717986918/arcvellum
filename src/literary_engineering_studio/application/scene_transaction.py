"""Application service for the lean scene-transaction lifecycle."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

from literary_engineering_studio_engine.public.literary import (
    CreativeResult,
    ReviewDecision,
    ReviewResult,
    SceneBrief,
    SceneExecutionMode,
    ScenePolicy,
    SceneTransactionStatus,
    VerificationReport,
    SceneCommitPlan,
    build_scene_commit_plan,
    derive_scene_policy,
    scene_brief_issues,
    verify_creative_result,
)


@dataclass(frozen=True)
class PreparedScene:
    brief: SceneBrief
    base_revision: str


@dataclass(frozen=True)
class SceneCommitReceipt:
    transaction_id: str
    scene_id: str
    committed_revision: str
    written_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class SceneTransaction:
    transaction_id: str
    project_root: str
    scene_id: str
    mode: SceneExecutionMode
    status: SceneTransactionStatus
    base_revision: str
    brief: SceneBrief
    policy: ScenePolicy
    creative_result: CreativeResult | None = None
    verification: VerificationReport | None = None
    review: ReviewResult | None = None
    commit_receipt: SceneCommitReceipt | None = None
    revision_attempts: int = 0
    blocked_from: str = ""
    last_error: str = ""
    version: int = 0

    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))


class SceneBriefProvider(Protocol):
    def prepare(
        self,
        project_root: Path,
        scene_id: str,
        mode: SceneExecutionMode,
    ) -> PreparedScene: ...


class CreativeRuntime(Protocol):
    def create_scene(
        self,
        transaction_id: str,
        brief: SceneBrief,
    ) -> CreativeResult: ...


class CriticRuntime(Protocol):
    def review_scene(
        self,
        transaction_id: str,
        brief: SceneBrief,
        result: CreativeResult,
        verification: VerificationReport,
    ) -> ReviewResult: ...


class SceneTransactionRepository(Protocol):
    def insert(self, transaction: SceneTransaction) -> SceneTransaction: ...

    def load(self, transaction_id: str) -> SceneTransaction: ...

    def save(
        self,
        transaction: SceneTransaction,
        *,
        expected_version: int,
    ) -> SceneTransaction: ...


class ProjectCommitPort(Protocol):
    def commit(self, plan: SceneCommitPlan) -> SceneCommitReceipt: ...


class TransactionEventSink(Protocol):
    def emit(self, event: str, transaction: SceneTransaction) -> None: ...


class _NullEventSink:
    def emit(self, event: str, transaction: SceneTransaction) -> None:
        return None


class SceneTransactionService:
    """Advance one scene while preserving completed work across retries."""

    def __init__(
        self,
        *,
        briefs: SceneBriefProvider,
        runtime: CreativeRuntime,
        repository: SceneTransactionRepository,
        commits: ProjectCommitPort,
        critic: CriticRuntime | None = None,
        events: TransactionEventSink | None = None,
        id_factory: Callable[[], str] | None = None,
    ):
        self._briefs = briefs
        self._runtime = runtime
        self._repository = repository
        self._commits = commits
        self._critic = critic
        self._events = events or _NullEventSink()
        self._id_factory = id_factory or (lambda: f"scene-tx-{uuid4().hex}")

    def prepare(
        self,
        project_root: Path,
        scene_id: str,
        *,
        mode: SceneExecutionMode = SceneExecutionMode.STANDARD,
    ) -> SceneTransaction:
        prepared = self._briefs.prepare(project_root, scene_id, mode)
        problems = scene_brief_issues(prepared.brief)
        if problems:
            raise ValueError("invalid scene brief: " + "; ".join(problems))
        transaction = SceneTransaction(
            transaction_id=self._id_factory(),
            project_root=str(project_root.resolve()),
            scene_id=prepared.brief.scene_id,
            mode=mode,
            status=SceneTransactionStatus.PREPARED,
            base_revision=prepared.base_revision,
            brief=prepared.brief,
            policy=derive_scene_policy(mode=mode, risk=prepared.brief.risk),
        )
        saved = self._repository.insert(transaction)
        self._emit("scene.prepared", saved)
        return saved

    def create(self, transaction_id: str) -> SceneTransaction:
        current = self._repository.load(transaction_id)
        if current.creative_result is not None:
            return current
        self._require_status(current, SceneTransactionStatus.PREPARED)
        creating = self._store(current, status=SceneTransactionStatus.CREATING)
        try:
            result = self._runtime.create_scene(creating.transaction_id, creating.brief)
        except Exception as exc:
            self._block(creating, SceneTransactionStatus.CREATING, exc)
            raise
        saved = self._store(
            creating,
            status=SceneTransactionStatus.VERIFYING,
            creative_result=result,
            last_error="",
            blocked_from="",
        )
        self._emit("scene.created", saved)
        return saved

    def verify(
        self,
        transaction_id: str,
        *,
        known_refs: Collection[str] = (),
    ) -> SceneTransaction:
        current = self._repository.load(transaction_id)
        if current.verification is not None:
            return current
        self._require_status(current, SceneTransactionStatus.VERIFYING)
        if current.creative_result is None:
            raise ValueError("creative result is missing")
        try:
            report = verify_creative_result(
                current.brief,
                current.creative_result,
                current.policy,
                known_refs=known_refs,
            )
        except Exception as exc:
            self._block(current, SceneTransactionStatus.VERIFYING, exc)
            raise
        if not report.can_commit:
            status = SceneTransactionStatus.REVISION_NEEDED
        elif self._review_required(current):
            status = SceneTransactionStatus.REVIEWING
        else:
            status = SceneTransactionStatus.COMMITTABLE
        saved = self._store(current, status=status, verification=report)
        self._emit("scene.verified", saved)
        return saved

    def review_if_required(self, transaction_id: str) -> SceneTransaction:
        current = self._repository.load(transaction_id)
        if current.review is not None:
            return current
        if not self._review_required(current):
            if current.status is SceneTransactionStatus.VERIFYING:
                return self._store(current, status=SceneTransactionStatus.COMMITTABLE)
            return current
        self._require_status(current, SceneTransactionStatus.REVIEWING)
        if self._critic is None:
            raise RuntimeError("scene review is required but no critic runtime is configured")
        if current.creative_result is None or current.verification is None:
            raise ValueError("review requires creative result and verification")
        try:
            review = self._critic.review_scene(
                current.transaction_id,
                current.brief,
                current.creative_result,
                current.verification,
            )
        except Exception as exc:
            self._block(current, SceneTransactionStatus.REVIEWING, exc)
            raise
        status = {
            ReviewDecision.PASS: SceneTransactionStatus.COMMITTABLE,
            ReviewDecision.REVISE: SceneTransactionStatus.REVISION_NEEDED,
            ReviewDecision.ESCALATE: SceneTransactionStatus.BLOCKED,
        }[review.decision]
        saved = self._store(
            current,
            status=status,
            review=review,
            blocked_from=(SceneTransactionStatus.REVIEWING.value if status is SceneTransactionStatus.BLOCKED else ""),
            last_error=(review.summary if status is SceneTransactionStatus.BLOCKED else ""),
        )
        self._emit("scene.reviewed", saved)
        return saved

    def accept_revision(
        self,
        transaction_id: str,
        result: CreativeResult,
    ) -> SceneTransaction:
        current = self._repository.load(transaction_id)
        self._require_status(current, SceneTransactionStatus.REVISION_NEEDED)
        if current.revision_attempts >= current.policy.max_revision_attempts:
            raise ValueError("automatic scene revision budget is exhausted")
        saved = self._store(
            current,
            status=SceneTransactionStatus.VERIFYING,
            creative_result=result,
            verification=None,
            review=None,
            revision_attempts=current.revision_attempts + 1,
            blocked_from="",
            last_error="",
        )
        self._emit("scene.revised", saved)
        return saved

    def commit(
        self,
        transaction_id: str,
        *,
        steward_approved: bool = False,
    ) -> SceneTransaction:
        current = self._repository.load(transaction_id)
        if current.status is SceneTransactionStatus.COMMITTED:
            return current
        self._require_status(current, SceneTransactionStatus.COMMITTABLE)
        if current.creative_result is None or current.verification is None:
            raise ValueError("commit requires creative result and verification")
        plan = build_scene_commit_plan(
            transaction_id=current.transaction_id,
            base_revision=current.base_revision,
            result=current.creative_result,
            verification=current.verification,
            policy=current.policy,
            review=current.review,
            steward_approved=steward_approved,
        )
        try:
            receipt = self._commits.commit(plan)
        except Exception as exc:
            self._block(current, SceneTransactionStatus.COMMITTABLE, exc)
            raise
        saved = self._store(
            current,
            status=SceneTransactionStatus.COMMITTED,
            commit_receipt=receipt,
            blocked_from="",
            last_error="",
        )
        self._emit("scene.committed", saved)
        return saved

    def resume(self, transaction_id: str) -> SceneTransaction:
        current = self._repository.load(transaction_id)
        if current.status is SceneTransactionStatus.CREATING:
            recovery = (
                SceneTransactionStatus.VERIFYING
                if current.creative_result is not None
                else SceneTransactionStatus.PREPARED
            )
            saved = self._store(current, status=recovery, blocked_from="", last_error="")
            self._emit("scene.resumed", saved)
            return saved
        if current.status is not SceneTransactionStatus.BLOCKED:
            return current
        recovery = {
            SceneTransactionStatus.CREATING.value: SceneTransactionStatus.PREPARED,
            SceneTransactionStatus.VERIFYING.value: SceneTransactionStatus.VERIFYING,
            SceneTransactionStatus.REVIEWING.value: SceneTransactionStatus.REVIEWING,
            SceneTransactionStatus.COMMITTABLE.value: SceneTransactionStatus.COMMITTABLE,
        }.get(current.blocked_from)
        if recovery is None:
            return current
        saved = self._store(current, status=recovery, blocked_from="", last_error="")
        self._emit("scene.resumed", saved)
        return saved

    def _review_required(self, transaction: SceneTransaction) -> bool:
        return transaction.policy.independent_review_required or bool(
            transaction.creative_result and transaction.creative_result.escalation_reasons
        )

    def _block(
        self,
        transaction: SceneTransaction,
        stage: SceneTransactionStatus,
        error: Exception,
    ) -> SceneTransaction:
        saved = self._store(
            transaction,
            status=SceneTransactionStatus.BLOCKED,
            blocked_from=stage.value,
            last_error=str(error),
        )
        self._emit("scene.blocked", saved)
        return saved

    def _store(self, transaction: SceneTransaction, **changes: Any) -> SceneTransaction:
        candidate = replace(transaction, **changes)
        return self._repository.save(candidate, expected_version=transaction.version)

    def _emit(self, event: str, transaction: SceneTransaction) -> None:
        try:
            self._events.emit(event, transaction)
        except Exception:
            pass

    @staticmethod
    def _require_status(
        transaction: SceneTransaction,
        expected: SceneTransactionStatus,
    ) -> None:
        if transaction.status is not expected:
            raise ValueError(
                f"scene transaction {transaction.transaction_id} is {transaction.status.value}; "
                f"expected {expected.value}"
            )


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


__all__ = [
    "CreativeRuntime",
    "CriticRuntime",
    "PreparedScene",
    "ProjectCommitPort",
    "SceneBriefProvider",
    "SceneCommitReceipt",
    "SceneTransaction",
    "SceneTransactionRepository",
    "SceneTransactionService",
    "TransactionEventSink",
]
