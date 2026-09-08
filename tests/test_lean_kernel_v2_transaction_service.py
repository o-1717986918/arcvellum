from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.application.scene_transaction import (
    PreparedScene,
    SceneCommitReceipt,
    SceneTransactionService,
)
from literary_engineering_studio.persistence.scene_transactions import (
    SCENE_TRANSACTION_SCHEMA_SQL,
    SceneTransactionRepository,
)
from literary_engineering_studio.persistence.sqlite_uow import SqliteUnitOfWork
from literary_engineering_studio_engine.literary.scene.transaction import (
    CreativeResult,
    LengthTarget,
    ReviewDecision,
    ReviewResult,
    RhythmDirective,
    SceneBrief,
    SceneDelta,
    SceneExecutionMode,
    SceneRisk,
    SceneRiskLevel,
    SceneTransactionStatus,
    StyleMountRef,
)


def _brief(level: SceneRiskLevel = SceneRiskLevel.LOW) -> SceneBrief:
    return SceneBrief(
        scene_id="scene_0001",
        objective="主人公登上末班车",
        scene_function="decision-turn",
        participants=("character/protagonist",),
        canon_constraints=("末班车在午夜前离站",),
        incoming_handoff=("车票即将失效",),
        chapter_obligations=("推进离乡承诺",),
        rhythm=RhythmDirective("slow-to-fast", "selective"),
        length=LengthTarget(),
        style_mount=StyleMountRef("plain-flowing", "v1"),
        risk=SceneRisk(level),
    )


def _result(*, trace: bool = False) -> CreativeResult:
    return CreativeResult(
        prose="雨刚停。他把车票递过去，随后登上末班车。",
        decision_summary="用行动完成离乡决定。",
        scene_delta=SceneDelta(next_handoff=("有人叫出他的旧名",)),
        decision_trace=(("核对重大转向后选择直接行动",) if trace else ()),
    )


class _Briefs:
    def __init__(self, level: SceneRiskLevel):
        self.level = level

    def prepare(self, project_root, scene_id, mode):
        return PreparedScene(_brief(self.level), "revision-1")


class _Runtime:
    def __init__(self, *, trace: bool = False):
        self.trace = trace
        self.requests = 0
        self.generations = 0
        self.cache = {}

    def create_scene(self, transaction_id, brief):
        self.requests += 1
        if transaction_id not in self.cache:
            self.generations += 1
            self.cache[transaction_id] = _result(trace=self.trace)
        return self.cache[transaction_id]


class _Critic:
    def __init__(self, decision=ReviewDecision.PASS):
        self.decision = decision
        self.calls = 0
        self.cache = {}

    def review_scene(self, transaction_id, brief, result, verification):
        self.calls += 1
        self.cache.setdefault(
            transaction_id,
            ReviewResult(self.decision, "场景行为可信，转向清楚。"),
        )
        return self.cache[transaction_id]


class _Commits:
    def __init__(self, *, fail_after_apply_once: bool = False):
        self.fail_after_apply_once = fail_after_apply_once
        self.requests = 0
        self.applied = {}

    def commit(self, plan):
        self.requests += 1
        receipt = self.applied.setdefault(
            plan.transaction_id,
            SceneCommitReceipt(
                plan.transaction_id,
                plan.scene_id,
                "revision-2",
                (f"drafts/scenes/{plan.scene_id}.md",),
            ),
        )
        if self.fail_after_apply_once:
            self.fail_after_apply_once = False
            raise RuntimeError("injected crash after project apply")
        return receipt


class _Events:
    def __init__(self):
        self.events = []

    def emit(self, event, transaction):
        self.events.append((event, transaction.status.value))


class _FailFirstCreatedSave:
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.failed = False

    def insert(self, transaction):
        return self.wrapped.insert(transaction)

    def load(self, transaction_id):
        return self.wrapped.load(transaction_id)

    def save(self, transaction, *, expected_version):
        if transaction.status is SceneTransactionStatus.VERIFYING and not self.failed:
            self.failed = True
            raise RuntimeError("injected crash before result persistence")
        return self.wrapped.save(transaction, expected_version=expected_version)


class LeanKernelV2TransactionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.uow = SqliteUnitOfWork(self.root / "studio.db")
        with self.uow.write() as connection:
            connection.executescript(SCENE_TRANSACTION_SCHEMA_SQL)
        self.repository = SceneTransactionRepository(self.uow)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _service(self, level, *, runtime=None, critic=None, commits=None, repository=None):
        return SceneTransactionService(
            briefs=_Briefs(level),
            runtime=runtime or _Runtime(trace=level is SceneRiskLevel.HIGH),
            critic=critic,
            repository=repository or self.repository,
            commits=commits or _Commits(),
            events=_Events(),
            id_factory=lambda: "scene-tx-1",
        )

    def test_low_risk_happy_path_uses_one_writer_and_no_critic(self) -> None:
        runtime = _Runtime()
        critic = _Critic()
        service = self._service(SceneRiskLevel.LOW, runtime=runtime, critic=critic)

        transaction = service.prepare(self.root, "scene_0001")
        service.create(transaction.transaction_id)
        verified = service.verify(transaction.transaction_id)
        committed = service.commit(transaction.transaction_id)

        self.assertEqual(verified.status, SceneTransactionStatus.COMMITTABLE)
        self.assertEqual(committed.status, SceneTransactionStatus.COMMITTED)
        self.assertEqual(runtime.generations, 1)
        self.assertEqual(critic.calls, 0)

    def test_standard_risk_requires_one_independent_review(self) -> None:
        critic = _Critic()
        service = self._service(SceneRiskLevel.STANDARD, critic=critic)
        transaction = service.prepare(self.root, "scene_0001")

        service.create(transaction.transaction_id)
        verified = service.verify(transaction.transaction_id)
        reviewed = service.review_if_required(transaction.transaction_id)
        committed = service.commit(transaction.transaction_id)

        self.assertEqual(verified.status, SceneTransactionStatus.REVIEWING)
        self.assertEqual(reviewed.status, SceneTransactionStatus.COMMITTABLE)
        self.assertEqual(committed.status, SceneTransactionStatus.COMMITTED)
        self.assertEqual(critic.calls, 1)

    def test_high_risk_requires_steward_approval(self) -> None:
        service = self._service(SceneRiskLevel.HIGH, critic=_Critic())
        transaction = service.prepare(self.root, "scene_0001")
        service.create(transaction.transaction_id)
        service.verify(transaction.transaction_id)
        service.review_if_required(transaction.transaction_id)

        with self.assertRaisesRegex(ValueError, "steward approval is required"):
            service.commit(transaction.transaction_id)
        committed = service.commit(transaction.transaction_id, steward_approved=True)
        self.assertEqual(committed.status, SceneTransactionStatus.COMMITTED)

    def test_resume_reuses_runtime_result_after_persistence_interruption(self) -> None:
        runtime = _Runtime()
        repository = _FailFirstCreatedSave(self.repository)
        service = self._service(
            SceneRiskLevel.LOW,
            runtime=runtime,
            repository=repository,
        )
        transaction = service.prepare(self.root, "scene_0001")

        with self.assertRaisesRegex(RuntimeError, "before result persistence"):
            service.create(transaction.transaction_id)
        resumed = service.resume(transaction.transaction_id)
        created = service.create(transaction.transaction_id)

        self.assertEqual(resumed.status, SceneTransactionStatus.PREPARED)
        self.assertEqual(created.status, SceneTransactionStatus.VERIFYING)
        self.assertEqual(runtime.requests, 2)
        self.assertEqual(runtime.generations, 1)

    def test_commit_retry_does_not_apply_project_mutation_twice(self) -> None:
        commits = _Commits(fail_after_apply_once=True)
        service = self._service(SceneRiskLevel.LOW, commits=commits)
        transaction = service.prepare(self.root, "scene_0001")
        service.create(transaction.transaction_id)
        service.verify(transaction.transaction_id)

        with self.assertRaisesRegex(RuntimeError, "after project apply"):
            service.commit(transaction.transaction_id)
        service.resume(transaction.transaction_id)
        committed = service.commit(transaction.transaction_id)

        self.assertEqual(committed.status, SceneTransactionStatus.COMMITTED)
        self.assertEqual(len(commits.applied), 1)
        self.assertEqual(commits.requests, 2)

    def test_sqlite_round_trip_preserves_nested_contracts_and_version(self) -> None:
        service = self._service(SceneRiskLevel.STANDARD, critic=_Critic())
        transaction = service.prepare(self.root, "scene_0001")
        created = service.create(transaction.transaction_id)
        loaded = self.repository.load(transaction.transaction_id)

        self.assertEqual(loaded, created)
        self.assertGreater(loaded.version, 0)
        self.assertEqual(loaded.brief.style_mount.style_id, "plain-flowing")

    def test_repository_lists_project_transactions_for_read_models(self) -> None:
        service = self._service(SceneRiskLevel.LOW)
        transaction = service.prepare(self.root, "scene_0001")

        values = self.repository.list_for_project(str(self.root.resolve()))

        self.assertEqual([item.transaction_id for item in values], [transaction.transaction_id])


if __name__ == "__main__":
    unittest.main()
