from __future__ import annotations

from pathlib import Path
import json
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
    render_scene_revision_prompt,
    render_scene_review_prompt,
)
from literary_engineering_studio_engine.literary.scene.transaction import (
    ChangeProposal,
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
        elif prompt.startswith("# 首轮场景正文续写"):
            answer = json.dumps({"insertion": "她想起昨夜反复推开的那扇门，终于把迟疑说给妹妹听。" * 30}, ensure_ascii=False)
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
        self.assertIn("canon_constraints", prompt)
        self.assertIn("不得用登记 new_asset_candidates 绕过", prompt)
        self.assertIn("逐字沿用其中已确定的人名、日期、年份、数量和时间差", prompt)
        self.assertIn("保留差值不代表可以改动构成差值的绝对值", prompt)
        self.assertIn("核对—追问—停顿—留悬念", prompt)
        self.assertIn("未列入 participants 的主要人物不得登场", prompt)
        self.assertIn("不得重演首次见面", prompt)
        self.assertIn("写对白前根据人物资产、欲望、身份和本场关系压力", prompt)
        self.assertIn("speech_style 未填写时从已知事实推导", prompt)
        self.assertIn("基础“清简”不能把所有人压成同一种平直短句", prompt)
        self.assertIn("Style Reference Priority", prompt)
        self.assertIn("一篇最贴合本场功能的样例作表达主参照", prompt)
        self.assertIn("主动模仿其叙述距离、句群呼吸", prompt)
        self.assertIn("新增精确数字默认不用", prompt)
        self.assertIn("“一个又一个”“一次次”等虚指反复并非精确计数", prompt)
        self.assertIn("当场问答、人物选择或谈判", prompt)
        self.assertIn("不要求五项同时成立", prompt)
        self.assertIn("不得批量删数字或机械换成模糊量词", prompt)
        self.assertIn("一张桌、两把椅子、拧两下、看几秒", prompt)
        self.assertIn("若只为显得具体，删去精度不损失对话信息", prompt)
        self.assertGreater(prompt.rfind("## Final Prose Pass"), prompt.rfind("## Output"))

    def test_review_treats_hard_continuity_conflicts_as_revision(self) -> None:
        result = CreativeResult("第一版正文。", "初稿", SceneDelta())
        prompt = render_scene_review_prompt(
            _brief(), result, VerificationReport("scene_0001", 6), revision_attempts=3
        )

        self.assertIn("必须判 revise", prompt)
        self.assertIn("指出冲突两端", prompt)
        self.assertIn("绝对测量值与差值", prompt)
        self.assertIn("软字数偏差只作建议，不得单独退回", prompt)
        self.assertIn("重复结构及可保留的有效内容", prompt)
        self.assertIn("共享调查题材", prompt)
        self.assertIn("最小指令", prompt)
        self.assertIn("当前场 scene_goal", prompt)
        self.assertIn("三个以上关键节拍", prompt)
        self.assertIn("本场已完成 3 轮返修", prompt)
        self.assertIn("孤立句式、局部动作相似或可选润色一律判 pass", prompt)
        self.assertIn("只有持续混同已损害人物可信度或关系张力时才要求修订", prompt)
        self.assertIn("对明确无关的精确计数，引用具体片段", prompt)
        self.assertIn("对虚指反复、当场问答或改变人物理解的数值，不得仅因数词存在", prompt)
        self.assertIn("不得按数词出现本身、数字密度或统一清单裁决", prompt)
        self.assertGreater(prompt.rfind("## Quantitative Detail Review"), prompt.rfind("## Relevant Sources"))

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

    def test_parser_discards_only_empty_placeholders_and_normalizes_handoff(self) -> None:
        result = creative_result_from_payload(
            {
                "prose": "正文。",
                "decision_summary": "摘要。",
                "scene_delta": {
                    "character_changes": [
                        {"target_ref": "", "summary": "", "evidence": "", "attributes": []},
                        {"target_ref": "", "summary": "缺少引用", "evidence": "正文证据"},
                    ],
                    "new_asset_candidates": [
                        {"target_ref": "location/new", "summary": "出现新地点"}
                    ],
                    "next_handoff": [
                        {"handoff": "下一场接住未完成的承诺"},
                        {"unexpected": "ignored"},
                    ],
                },
            }
        )

        self.assertEqual(len(result.scene_delta.character_changes), 1)
        self.assertEqual(result.scene_delta.character_changes[0].summary, "缺少引用")
        self.assertEqual(result.scene_delta.new_asset_candidates[0].operation, "create")
        self.assertEqual(result.scene_delta.next_handoff, ("下一场接住未完成的承诺",))

    def test_prompts_explain_exact_reference_and_revision_delta_contracts(self) -> None:
        brief = _brief()
        create = render_scene_create_prompt(
            brief,
            allowed_refs={"character/protagonist", "character/sister"},
        )
        result = CreativeResult(
            "第一版正文。",
            "初稿",
            SceneDelta(
                character_changes=(
                    ChangeProposal("invented-id", "人物改变", "正文证据"),
                )
            ),
        )
        revision = render_scene_revision_prompt(
            brief,
            result,
            VerificationReport("scene_0001", 6),
            None,
            allowed_refs={"character/protagonist", "character/sister"},
        )

        self.assertIn('"character/protagonist"', create)
        self.assertIn("只能逐字选自 Allowed Existing Refs", create)
        self.assertIn("Existing SceneDelta", revision)
        self.assertIn("invented-id", revision)
        self.assertIn("不得保留空对象", revision)
        self.assertIn("不得在修复一个问题时重新引入已消失的冲突", revision)
        self.assertIn("不得用 new_asset_candidates 绕过", revision)
        self.assertIn("修订时保留或恢复与本场相合的具体样例表达形态", revision)
        self.assertIn("新增精确数字默认不用", revision)
        self.assertIn("不要求五项同时成立", revision)
        self.assertIn("不要把所有台词统一磨成平直短句", revision)
        self.assertGreater(revision.rfind("## Final Prose Pass"), revision.rfind("## Output"))

    def test_runtime_inlines_only_project_local_sources_and_caches_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "characters").mkdir()
            (root / "characters" / "hero.md").write_text("人物怕失去妹妹的信任。", encoding="utf-8")
            (root / "style" / "mounted" / "sample").mkdir(parents=True)
            (root / "style" / "mounted" / "sample" / "style-profile.md").write_text(
                "R01：短句承压。\nR25：结尾以行动落定。", encoding="utf-8"
            )
            outside = root.parent / "lean-kernel-secret.txt"
            outside.write_text("不应读取", encoding="utf-8")
            gateway = _Gateway()
            runtime = PiSceneTransactionRuntime(
                {},
                project_root=root,
                data_root=root / ".studio",
                gateway=gateway,
            )
            brief = _brief((
                "characters/hero.md",
                "style/mounted/sample/style-profile.md",
                "../lean-kernel-secret.txt",
            ))

            first = runtime.create_scene("tx-1", brief)
            second = runtime.create_scene("tx-1", brief)

            self.assertEqual(first, second)
            self.assertEqual(len(gateway.calls), 2)
            self.assertIn("人物怕失去妹妹的信任", gateway.calls[0][1])
            self.assertIn("R25：结尾以行动落定。", gateway.calls[0][1])
            self.assertNotIn("不应读取", gateway.calls[0][1])
            self.assertEqual(runtime.metrics.provider_calls, 2)
            self.assertEqual(runtime.metrics.cache_hits, 1)
            self.assertGreaterEqual(len(first.prose), 600)
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
            self.assertEqual([call[0] for call in gateway.calls], ["worker", "worker", "reviewer"])

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
