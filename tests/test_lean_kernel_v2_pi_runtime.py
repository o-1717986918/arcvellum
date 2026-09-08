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
from literary_engineering_studio.runtime.role_conversation import RoleConversationResult
from literary_engineering_studio.runtimes.pi_scene_transaction import (
    PiSceneTransactionRuntime,
    creative_result_from_payload,
    render_scene_create_prompt,
)
from literary_engineering_studio_engine.literary.scene.transaction import (
    CreativeResult,
    LengthTarget,
    RhythmDirective,
    SceneBrief,
    SceneExecutionMode,
    SceneRisk,
    SceneRiskLevel,
    SceneDelta,
    SceneTransactionStatus,
    StyleMountRef,
    VerificationReport,
)


def _brief(source_refs=()) -> SceneBrief:
    return SceneBrief(
        scene_id="scene_0001",
        objective="主人公承认自己拿走了信",
        scene_function="relationship-turn",
        participants=("character/protagonist", "character/sister"),
        canon_constraints=("信在昨夜被取走",),
        incoming_handoff=("妹妹已经发现抽屉被打开",),
        chapter_obligations=("本章必须改变兄妹之间的信任",),
        rhythm=RhythmDirective("slow-to-fast", "selective", "隐瞒转为承认", "不安"),
        length=LengthTarget(800, 600, 1100),
        style_mount=StyleMountRef("plain-flowing", "v1"),
        risk=SceneRisk(SceneRiskLevel.STANDARD, ("relationship-state-change",)),
        source_refs=tuple(source_refs),
    )


class _Gateway:
    def __init__(self):
        self.calls = []

    def run(self, workspace, prompt, *, role, timeout, event_sink=None, cancel_event=None):
        self.calls.append((role, prompt))
        if event_sink is not None:
            event_sink("agent.message.delta", {"text": "{"})
        if role == "reviewer":
            answer = (
                '{"decision":"pass","summary":"承认行为改变了关系压力",'
                '"revision_instructions":[],"evidence":["她把信放回桌上"]}'
            )
        else:
            answer = (
                '{"prose":"她把信放回桌上，说是自己拿的。妹妹没有接话。",'
                '"decision_summary":"用承认改变关系。","scene_delta":{'
                '"character_changes":[{"target_ref":"character/protagonist",'
                '"summary":"承认取信","evidence":"说是自己拿的",'
                '"attributes":{"trust":"lower"}}],"next_handoff":["妹妹保持沉默"]},'
                '"decision_trace":[],"escalation_reasons":[]}'
            )
        return RoleConversationResult("pi-worker", "run-1", "test/model", answer)


class _BriefProvider:
    def __init__(self, brief):
        self.brief = brief

    def prepare(self, project_root, scene_id, mode):
        return PreparedScene(self.brief, "revision-1")


class _CommitPort:
    def commit(self, plan):
        return SceneCommitReceipt(plan.transaction_id, plan.scene_id, "revision-2")


class LeanKernelV2PiRuntimeTests(unittest.TestCase):
    def test_prompt_is_compact_and_contains_no_legacy_lifecycle_manual(self) -> None:
        prompt = render_scene_create_prompt(_brief())

        self.assertLess(len(prompt), 4_000)
        self.assertNotIn("SKILL.md", prompt)
        self.assertNotIn("task-submit", prompt)
        self.assertNotIn("expected_outputs", prompt)
        self.assertIn("SceneBrief", prompt)

    def test_parser_rejects_studio_owned_metadata(self) -> None:
        with self.assertRaisesRegex(ValueError, "Studio-owned"):
            creative_result_from_payload(
                {
                    "prose": "正文",
                    "decision_summary": "摘要",
                    "scene_delta": {},
                    "task_id": "forged",
                }
            )

    def test_runtime_inlines_only_project_local_sources_and_caches_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "characters").mkdir()
            (root / "characters" / "hero.md").write_text("人物怕失去妹妹的信任。", encoding="utf-8")
            outside = root.parent / "lean-kernel-secret.txt"
            outside.write_text("不应读取", encoding="utf-8")
            gateway = _Gateway()
            runtime = PiSceneTransactionRuntime(
                {},
                project_root=root,
                data_root=root / ".studio",
                gateway=gateway,
            )
            brief = _brief(("characters/hero.md", "../lean-kernel-secret.txt"))

            first = runtime.create_scene("tx-1", brief)
            second = runtime.create_scene("tx-1", brief)

            self.assertEqual(first, second)
            self.assertEqual(len(gateway.calls), 1)
            self.assertIn("人物怕失去妹妹的信任", gateway.calls[0][1])
            self.assertNotIn("不应读取", gateway.calls[0][1])
            self.assertEqual(runtime.metrics.provider_calls, 1)
            self.assertEqual(runtime.metrics.cache_hits, 1)
            self.assertEqual(
                first.scene_delta.character_changes[0].attributes,
                (("trust", "lower"),),
            )
            outside.unlink(missing_ok=True)

    def test_standard_scene_runs_through_pi_create_and_review_adapters(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gateway = _Gateway()
            runtime = PiSceneTransactionRuntime(
                {},
                project_root=root,
                data_root=root / ".studio",
                gateway=gateway,
            )
            uow = SqliteUnitOfWork(root / "studio.db")
            with uow.write() as connection:
                connection.executescript(SCENE_TRANSACTION_SCHEMA_SQL)
            repository = SceneTransactionRepository(uow)
            service = SceneTransactionService(
                briefs=_BriefProvider(_brief()),
                runtime=runtime,
                critic=runtime,
                repository=repository,
                commits=_CommitPort(),
                id_factory=lambda: "tx-standard",
            )

            transaction = service.prepare(root, "scene_0001", mode=SceneExecutionMode.STANDARD)
            service.create(transaction.transaction_id)
            service.verify(
                transaction.transaction_id,
                known_refs={"character/protagonist"},
            )
            service.review_if_required(transaction.transaction_id)
            committed = service.commit(transaction.transaction_id)

            self.assertEqual(committed.status, SceneTransactionStatus.COMMITTED)
            self.assertEqual([call[0] for call in gateway.calls], ["worker", "reviewer"])

    def test_review_cache_is_bound_to_the_exact_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gateway = _Gateway()
            runtime = PiSceneTransactionRuntime(
                {},
                project_root=root,
                data_root=root / ".studio",
                gateway=gateway,
            )
            report = VerificationReport("scene_0001", 20)
            first = CreativeResult("第一版正文。", "初稿", SceneDelta())
            second = CreativeResult("第二版正文。", "修订稿", SceneDelta())

            runtime.review_scene("tx-review", _brief(), first, report)
            runtime.review_scene("tx-review", _brief(), first, report)
            runtime.review_scene("tx-review", _brief(), second, report)

            self.assertEqual([role for role, _ in gateway.calls], ["reviewer", "reviewer"])
            self.assertEqual(runtime.metrics.cache_hits, 1)


if __name__ == "__main__":
    unittest.main()
