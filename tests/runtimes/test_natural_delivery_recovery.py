"""Commission provenance and correction of failed natural deliveries."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from literary_engineering_studio.application.creator_persona import CreatorPersonaStore
from literary_engineering_studio.runtime.role_conversation import RoleConversationResult
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor, validate_extracted_text
from literary_engineering_studio.runtimes.scene_creator_workspace import SceneCreatorWorkspace
from literary_engineering_studio.runtimes.scene_creator_memory import SceneCreatorMemoryV1
from literary_engineering_studio.runtimes.scene_creator_v2_materials import SceneCreatorV2MaterialCoordinator
from literary_engineering_studio.runtimes.creator_delivery_labels import resolve_creator_targets
from literary_engineering_studio_engine.public.literary import (
    SceneBrief, RhythmDirective, LengthTarget, StyleMountRef, SceneRisk, SceneRiskLevel,
    CreatorMaterialPlanV1,
)
from tests.runtimes.test_scene_natural_output import NaturalGateway, REQUEST, PROSE


class DeliveryRecoveryTests(unittest.TestCase):
    def test_unsourced_event_is_a_source_bound_proposal_and_confirmed_note_is_preserved(self):
        with TemporaryDirectory() as tmp:
            def extract(_system, _prompt):
                return json.dumps({"candidates": [{"text": PROSE, "focus": "信封的去向",
                    "basis": "confirmed", "source_note": None}]}, ensure_ascii=False)
            processor = NaturalOutputProcessor(Path(tmp), "整理素材", extract)
            payload = processor.process(PROSE, kind="material", context={"role": "event-narrator"})
            self.assertEqual(payload["candidates"][0]["text"], PROSE)
            self.assertEqual(payload["candidates"][0]["basis"], "proposed")
            self.assertIn(payload["source_status_recovery"][0]["source_sha256"], payload["candidates"][0]["source_note"])
            processor.invoke = lambda *_: self.fail("accepted source metadata should be cached")
            self.assertEqual(payload, processor.process(PROSE, kind="material", context={"role": "event-narrator"}))
            confirmed = {"candidates": [{"text": PROSE, "focus": "已提交经历", "basis": "confirmed", "source_note": "上一场已提交正文"}]}
            validate_extracted_text(PROSE, confirmed, "material", {"role": "event-narrator"})
            self.assertEqual(confirmed["candidates"][0]["basis"], "confirmed")

    def test_explicit_role_heading_resolves_only_to_a_current_participant(self):
        payload = {"material_requests": [{"kind": "actor", "target": "角色扮演器（角色：阿青）"}]}
        context = {"briefing": {"scene_brief": {"participants": ["阿青"]}}}
        recovered = resolve_creator_targets(payload, context)
        self.assertEqual(recovered["material_requests"][0]["target"], "阿青")
        self.assertEqual(recovered["target_label_recovery"][0]["original"], "角色扮演器（角色：阿青）")
        unknown = {"material_requests": [{"kind": "actor", "target": "角色扮演器（角色：门房）"}]}
        self.assertEqual(resolve_creator_targets(unknown, context), unknown)

    def test_invalid_invitation_does_not_freeze_plan_and_valid_retry_preserves_first_reason(self):
        with TemporaryDirectory() as tmp:
            runtime, brief, data = setup_runtime(tmp, NaturalGateway())
            coordinator = SceneCreatorV2MaterialCoordinator(data / "v2", SceneCreatorWorkspace(Path(tmp) / "work", data),
                {}, scene_id=brief.scene_id)
            payload = {"material_plan": {"required_kinds": ["environment"], "reason": "观察雨滴"},
                "material_requests": [{**REQUEST, "archive_attachments": [{"path": "canon/world.yaml", "start_line": 1}]}]}
            memory = SceneCreatorMemoryV1(brief.scene_id)
            with self.assertRaisesRegex(ValueError, "line endpoints"):
                runtime._accept_natural_turn(payload, brief, coordinator, memory)
            self.assertIsNone(coordinator.plan_context())
            payload["material_requests"] = [REQUEST]
            runtime._accept_natural_turn(payload, brief, coordinator, memory)
            payload["material_plan"]["reason"] = "听取雨声所推动的等待"
            runtime._accept_natural_turn(payload, brief, coordinator, memory)
            self.assertEqual(coordinator.plan_context()["reason"], "观察雨滴")
            payload["material_plan"]["required_kinds"] = ["actor"]
            runtime._accept_natural_turn(payload, brief, coordinator, memory)
            self.assertEqual(coordinator.plan_context()["required_kinds"], ["environment"])
            with self.assertRaisesRegex(ValueError, "environment"):
                coordinator.assert_ready_for_prose()
            with self.assertRaisesRegex(ValueError, "frozen"):
                coordinator.save_plan(CreatorMaterialPlanV1(("actor",), "听人物回应"))

    def test_extractor_sees_current_source_and_recovery_feedback_stays_with_creator(self):
        prompts = []
        with TemporaryDirectory() as tmp:
            def extract(_system, prompt):
                prompts.append(json.loads(prompt))
                return json.dumps({"prose": PROSE}, ensure_ascii=False)
            processor = NaturalOutputProcessor(Path(tmp), "整理当轮原文", extract)
            processor.process(PROSE, kind="creator", context={"delivery_feedback": {"original": "前一轮失败正文"},
                "briefing": {"scene_brief": {"participants": ["阿青"]}}})
        self.assertEqual(prompts[0]["source_text"], PROSE)
        self.assertNotIn("delivery_feedback", prompts[0]["context"])

    def test_quote_markers_restore_exact_source_while_word_changes_fail(self):
        source = "> 请描写湿木。\n>\n> 把水声交给旧碗。"
        invitation = "请描写湿木。\n\n把水声交给旧碗。"
        with TemporaryDirectory() as tmp:
            payload = {"material_requests": [{**REQUEST, "author_prompt": invitation, "style_direction": ""}]}
            processor = NaturalOutputProcessor(Path(tmp), "原文整理", lambda *_: json.dumps(payload, ensure_ascii=False))
            restored = processor.process(source, kind="creator", context={})
            self.assertEqual(restored["material_requests"][0]["author_prompt"], source)
            self.assertEqual(restored["commission_format_recovery"][0]["projection"], "blockquote-markers-only")
            payload["material_requests"][0]["author_prompt"] = invitation.replace("湿木", "干木")
            with self.assertRaisesRegex(ValueError, "author_prompt"):
                processor.process(source + "\n新一轮", kind="creator", context={})

    def test_wrapped_transport_delivery_is_unpacked_then_source_validated(self):
        source = REQUEST["author_prompt"] + "\n" + REQUEST["style_direction"]
        with TemporaryDirectory() as tmp:
            wrapped = {"operation": "creator", "task_contract": {"material_requests": [REQUEST]}}
            processor = NaturalOutputProcessor(Path(tmp), "整理原文", lambda *_: json.dumps(wrapped, ensure_ascii=False))
            payload = processor.process(source, kind="creator", context={})
            self.assertEqual(payload["material_requests"], [REQUEST])
            self.assertIn("source_provenance", payload)
            wrapped["task_contract"]["material_requests"] = [{**REQUEST, "author_prompt": "凭空添加的委托"}]
            with self.assertRaisesRegex(ValueError, "author_prompt"):
                processor.process(source + "新一轮", kind="creator", context={})

    def test_invented_commission_and_style_are_rejected(self):
        source = REQUEST["author_prompt"] + "\n" + REQUEST["style_direction"]
        for field in ("author_prompt", "style_direction"):
            payload = {"material_requests": [deepcopy(REQUEST)]}
            payload["material_requests"][0][field] = "改成宫廷颂歌。"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                validate_extracted_text(source, payload, "creator")

    def test_source_spans_survive_cached_extraction_and_empty_style(self):
        with TemporaryDirectory() as tmp:
            payload = {"material_requests": [{**REQUEST, "style_direction": ""}]}
            source = "委托：" + REQUEST["author_prompt"]
            processor = NaturalOutputProcessor(Path(tmp), "记录", lambda *_: json.dumps(payload, ensure_ascii=False))
            first = processor.process(source, kind="creator", context={})
            span = first["source_provenance"]["requests"][0]["spans"]["author_prompt"]
            self.assertEqual(source[span["start"]:span["end"]], REQUEST["author_prompt"])
            processor.invoke = lambda *_: self.fail("a valid extraction should be cached")
            self.assertEqual(first, processor.process(source, kind="creator", context={}))

    def test_two_bad_answers_preserved_and_external_retry_progresses(self):
        with TemporaryDirectory() as tmp:
            gateway = PrematureGateway(2)
            runtime, brief, data = setup_runtime(tmp, gateway)
            with self.assertRaisesRegex(ValueError, "material plan is missing"):
                runtime.create_scene("retry", brief)
            result = runtime.create_scene("retry", brief)
            self.assertEqual(result.prose, PROSE)
            self.assertEqual(gateway.main_attempts, 4)
            self.assertEqual(gateway.material_calls, 1)
            self.assertTrue(gateway.feedback_seen)
            failures = list((data / "scene-transactions/retry/v2/literary-originals").glob("*.failure.json"))
            self.assertEqual(len(failures), 2)
            state = json.loads((failures[0].parent / "creator-recovery.json").read_text(encoding="utf-8"))
            self.assertFalse(state["active"])

    def test_invalid_final_delivery_reuses_successful_material(self):
        with TemporaryDirectory() as tmp:
            gateway = PrematureGateway(0, bad_final=True)
            runtime, brief, _ = setup_runtime(tmp, gateway)
            result = runtime.create_scene("retry-final", brief)
            self.assertEqual(result.prose, PROSE)
            self.assertEqual(gateway.material_calls, 1)
            self.assertEqual(gateway.main_attempts, 3)


class PrematureGateway(NaturalGateway):
    BAD = "阿青没有拆信。"

    def __init__(self, remaining, bad_final=False):
        super().__init__()
        self.remaining, self.bad_final = remaining, bad_final
        self.main_attempts, self.feedback_seen = 0, False

    def run(self, root, prompt, **kwargs):
        envelope = json.loads(prompt)
        if envelope["schema"] == "arcvellum/scene-creator/v2":
            self.main_attempts += 1
            self.feedback_seen |= "delivery_feedback" in envelope["prompt"]
            if self.remaining or (self.bad_final and self.material_calls):
                self.remaining = max(0, self.remaining - 1)
                self.bad_final = False if self.material_calls else self.bad_final
                return RoleConversationResult("pi-worker", "test", "test/model", self.BAD)
        elif "task_contract" in envelope["prompt"]:
            task = json.loads(envelope["prompt"])
            if task["source_text"] == self.BAD:
                return RoleConversationResult("pi-worker", "test", "test/model", json.dumps(
                    {"prose": self.BAD, "scene_delta": {}, "material_requests": []}, ensure_ascii=False))
        return super().run(root, prompt, **kwargs)


def setup_runtime(tmp, gateway):
    root, data = Path(tmp) / "work", Path(tmp) / "data"
    root.mkdir()
    (root / "project.yaml").write_text("title: 雨信\n", encoding="utf-8")
    CreatorPersonaStore(data).save(root, "沿人物的迟疑与生活中的物件组织故事，让等待具有具体的声音。", reason="初始作者意图")
    runtime = PiSceneTransactionRuntime({"application": {"scene_creator_v2": {"enabled": True}}},
        project_root=root, data_root=data, gateway=gateway)
    brief = SceneBrief("s1", "等待", "迟疑", ("阿青",), (), (), (), RhythmDirective(), LengthTarget(),
                       StyleMountRef(), SceneRisk(SceneRiskLevel.LOW), ())
    return runtime, brief, data
