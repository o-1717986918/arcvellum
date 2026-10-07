"""Commission provenance and correction of failed natural deliveries."""
from copy import deepcopy
from hashlib import sha256
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
    VerificationReport,
)
from literary_engineering_studio_engine.public.prompting import list_prompt_layer_specs
from tests.runtimes.test_scene_natural_output import NaturalGateway, REQUEST, PROSE


class DeliveryRecoveryTests(unittest.TestCase):
    def test_unreadable_or_oversized_archives_do_not_freeze_plan_or_create_pending_calls(self):
        for problem in ("missing", "budget"):
            with self.subTest(problem=problem), TemporaryDirectory() as tmp:
                runtime, brief, data = setup_runtime(tmp, NaturalGateway())
                project = Path(tmp) / "work"
                if problem == "budget":
                    (project / "large.md").write_text("雨" * 24_001, encoding="utf-8")
                coordinator = SceneCreatorV2MaterialCoordinator(data / "v2",
                    SceneCreatorWorkspace(project, data), {}, scene_id=brief.scene_id)
                memory = SceneCreatorMemoryV1(brief.scene_id)
                before = memory.to_dict()
                payload = {"material_plan": {"required_kinds": ["environment"], "reason": "听雨"},
                    "material_requests": [{**REQUEST, "archive_attachments": [{"path": "project.yaml"}]},
                        {**REQUEST, "archive_attachments": [{"path": "large.md" if problem == "budget" else "missing.md"}]}]}
                with self.assertRaisesRegex(ValueError, "context budget" if problem == "budget" else "missing.md"):
                    runtime._accept_natural_turn(payload, brief, coordinator, memory)
                self.assertIsNone(coordinator.plan_context())
                self.assertEqual(memory.to_dict(), before)
                self.assertFalse(list((coordinator.root / "calls").glob("*.json")))

    def test_actor_partition_fields_are_retried_against_same_original_before_creator_memory(self):
        source = REQUEST["author_prompt"] + "\n" + REQUEST["style_direction"] + "\n角色可知区：characters/a-qing.yaml"
        prompts = []
        with TemporaryDirectory() as tmp:
            def extract(_system, prompt):
                prompts.append(json.loads(prompt))
                request = {**REQUEST, "kind": "actor", "target": "阿青", "archive_attachments": [
                    {"path": "characters/a-qing.yaml", "knowledge": "known" if len(prompts) == 2 else ""}]}
                return json.dumps({"material_requests": [request]}, ensure_ascii=False)
            processor = NaturalOutputProcessor(Path(tmp), "整理", extract)
            result = processor.process(source, kind="creator", context={"briefing": {
                "scene_brief": {"participants": ["阿青"]}}})
            self.assertEqual(result["material_requests"][0]["archive_attachments"][0]["knowledge"], "known")
            self.assertEqual(prompts[0]["source_text"], prompts[1]["source_text"])
            self.assertIn("known or reference", prompts[1]["transport_feedback"]["issue"])

    def test_missing_actor_partition_is_retained_for_creator_correction(self):
        source = REQUEST["author_prompt"] + "\n" + REQUEST["style_direction"]
        request = {**REQUEST, "kind": "actor", "target": "阿青", "archive_attachments": [{"path": "characters/a-qing.yaml"}]}
        with TemporaryDirectory() as tmp:
            processor = NaturalOutputProcessor(Path(tmp), "整理", lambda *_: json.dumps(
                {"material_requests": [request]}, ensure_ascii=False))
            with self.assertRaisesRegex(ValueError, "known or reference"):
                processor.process(source, kind="creator", context={"briefing": {"scene_brief": {"participants": ["阿青"]}}})
            self.assertEqual(len(list(Path(tmp).rglob("*.failure.json"))), 2)
            self.assertEqual(next(Path(tmp).rglob("original.md")).read_text(encoding="utf-8"), source)

    def test_next_natural_review_receives_previous_accepted_judgment_and_source(self):
        with TemporaryDirectory() as tmp:
            gateway = NaturalGateway()
            runtime, brief, data = setup_runtime(tmp, gateway)
            result = runtime.create_scene("review-history", brief)
            root = data / "scene-transactions/review-history"
            previous = {"decision": "revise", "summary": "水声与信封已成立，补足时间锚。",
                "revision_instructions": ["明确她想起门房的时间。"], "evidence": ["信封压在碗底"]}
            earlier = "review_result_v2_" + sha256("上一稿".encode()).hexdigest()[:16] + ".json"
            (root / earlier).write_text(json.dumps(previous, ensure_ascii=False), encoding="utf-8")
            current = "review_result_v2_" + sha256(result.prose.encode()).hexdigest()[:16] + ".json"
            (root / current).write_text('{"decision":"pass","summary":"current cache"}', encoding="utf-8")
            (root / "revision_result_v2_1.json").write_text('{}', encoding="utf-8")
            invoke, contexts = gateway.run, []
            def capture(project, prompt, **kwargs):
                envelope = json.loads(prompt)
                if envelope["schema"] == "arcvellum/default-conversation/v1" and "task_contract" not in envelope["prompt"]:
                    contexts.append(json.loads(envelope["prompt"].split("\n\n本次审读资料：\n", 1)[1]))
                return invoke(project, prompt, **kwargs)
            gateway.run = capture
            layers = {spec.layer_id: spec.default_text for spec in list_prompt_layer_specs()}
            runtime._review_natural("review-history", layers, {}, brief, result,
                VerificationReport(brief.scene_id, len(PROSE)), "")
            continuity = contexts[0]["review_continuity"]
            self.assertEqual(continuity["previous"]["review"], previous)
            self.assertEqual(continuity["previous"]["source"], earlier)
            self.assertEqual((continuity["completed_reviews"], continuity["completed_revisions"]), (1, 1))

    def test_mixed_creator_transport_retries_original_and_preserves_selected_phase(self):
        source = "完整正文：\n" + PROSE + "\n委托回顾：\n" + REQUEST["author_prompt"] + "\n" + REQUEST["style_direction"]
        for phase in ("prepare", "complete"):
            prompts = []
            with self.subTest(phase=phase), TemporaryDirectory() as tmp:
                def extract(_system, prompt):
                    prompts.append(json.loads(prompt))
                    payload = {"prose": PROSE, "material_requests": [REQUEST]}
                    if len(prompts) == 2:
                        payload["prose"] = "" if phase == "prepare" else PROSE
                        payload["material_requests"] = [REQUEST] if phase == "prepare" else []
                    return json.dumps(payload, ensure_ascii=False)
                processor = NaturalOutputProcessor(Path(tmp), "整理当轮交付", extract)
                result = processor.process(source, kind="creator", context={})
                self.assertEqual(prompts[0]["archive_knowledge_values"]["known"][0], "role_known_archive")
                self.assertEqual(result["prose"], "" if phase == "prepare" else PROSE)
                self.assertEqual(result["material_requests"], [REQUEST] if phase == "prepare" else [])
                self.assertEqual(prompts[0]["source_text"], prompts[1]["source_text"])
                self.assertIn("delivery phase", prompts[1]["transport_feedback"]["issue"])
                self.assertIn("complete", prompts[1]["delivery_modes"])
                self.assertEqual(len(list(Path(tmp).rglob("*.failure.json"))), 1)

    def test_persistently_mixed_transport_is_preserved_for_recovery(self):
        source = PROSE + "\n" + REQUEST["author_prompt"] + "\n" + REQUEST["style_direction"]
        with TemporaryDirectory() as tmp:
            processor = NaturalOutputProcessor(Path(tmp), "整理", lambda *_: json.dumps(
                {"prose": PROSE, "material_requests": [REQUEST]}, ensure_ascii=False))
            with self.assertRaisesRegex(ValueError, "mixes completed prose"):
                processor.process(source, kind="creator", context={})
            self.assertEqual(next(Path(tmp).rglob("original.md")).read_text(encoding="utf-8"), source)
            self.assertEqual(len(list(Path(tmp).rglob("*.failure.json"))), 2)

    def test_bad_transport_retries_same_original_with_specific_feedback(self):
        prompts = []
        with TemporaryDirectory() as tmp:
            def extract(_system, prompt):
                prompts.append(json.loads(prompt))
                return json.dumps({"candidates": [{"text": PROSE, "focus": "等待",
                    "private_impulse": "整理者添加的内心" if len(prompts) == 1 else ""}]}, ensure_ascii=False)
            processor = NaturalOutputProcessor(Path(tmp), "整理素材原文", extract)
            result = processor.process(PROSE, kind="material", context={"role": "character-actor"})
            self.assertEqual(result["candidates"][0]["text"], PROSE)
            self.assertEqual(prompts[0]["source_text"], prompts[1]["source_text"])
            self.assertIn("private_impulse", prompts[1]["transport_feedback"]["issue"])
            self.assertEqual(len(list(Path(tmp).rglob("*.extraction*.md"))), 2)
            self.assertEqual(len(list(Path(tmp).rglob("*.failure.json"))), 1)

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
