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
from literary_engineering_studio_engine.public.literary import (
    SceneBrief, RhythmDirective, LengthTarget, StyleMountRef, SceneRisk, SceneRiskLevel,
)
from tests.runtimes.test_scene_natural_output import NaturalGateway, REQUEST, PROSE


class DeliveryRecoveryTests(unittest.TestCase):
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
