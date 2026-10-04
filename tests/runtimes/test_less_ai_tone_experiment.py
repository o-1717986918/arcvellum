"""Automatic editing mount through the real scene runtime and natural transport."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from literary_engineering_studio.runtime.role_conversation import RoleConversationResult
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.less_ai_tone_edits import apply_tone_edits
from literary_engineering_studio.runtimes.less_ai_tone_experiment import EDITOR
from literary_engineering_studio.runtimes.scene_natural_output import validate_extracted_text
from literary_engineering_studio_engine.public.literary import (
    CreativeResult, SceneDelta, ChangeProposal, SceneBrief, RhythmDirective,
    LengthTarget, StyleMountRef, SceneRisk, SceneRiskLevel, VerificationReport,
)
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
from tests.runtimes.test_scene_natural_output import NaturalGateway, PROSE

RAW = "说白了，阿青等了3天。\n\n她说：“再等一下。”"
CLEAN = "阿青等了3天。\n\n她说：“再等一下。”"


def edit(before="说白了，", after="", rule="9"):
    return dict(rule_id=rule, before=before, after=after, reason="让等待直接落在人物身上。")


def brief():
    return SceneBrief("s1", "等待一封信", "让等待可感", ("阿青",), (), (), (),
        RhythmDirective(), LengthTarget(), StyleMountRef(), SceneRisk(SceneRiskLevel.LOW), ())


class EditingGateway:
    def __init__(self):
        self.calls = []

    def run(self, root, prompt, **kwargs):
        envelope = json.loads(prompt)
        self.calls.append((kwargs["role"], envelope))
        if kwargs["role"] == "worker":
            answer = "规则9：原片段「说白了，」，替换为空。让等待直接落在人物身上。"
        else:
            answer = json.dumps({"edits": [edit()], "summary": "一处开场清理"}, ensure_ascii=False)
        return RoleConversationResult("pi-worker", "test", "test/model", answer)


def runtime(directory, enabled=True, gateway=None, sink=None):
    root = directory / "work"
    root.mkdir(exist_ok=True)
    (root / "project.yaml").write_text("title: 等待\n", encoding="utf-8")
    return PiSceneTransactionRuntime({"application": {"less_ai_tone_experiment": {"enabled": enabled}}},
        project_root=root, data_root=directory / "data", gateway=gateway or EditingGateway(), event_sink=sink)


class ToneExperimentTests(unittest.TestCase):
    def test_create_revision_cache_and_delta_evidence(self):
        with TemporaryDirectory() as tmp:
            events, gateway = [], EditingGateway()
            adapter = runtime(Path(tmp), gateway=gateway, sink=lambda *event: events.append(event))
            delta = SceneDelta(continuity_changes=(ChangeProposal("continuity", "等待", "阿青等了3天。"),))
            original = CreativeResult(RAW, "等待", delta)
            with patch.object(adapter, "_create_scene", return_value=original):
                cleaned = adapter.create_scene("tone-tx", brief())
                self.assertEqual(cleaned.prose, CLEAN)
                self.assertIs(cleaned.scene_delta, delta)
                adapter.create_scene("tone-tx", brief())
            self.assertEqual(len(gateway.calls), 2)
            self.assertEqual([role for role, _ in gateway.calls], ["worker", "reviewer"])
            self.assertEqual(gateway.calls[0][1]["schema"], "arcvellum/default-conversation/v1")
            self.assertNotIn("{{STYLE_DIRECTION}}", gateway.calls[0][1]["system_prompt"])
            with patch.object(adapter, "_revise_scene", return_value=original):
                adapter.revise_scene("tone-tx", brief(), original, None, None, attempt=1)
            self.assertEqual(len(gateway.calls), 4)
            reports = list((Path(tmp) / "data/scene-transactions/tone-tx/less-ai-tone").glob("*/report.json"))
            self.assertEqual(len(reports), 2)
            report = json.loads(reports[0].read_text(encoding="utf-8"))
            self.assertEqual((report["original"], report["cleaned"]), (RAW, CLEAN))
            self.assertEqual((reports[0].parent / "original.md").read_text(encoding="utf-8"), RAW)
            self.assertEqual(events[0][0], "scene.less-ai-tone.completed")

    def test_off_and_existing_scene_snapshot_remain_frozen(self):
        with TemporaryDirectory() as tmp:
            adapter = runtime(Path(tmp), enabled=False)
            self.assertFalse(adapter._tone_mount("off")["enabled"])
            adapter._config["application"]["less_ai_tone_experiment"]["enabled"] = True
            self.assertFalse(adapter._tone_mount("off")["enabled"])
            old = adapter._cache_path("old", "prompt_assembly_v2.json")
            old.parent.mkdir(parents=True)
            old.write_text("{}", encoding="utf-8")
            self.assertFalse(adapter._tone_mount("old")["enabled"])
            self.assertTrue(adapter._tone_mount("new")["enabled"])
            original = CreativeResult(RAW, "", SceneDelta())
            with patch.object(adapter, "_create_scene", return_value=original):
                self.assertIs(adapter.create_scene("off", brief()), original)
            self.assertEqual(adapter._gateway.calls, [])

    def test_natural_v2_generation_and_review_use_cleaned_result(self):
        class Gateway(NaturalGateway):
            def run(self, root, prompt, **kwargs):
                envelope = json.loads(prompt)
                if envelope["system_prompt"].startswith("你是本场主创，正在以文学编辑"):
                    answer = "规则9：原片段「最后一滴水落下来时，」，改为「水滴落尽，」。让句子直接接上感知。"
                    return RoleConversationResult("pi-worker", "test", "test/model", answer)
                if '"operation": "tone"' in envelope["prompt"]:
                    answer = json.dumps({"edits": [edit("最后一滴水落下来时，", "水滴落尽，")], "summary": "清理"}, ensure_ascii=False)
                    return RoleConversationResult("pi-worker", "test", "test/model", answer)
                if "task_contract" not in envelope["prompt"] and kwargs["role"] == "reviewer":
                    self.review_prompt = envelope["prompt"]
                return super().run(root, prompt, **kwargs)
        with TemporaryDirectory() as tmp:
            from literary_engineering_studio.application.creator_persona import CreatorPersonaStore
            gateway = Gateway()
            adapter = runtime(Path(tmp), gateway=gateway)
            adapter._config["application"]["scene_creator_v2"] = {"enabled": True}
            CreatorPersonaStore(Path(tmp) / "data").save(adapter._project_root, "沿人物的迟疑与生活中的物件组织故事，让等待具有具体的声音。", reason="本次作者初始意图")
            result = adapter.create_scene("v2-tone", brief())
            self.assertEqual(result.prose, PROSE.replace("最后一滴水落下来时，", "水滴落尽，"))
            adapter.review_scene("v2-tone", brief(), result, VerificationReport("s1", len(result.prose)))
            self.assertIn(result.prose, gateway.review_prompt)

    def test_prompt_version_and_style_are_frozen_with_the_mount(self):
        with TemporaryDirectory() as tmp:
            adapter = runtime(Path(tmp))
            texts = {key: prompt_layer_spec(key).default_text for key in (EDITOR, "scene.v2.transport.extractor")}
            adapter._prompt_snapshot_provider = lambda *_: {"texts": texts, "digest": "version-one",
                "layers": [{"layer_id": EDITOR, "source": "project", "version": 3}]}
            style_path = adapter._project_root / "style/owner_style_directive.md"
            style_path.parent.mkdir()
            style_path.write_text("原有文风", encoding="utf-8")
            mounted = adapter._tone_mount("versioned")
            adapter._prompt_snapshot_provider = lambda *_: {"texts": {}, "digest": "version-two"}
            style_path.write_text("新的文风", encoding="utf-8")
            resumed = adapter._tone_mount("versioned")
            self.assertEqual(resumed, mounted)
            self.assertIn("原有文风", resumed["style"])
            self.assertEqual(resumed["prompt_snapshot"]["layers"][0]["version"], 3)

    def test_positive_template_keeps_one_style_field_and_eleven_rules(self):
        text = prompt_layer_spec(EDITOR).default_text
        self.assertEqual(text.count("{{STYLE_DIRECTION}}"), 1)
        for number in range(1, 12):
            self.assertIn(f"{number} ·", text)
        for wording in ("你不是", "你不能", "不得", "不要", "没有权限"):
            self.assertNotIn(wording, text)


class LocalEditingTests(unittest.TestCase):
    def test_protected_dialogue_numbers_name_and_evidence(self):
        for before, after in (("再等一下", "快走"), ("3", "4"), ("阿青", "小青"), ("等了", "走了")):
            with self.subTest(before=before):
                cleaned, accepted, rejected = apply_tone_edits(RAW, [edit(before, after)], ["阿青", "阿青等了3天。"])
                self.assertEqual(cleaned, RAW)
                self.assertEqual(accepted, [])
                self.assertEqual(len(rejected), 1)

    def test_duplicate_overlap_and_structure(self):
        prose = "说白了，阿青等着。\n\n窗外有风。"
        edits = [edit(), edit("说白了，阿青", "阿青"), edit("\n\n", "\n")]
        cleaned, accepted, rejected = apply_tone_edits(prose, edits)
        self.assertEqual(cleaned, prose.replace("说白了，", ""))
        self.assertEqual((len(accepted), len(rejected)), (1, 2))
        self.assertEqual(apply_tone_edits("啊，啊", [edit("啊", "哦")])[1], [])
        self.assertEqual(apply_tone_edits("# 标题\n正文", [edit("# ", "")])[1], [])

    def test_combined_patch_protection_and_original_no_edits(self):
        # Individually safe patches can together create a protected string.
        self.assertEqual(len(apply_tone_edits("xy", [edit("x", "a")], ["ab"])[1]), 1)
        self.assertEqual(apply_tone_edits("xy", [edit("x", "a"), edit("y", "b")], ["ab"])[0], "xy")
        self.assertEqual(apply_tone_edits(RAW, []), (RAW, [], []))

    def test_processor_keeps_proposed_replacement_verbatim(self):
        with self.assertRaisesRegex(ValueError, "tone replacement"):
            validate_extracted_text("原片段：说白了，", {"edits": [edit(after="他猜想")]}, "tone")
        with self.assertRaisesRegex(ValueError, "tone original fragment"):
            validate_extracted_text("全文可保留", {"edits": [edit()]}, "tone")
        validate_extracted_text("全文可保留", {"edits": []}, "tone")
