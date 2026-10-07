"""Roundtrip natural answers and frozen role systems through the real v2 adapter."""
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest
from literary_engineering_studio.application.creator_persona import CreatorPersonaStore
from literary_engineering_studio.runtime.role_conversation import RoleConversationResult, _conversation_prompt
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
from literary_engineering_studio.runtimes.scene_creator_v2_materials import render_material_invocation
from literary_engineering_studio_engine.public.literary import (
    LengthTarget, RhythmDirective, SceneBrief, SceneRisk, SceneRiskLevel, StyleMountRef,
    parse_scene_material_requests_v3,
    VerificationReport,
    ACTOR_CARD_SECTIONS,
)
from literary_engineering_studio_engine.public.prompting import list_prompt_layer_specs, prompt_layer_spec

MATERIAL = "窗沿的水一滴一滴落进旧碗，阿青的手停在碗口。"
PROSE = "阿青把空信封压在碗底。最后一滴水落下来时，她才听见有人叫她。"
REQUEST = {"kind": "environment", "target": "", "purpose": "延续等待", "scene_moment": "打开信封前",
    "cue": "雨将停", "author_prompt": "请沿湿木与水滴写出这个房间的等待。",
    "style_direction": "让句子随水滴的间隔呼吸，保留旧物的质地。", "archive_attachments": []}

class NaturalGateway:
    def __init__(self):
        self.creator_calls, self.material_calls, self.extract_calls = 0, 0, 0
        self.systems = []

    def run(self, root, prompt, **kwargs):
        envelope = json.loads(prompt)
        self.systems.append(envelope["system_prompt"])
        if envelope["schema"] == "arcvellum/scene-creator/v2":
            self.creator_calls += 1
            if self.creator_calls == 1:
                answer = "本场先用 environment 取材，借水声延续等待。" + REQUEST["author_prompt"] + "\n文风：" + REQUEST["style_direction"]
            else:
                self.context = json.loads(envelope["prompt"].split("本次创作资料：\n", 1)[1])
                identifier = re.search(r"v2:[a-f0-9]+:1", self.context["material_index"])[0]
                answer = PROSE + "\n\n创作札记：改写 " + identifier + "，让水滴成为回应的时点。信的去向仍待揭晓。"
        elif "task_contract" not in envelope["prompt"]:
            answer = "建议通过。信封压在碗底这个动作让等待落在具体物件上，水滴使回应的时点可感。"
        else:
            self.extract_calls += 1
            task = json.loads(envelope["prompt"])
            if task["operation"] == "review":
                payload = {"decision": "pass", "summary": "等待具有具体的声音与动作", "evidence": ["信封压在碗底"],
                           "revision_instructions": []}
            elif task["operation"] == "material":
                payload = {"candidates": [{"text": MATERIAL, "focus": "等待中的声音"}]}
            elif task["source_text"].startswith("本场"):
                payload = {"material_plan": {"required_kinds": ["environment"], "reason": "借水声延续等待"},
                           "material_requests": [REQUEST]}
            else:
                identifier = re.search(r"v2:[a-f0-9]+:1", task["context"]["material_index"])[0]
                payload = {"prose": PROSE, "decision_summary": "让水滴成为回应的时点",
                    "material_decisions": [{"candidate_id": identifier, "decision": "adapt", "reason": "成为回应的时点"}],
                    "scene_delta": {"next_handoff": ["信的去向仍待揭晓"]}}
            answer = json.dumps(payload, ensure_ascii=False)
        return RoleConversationResult("pi-worker", "test", "test/model", answer)

    def run_role_turn(self, root, **kwargs):
        self.material_calls += 1
        self.systems.append(kwargs["initialization"])
        return RoleConversationResult("pi-worker", "test", "test/model", MATERIAL)

class NaturalSceneTests(unittest.TestCase):
    def test_creator_material_final_roundtrip_and_cache(self):
        with TemporaryDirectory() as tmp:
            root, data = Path(tmp) / "work", Path(tmp) / "data"
            root.mkdir()
            (root / "project.yaml").write_text("title: 雨信\n", encoding="utf-8")
            CreatorPersonaStore(data).save(root, "沿人物的迟疑与生活中的物件组织故事，让等待具有具体的声音。", reason="初始作者意图")
            brief = SceneBrief("s1", "寻找信", "让等待可感", ("阿青",), (), (), (),
                RhythmDirective(), LengthTarget(), StyleMountRef(), SceneRisk(SceneRiskLevel.LOW), ())
            gateway = NaturalGateway()
            runtime = PiSceneTransactionRuntime({"application": {"scene_creator_v2": {"enabled": True}}},
                project_root=root, data_root=data, gateway=gateway)
            result = runtime.create_scene("tx-natural", brief)
            self.assertEqual(result.prose, PROSE)
            self.assertEqual(result.scene_delta.next_handoff, ("信的去向仍待揭晓",))
            self.assertEqual((gateway.creator_calls, gateway.material_calls, gateway.extract_calls), (2, 1, 2))
            runtime.create_scene("tx-natural", brief)
            self.assertEqual(gateway.creator_calls, 2)
            originals = list((data / "scene-transactions/tx-natural/v2/natural-answers").glob("*/original.md"))
            self.assertEqual(len(originals), 3)
            self.assertTrue(any(path.read_text(encoding="utf-8") == MATERIAL for path in originals))
            material_system = next(text for text in gateway.systems if text.startswith("你是一位以地方"))
            self.assertIn(REQUEST["style_direction"], material_system)
            self.assertNotIn("固定权限", material_system)
            self.assertNotIn("JSON", material_system)
            snapshot = json.loads((data / "scene-transactions/tx-natural/prompt_assembly_v2.json").read_text(encoding="utf-8"))
            self.assertNotIn("scene.v2.material.shared.protocol", snapshot["texts"])
            review = runtime.review_scene("tx-natural", brief, result, VerificationReport("s1", len(PROSE)))
            self.assertEqual(review.decision.value, "pass")
            self.assertIsNone(runtime._review_original("tx-natural", PROSE + "新稿"))
            revised = runtime.revise_scene("tx-natural", brief, result,
                VerificationReport("s1", len(PROSE)), review, attempt=1)
            self.assertEqual(revised.prose, PROSE)
            self.assertEqual(gateway.context["revision_context"]["previous_prose"], PROSE)
            self.assertIn("信封压在碗底这个动作", gateway.context["revision_context"]["review_original"]["content"])
            self.assertEqual(gateway.material_calls, 1)
            runtime.revise_scene("tx-natural", brief, result,
                VerificationReport("s1", len(PROSE)), review, attempt=1)
            self.assertEqual(gateway.creator_calls, 3)

    def test_extraction_rewrite_fails_and_preserves_original(self):
        with TemporaryDirectory() as tmp:
            processor = NaturalOutputProcessor(Path(tmp), "整理原文", lambda *_: '{"prose":"被整理者改写的正文"}')
            with self.assertRaisesRegex(ValueError, "changed prose"):
                processor.process(PROSE, kind="creator", context={})
            original, = Path(tmp).glob("natural-answers/*/original.md")
            self.assertEqual(original.read_text(encoding="utf-8"), PROSE)

    def test_direct_material_identity_and_custom_transport_system(self):
        request, = parse_scene_material_requests_v3({"material_requests":[REQUEST]}, [])
        layers = {spec.layer_id:spec.default_text for spec in list_prompt_layer_specs()}
        invocation = render_material_invocation(request, [], layers, scene_id="s1")
        expected = prompt_layer_spec("scene.v2.material.environment").default_text.replace("{{STYLE_DIRECTION}}", REQUEST["style_direction"])
        self.assertEqual(invocation.initialization, expected)
        envelope = json.dumps({"schema":"arcvellum/default-conversation/v1", "system_prompt":"整理", "prompt":"原文"})
        self.assertEqual(_conversation_prompt("reviewer", envelope), (envelope, False))

    def test_creator_card_extraction_preserves_authorship(self):
        from literary_engineering_studio.runtimes.scene_natural_output import validate_extracted_text
        card = {"sections": {key: key + "：人物原文" for key in ACTOR_CARD_SECTIONS}}
        payload = {"material_requests": [{"character_card": card}]}
        source = "\n".join(card["sections"].values())
        validate_extracted_text(source, payload, "creator")
        with self.assertRaisesRegex(ValueError, "changed card section"):
            validate_extracted_text("整理者自行编了一张卡", payload, "creator")
        validate_extracted_text("请继续用这张已冻结的卡。", payload, "creator", {
            "actor_card_context": {"frozen_scene_cards": [{"card": card}]}})

if __name__=="__main__": unittest.main()

