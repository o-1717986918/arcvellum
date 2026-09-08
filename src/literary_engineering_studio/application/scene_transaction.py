"""Application service for the lean scene-transaction lifecycle."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

from literary_engineering_studio_engine.literary.scene.transaction import (
    ChangeProposal,
    CreativeResult,
    IssueSeverity,
    LengthTarget,
    ReviewDecision,
    ReviewResult,
    RhythmDirective,
    SceneBrief,
    SceneDelta,
    SceneExecutionMode,
    ScenePolicy,
    SceneRisk,
    SceneRiskLevel,
    SceneTransactionStatus,
    StyleMountRef,
    VerificationIssue,
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


def scene_transaction_from_dict(payload: dict[str, Any]) -> SceneTransaction:
    brief_data = dict(payload["brief"])
    risk_data = dict(brief_data["risk"])
    brief = SceneBrief(
        scene_id=str(brief_data["scene_id"]),
        objective=str(brief_data["objective"]),
        scene_function=str(brief_data["scene_function"]),
        participants=tuple(brief_data.get("participants") or ()),
        canon_constraints=tuple(brief_data.get("canon_constraints") or ()),
        incoming_handoff=tuple(brief_data.get("incoming_handoff") or ()),
        chapter_obligations=tuple(brief_data.get("chapter_obligations") or ()),
        rhythm=RhythmDirective(**dict(brief_data.get("rhythm") or {})),
        length=LengthTarget(**dict(brief_data.get("length") or {})),
        style_mount=StyleMountRef(**dict(brief_data.get("style_mount") or {})),
        risk=SceneRisk(
            SceneRiskLevel(str(risk_data["level"])),
            tuple(risk_data.get("reasons") or ()),
        ),
        source_refs=tuple(brief_data.get("source_refs") or ()),
        viewpoint=str(brief_data.get("viewpoint") or ""),
        location=str(brief_data.get("location") or ""),
        external_conflict=str(brief_data.get("external_conflict") or ""),
        internal_conflict=str(brief_data.get("internal_conflict") or ""),
    )
    policy_data = dict(payload["policy"])
    policy_risk = dict(policy_data["risk"])
    policy = ScenePolicy(
        mode=SceneExecutionMode(str(policy_data["mode"])),
        risk=SceneRisk(
            SceneRiskLevel(str(policy_risk["level"])),
            tuple(policy_risk.get("reasons") or ()),
        ),
        independent_review_required=bool(policy_data["independent_review_required"]),
        explicit_decision_trace_required=bool(policy_data["explicit_decision_trace_required"]),
        defer_semantic_review_to_chapter=bool(policy_data["defer_semantic_review_to_chapter"]),
        automatic_revision_allowed=bool(policy_data["automatic_revision_allowed"]),
        max_revision_attempts=int(policy_data["max_revision_attempts"]),
        steward_approval_required=bool(policy_data["steward_approval_required"]),
    )
    return SceneTransaction(
        transaction_id=str(payload["transaction_id"]),
        project_root=str(payload["project_root"]),
        scene_id=str(payload["scene_id"]),
        mode=SceneExecutionMode(str(payload["mode"])),
        status=SceneTransactionStatus(str(payload["status"])),
        base_revision=str(payload["base_revision"]),
        brief=brief,
        policy=policy,
        creative_result=_creative_result(payload.get("creative_result")),
        verification=_verification(payload.get("verification")),
        review=_review(payload.get("review")),
        commit_receipt=_receipt(payload.get("commit_receipt")),
        revision_attempts=int(payload.get("revision_attempts") or 0),
        blocked_from=str(payload.get("blocked_from") or ""),
        last_error=str(payload.get("last_error") or ""),
        version=int(payload.get("version") or 0),
    )


def _creative_result(value: Any) -> CreativeResult | None:
    if not isinstance(value, dict):
        return None
    delta = dict(value.get("scene_delta") or {})
    return CreativeResult(
        prose=str(value.get("prose") or ""),
        decision_summary=str(value.get("decision_summary") or ""),
        scene_delta=SceneDelta(
            character_changes=_proposals(delta.get("character_changes")),
            canon_candidates=_proposals(delta.get("canon_candidates")),
            continuity_changes=_proposals(delta.get("continuity_changes")),
            promise_updates=_proposals(delta.get("promise_updates")),
            reader_question_updates=_proposals(delta.get("reader_question_updates")),
            next_handoff=tuple(delta.get("next_handoff") or ()),
            new_asset_candidates=_proposals(delta.get("new_asset_candidates")),
        ),
        decision_trace=tuple(value.get("decision_trace") or ()),
        escalation_reasons=tuple(value.get("escalation_reasons") or ()),
    )


def _proposals(value: Any) -> tuple[ChangeProposal, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        ChangeProposal(
            target_ref=str(item.get("target_ref") or ""),
            summary=str(item.get("summary") or ""),
            evidence=str(item.get("evidence") or ""),
            operation=str(item.get("operation") or "update"),
            attributes=tuple(tuple(pair) for pair in item.get("attributes") or ()),
        )
        for item in value
        if isinstance(item, dict)
    )


def _verification(value: Any) -> VerificationReport | None:
    if not isinstance(value, dict):
        return None
    return VerificationReport(
        scene_id=str(value.get("scene_id") or ""),
        body_hanzi=int(value.get("body_hanzi") or 0),
        issues=tuple(
            VerificationIssue(
                code=str(item.get("code") or ""),
                severity=IssueSeverity(str(item.get("severity") or "warning")),
                message=str(item.get("message") or ""),
                evidence=str(item.get("evidence") or ""),
            )
            for item in value.get("issues") or ()
            if isinstance(item, dict)
        ),
    )


def _review(value: Any) -> ReviewResult | None:
    if not isinstance(value, dict):
        return None
    return ReviewResult(
        decision=ReviewDecision(str(value.get("decision") or "pass")),
        summary=str(value.get("summary") or ""),
        revision_instructions=tuple(value.get("revision_instructions") or ()),
        evidence=tuple(value.get("evidence") or ()),
    )


def _receipt(value: Any) -> SceneCommitReceipt | None:
    if not isinstance(value, dict):
        return None
    return SceneCommitReceipt(
        transaction_id=str(value.get("transaction_id") or ""),
        scene_id=str(value.get("scene_id") or ""),
        committed_revision=str(value.get("committed_revision") or ""),
        written_refs=tuple(value.get("written_refs") or ()),
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
    "scene_transaction_from_dict",
]
