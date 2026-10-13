import json
from pathlib import Path
import tempfile
import unittest

from ruamel.yaml import YAML
from literary_engineering_studio_engine.public.literary import normalize_scene_window, materialize_lean_window
from literary_engineering_studio.application.lean_asset_enrichment import _validated_rows
from literary_engineering_studio_engine.public.literary import parse_describer_candidates, parse_environment_material
from literary_engineering_studio_engine.public.prompting import prompt_layer_scope, prompt_layer_spec, render_prompt_template
from literary_engineering_studio.runtimes.scene_performance import _cached_payload, _plan_for_requests
from literary_engineering_studio.runtimes.pi_scene_payload import _answer_payload


class NarrativeRangeTests(unittest.TestCase):
    def test_new_delegation_dispatches_macro_requests_without_an_independent_plan_call(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            payload = {"material_requests": [{"kind": "environment", "target": "森林"},
                       {"kind": "event-narration", "target": "一年风俗"}]}
            plan = _plan_for_requests({"scene_id": "s", "objective": "建立世界尺度"}, {}, "世界规则", payload,
                Path(directory), "digest", lambda *args: calls.append(args), "世界开场",
                {"scene.environment.identity": "环境创作者的初始化"}, True)
            self.assertEqual(calls, [])
            self.assertEqual(plan["environment_initialization"], "环境创作者的初始化")
            self.assertEqual(plan["beats"][0]["event"], "建立世界尺度")
    def test_prefaced_json_fence_preserves_prose_and_rejects_substantive_trailing_text(self):
        payload = {"prose": "先说森林的历法。\n\n整个夏季已经过去。", "material_decisions": []}
        source = "已读完素材，以下是交付。\n```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"
        self.assertEqual(_answer_payload(source), payload)
        with self.assertRaisesRegex(ValueError, "text after"):
            _answer_payload(source + "\n另一个正文结尾。")
    def test_failed_material_delivery_is_saved_and_can_be_reprocessed_without_another_call(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "material.json"
            calls = []
            original = {"answer": "完整原始素材", "payload": {"text": "完整原始素材"}}
            def produce():
                calls.append(1)
                return original
            def reject(payload):
                raise ValueError("来源札记格式需要修复")
            with self.assertRaises(ValueError):
                _cached_payload(path, produce, reject)
            self.assertEqual(json.loads(path.with_name("material.received.json").read_text(encoding="utf-8")), original)
            self.assertEqual(_cached_payload(path, produce, lambda payload: payload), original)
            self.assertEqual(len(calls), 1)
    def test_world_material_can_exceed_the_former_micro_description_limits(self):
        text = "森林在整季中改变道路与历法。" * 100
        parsed = parse_describer_candidates({"candidates": [{"text": text, "focus": "一季的风俗",
                  "basis": "confirmed", "source_note": "世界档案来处。" * 100}]}, "event-narration")
        self.assertEqual(parsed[0]["text"], text)
        environment = parse_environment_material({"scene_id": "s", "passages": [{"beat_id": "b1",
                    "description": text, "focal_character": ""}]}, {"scene_id": "s", "participants": []}, [{"beat_id": "b1"}])
        self.assertEqual(environment["passages"][0]["description"], text)

    def test_frozen_prompt_scope_restores_defaults_and_supports_nested_transactions(self):
        key = "scene.describer.turn.protocol"
        original = prompt_layer_spec(key).default_text
        with prompt_layer_scope({key: "旧交易的固定交付模板"}):
            self.assertEqual(prompt_layer_spec(key).default_text, "旧交易的固定交付模板")
            self.assertEqual(render_prompt_template(key, ()), "旧交易的固定交付模板\n")
            with prompt_layer_scope({key: "另一交易"}):
                self.assertEqual(prompt_layer_spec(key).default_text, "另一交易")
            self.assertEqual(prompt_layer_spec(key).default_text, "旧交易的固定交付模板")
        self.assertEqual(prompt_layer_spec(key).default_text, original)
    def test_world_narration_survives_normalization_and_materialization_without_staged_conflict(self):
        strategy = "叙述者俯看森林，概述整季风俗，带着亲昵的幽默。"
        scenes = normalize_scene_window([{"name": "森林的历法", "function": "建立世界尺度", "obligation": "认识森林的节日",
              "participants": [], "narrative_strategy": strategy}], {"scene_count": 1, "target_words": 1800,
              "chapter_id": "chapter_0001", "volume_id": "volume_01"}, start_index=1)
        self.assertEqual(scenes[0]["conflict"], "")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "plan.json"
            source.write_text("{}", encoding="utf-8")
            materialize_lean_window(root, scenes=scenes, obligations={"chapter_0001": {"literary_task": "让世界成为阅读乐趣"}},
                                    sources=(source,), outline_text="认识森林")
            scene = YAML(typ="safe").load((root / "scenes/scene_0001.yaml").read_text(encoding="utf-8"))
            self.assertEqual(scene["participants"], [])
            self.assertEqual(scene["narrative_strategy"], strategy)
            self.assertEqual(scene["narrative_rhythm"]["density_mix"], {})
            obligation = json.loads((root / "plot/chapter_obligations/chapter_0001.json").read_text(encoding="utf-8"))
            self.assertEqual(obligation["literary_task"], "让世界成为阅读乐趣")

    def test_character_enrichment_accepts_open_and_unwounded_personality(self):
        row = {"name": "节日精灵", "summary": "爱热闹的精灵", "appearance": "明亮", "clothing": "彩衣",
               "public_private_contrast": "都爱热闹", "moral_line": "信守约定", "hidden_wound": "", "reveal_policy": "open",
               **{key: [] for key in ("formative_events", "behavior_influences", "beliefs", "intentions", "fears", "secrets", "relationships")}}
        result = _validated_rows({"characters": [row]}, {"节日精灵": Path("card.yaml")})
        self.assertEqual(result[0]["hidden_wound"], "")
        self.assertEqual(result[0]["reveal_policy"], "open")
