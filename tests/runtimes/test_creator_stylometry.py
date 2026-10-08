from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from literary_engineering_studio.application.creator_persona import CreatorPersonaStore
from literary_engineering_studio.application.style.stylometry_contracts import CreatorStyleSnapshot, LabDocument
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.scene_natural_output import (
    briefing_for_natural_context, creator_style,
)
from tests.runtimes.test_less_ai_tone_experiment import brief
from tests.runtimes.test_scene_natural_output import NaturalGateway
from literary_engineering_studio_engine.public.literary import CreativeResult, SceneDelta


def snapshot(text="在句子之间安排缓慢而清晰的呼吸。", **options):
    return CreatorStyleSnapshot(True, 1, "version-one", "profile-one", fragment_text=text,
        content_sha256=sha256(text.encode()).hexdigest(), **options)


class CreatorStylometryTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.directory = Path(self.folder.name)
        self.root = self.directory / "work"
        self.root.mkdir()
        (self.root / "project.yaml").write_text("title: 等待", encoding="utf-8")
        self.mount = snapshot()
        self.adapter = PiSceneTransactionRuntime({}, project_root=self.root,
            data_root=self.directory / "data", gateway=NaturalGateway(),
            creator_style_snapshot_provider=lambda _: self.mount)

    def test_version_is_frozen_and_old_transaction_stays_off(self):
        first = self.adapter._creator_style_snapshot("new")
        self.mount = snapshot("把语势交给窗外的雨。")
        self.assertEqual(first, self.adapter._creator_style_snapshot("new"))
        self.assertNotEqual(first, self.adapter._creator_style_snapshot("next"))
        old = self.adapter._cache_path("old", "prompt_assembly_v1.json")
        old.parent.mkdir(parents=True)
        old.write_text("{}")
        self.assertFalse(self.adapter._creator_style_snapshot("old")["enabled"])

    def test_observe_replace_append_and_single_v2_style_interface(self):
        self.assertIn(self.mount.fragment_text, self.adapter._creator_style_text("append", "原文风"))
        self.mount = replace(self.mount, combine="replace")
        self.assertNotIn("原文风", self.adapter._creator_style_text("replace", "原文风"))
        briefing = {"style": {"mounted": {"content": "原文风"}, "author_directive": {"content": "作者方向"}}}
        self.adapter._creator_style_briefing("replace", briefing)
        self.assertEqual(creator_style(briefing), "作者方向\n\n" + self.mount.fragment_text)
        self.mount = replace(self.mount, usage="observe")
        self.assertEqual(self.adapter._creator_style_text("observe", "原文风"), "原文风")
        untouched = {"style": {}}
        self.adapter._creator_style_briefing("observe", untouched)
        self.assertEqual(untouched, {"style": {}})

    def test_natural_context_keeps_style_provenance_without_copying_style_body(self):
        briefing = {"scene_id": "s1", "style": {
            "mounted": {"status": "mounted", "content": "正式文风", "source_paths": ["style/author.md"]},
            "author_directive": {"status": "active", "content": "作者指令", "revision": 4},
            "stylometry": {"version_id": "version-3", "content_sha256": "digest",
                           "combine": "append", "content": "计量指导"},
        }}

        projected = briefing_for_natural_context(briefing)

        self.assertEqual(briefing["style"]["mounted"]["content"], "正式文风")
        self.assertEqual(projected["scene_id"], "s1")
        self.assertEqual(projected["style"]["mounted"], {
            "status": "mounted", "source_paths": ["style/author.md"], "delivered_via": "system_prompt"})
        self.assertEqual(projected["style"]["author_directive"]["revision"], 4)
        self.assertEqual(projected["style"]["stylometry"]["version_id"], "version-3")
        self.assertTrue(all("content" not in item for item in projected["style"].values()))
        self.assertEqual(creator_style(briefing), "作者指令\n\n正式文风\n\n计量指导")

    def test_actual_natural_v2_main_receives_style_material_does_not(self):
        self.adapter._config = {"application": {"scene_creator_v2": {"enabled": True}}}
        CreatorPersonaStore(self.directory / "data").save(self.root,
            "沿人物的迟疑与生活中的物件组织故事，让等待具有具体的声音。", reason="作者初始意图")
        result = self.adapter.create_scene("v2", brief())
        systems = self.adapter._gateway.systems
        self.assertIn(self.mount.fragment_text, systems[0])
        material = [text for text in systems if text.startswith("你是一位以地方")]
        self.assertTrue(result.prose)
        self.assertNotIn(self.mount.fragment_text, json.dumps(self.adapter._gateway.context, ensure_ascii=False))
        self.assertTrue(material)
        self.assertTrue(all(self.mount.fragment_text not in text for text in material))

    def test_output_statistics_bind_text_and_measure_failure_is_visible(self):
        self.adapter._creator_style_measure_provider = lambda *args: LabDocument("stylometric-host/v1", '{"measurement": 1}')
        result = CreativeResult("风停了。", "", SceneDelta())
        with patch.object(self.adapter, "_create_scene", return_value=result):
            self.assertIs(self.adapter.create_scene("measured", brief()), result)
        reports = list(self.adapter._cache_path("measured", "stylometry").glob("*.json"))
        self.assertEqual(json.loads(reports[0].read_text(encoding="utf-8"))["text_sha256"], sha256(result.prose.encode()).hexdigest())
        def fail(*_):
            raise ValueError("missing analysis")
        self.adapter._creator_style_measure_provider = fail
        with patch.object(self.adapter, "_create_scene", return_value=result):
            self.assertIs(self.adapter.create_scene("failed", brief()), result)
        report = next(self.adapter._cache_path("failed", "stylometry").glob("*.json"))
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"], "failed")
