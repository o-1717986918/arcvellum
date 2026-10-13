"""Integration checks for source-backed demand, unchanged input reuse and lossless cards."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from literary_engineering_studio.runtimes.creator_context_projection import deduplicate_cards
from literary_engineering_studio.runtimes.material_need import (
    NEED_MARKER, require_source_needs, record_source_needs, validate_need,
)
from literary_engineering_studio.runtimes.natural_transport_repair import NaturalSourceClarificationError
from literary_engineering_studio.runtimes.scene_creator_material_context import natural_material_invitation
from literary_engineering_studio.runtimes.scene_creator_v2_materials import SceneCreatorV2MaterialCoordinator, MaterialInvocationV2
from literary_engineering_studio.runtimes.material_input_reuse import input_identity
from literary_engineering_studio.runtimes.scene_creator_workspace import SceneCreatorWorkspace
from literary_engineering_studio_engine.public.literary import parse_scene_material_requests_v4, parse_creator_material_plan
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
from tests.material_need_fixtures import with_need
from tests.runtimes.test_scene_natural_output import REQUEST


class MaterialNeedEfficiencyTests(unittest.TestCase):
    def test_reuse_binding_invalidates_sources_knowledge_style_and_actor_history(self):
        manifest = ({"path": "facts.md", "knowledge": "known", "file_sha256": "version1", "line_range": [1, 2]},)
        call = MaterialInvocationV2("character-actor", "十一块完整卡", "新的来话", "bookkeeping-id", manifest)
        original = input_identity(call, "s1", {})
        self.assertEqual(input_identity(replace(call, request_id="another-id"), "s1", {}), original)
        changes = [
            replace(call, prompt="另一刺激"), replace(call, initialization="另一版本的完整卡"),
            replace(call, history=(("已发生的来话", "采用后的回应"),)),
            replace(call, attachment_manifest=({**manifest[0], "knowledge": "reference"},)),
            replace(call, attachment_manifest=({**manifest[0], "file_sha256": "version2"},)),
            replace(call, attachment_manifest=({**manifest[0], "line_range": [2, 2]},)),
        ]
        for changed in changes:
            self.assertNotEqual(input_identity(changed, "s1", {}), original)

    def test_missing_or_invented_need_is_scoped_to_metadata(self):
        row = deepcopy(REQUEST); row.pop("need_evidence")
        with self.assertRaises(NaturalSourceClarificationError) as caught:
            require_source_needs(json.dumps(row, ensure_ascii=False), {"material_requests": [row]},
                                 {"material_need_contract": "v1"})
        self.assertEqual(caught.exception.fields, ("/material_requests/0/need_evidence",))
        row = deepcopy(REQUEST)
        with self.assertRaisesRegex(NaturalSourceClarificationError, "不能代写"):
            require_source_needs(row["author_prompt"], {"material_requests": [row]},
                                 {"material_need_contract": "v1"})

    def test_existing_material_needs_source_excerpt_and_each_mount_reason(self):
        row = with_need({**REQUEST, "material_attachments": [{"candidate_id": "one"}]},
                        reviewed=["one"], excerpts={"one": "雨落旧碗"})
        validate_need(row["need_evidence"], row, {"one"}, {"one": {"text": "雨落旧碗，手停住。"}})
        with self.assertRaisesRegex(ValueError, "原文证据"):
            validate_need(row["need_evidence"], row, {"one"}, {"one": {"text": "新的刺激。"}})
        broken = deepcopy(row["need_evidence"]); broken["mount_reasons"] = {}
        with self.assertRaisesRegex(ValueError, "每项挂载"):
            validate_need(broken, row, {"one"})
        with self.assertRaisesRegex(ValueError, "原文片段"):
            validate_need({**row["need_evidence"], "existing_material_evidence": {}}, row, {"one"})

    def test_new_subject_does_not_require_reading_unrelated_material(self):
        row = with_need(REQUEST)
        sources = {"other": {"kind": "actor", "target": "别人", "text": "无关回应"}}
        validate_need(row["need_evidence"], row, set(sources), sources)
        sources["related"] = {"kind": row["kind"], "target": row["target"], "text": "已有相关观察"}
        with self.assertRaisesRegex(ValueError, "同一对象已有回应"):
            validate_need(row["need_evidence"], row, set(sources), sources)

    def test_source_bound_dispatch_and_same_input_bookkeeping_reuse(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); work = root / "work"; work.mkdir()
            (work / "project.yaml").write_text("title: source", encoding="utf-8")
            layers = {"scene.v2.creator.delegation": NEED_MARKER, "scene.v2.transport.extractor": "整理",
                      "scene.v2.material.environment": prompt_layer_spec("scene.v2.material.environment").default_text,
                      "scene.v2.material.actor": prompt_layer_spec("scene.v2.material.actor").default_text}
            coordinator = SceneCreatorV2MaterialCoordinator(root / "tx",
                SceneCreatorWorkspace(work, root / "data"), layers, scene_id="s1")
            coordinator.save_plan(parse_creator_material_plan({"material_plan":
                {"required_kinds": ["environment"], "reason": "直接观察"}}))
            request, = parse_scene_material_requests_v4({"material_requests": [REQUEST]}, [])
            invoked = []
            def invoke(call):
                invoked.append(call)
                return {"candidates": [{"text": "雨落旧碗，手停住。", "focus": "节奏"}], "__answer": "雨落旧碗，手停住。"}
            with self.assertRaisesRegex(ValueError, "尚无经原文校验"):
                coordinator.execute(request, invoke)
            self.assertEqual(invoked, [])
            source = json.dumps({"material_requests": [REQUEST]}, ensure_ascii=False)
            require_source_needs(source, {"material_requests": [REQUEST]}, {"material_need_contract": "v1"})
            provenance = {"source_sha256": sha256(source.encode()).hexdigest()}
            independent = replace(request, cue="第二个独立观察时刻")
            record_source_needs(coordinator, [request, independent], provenance)
            first = coordinator.execute(request, invoke)
            coordinator.execute(independent, invoke)
            identifier = first[0]["candidate_id"]
            evidence = {**request.need_evidence, "gap": "同一观察的记账表述",
                        "reviewed_candidate_ids": [identifier], "existing_material_evidence": {identifier: "雨落旧碗"}}
            same = replace(request, need_evidence=evidence)
            record_source_needs(coordinator, [same], provenance)
            self.assertEqual(coordinator.execute(same, invoke), first)
            self.assertEqual(len(invoked), 2)
            self.assertEqual(len(list((coordinator.root / "reused-inputs").glob("*.json"))), 1)
            changed = replace(same, cue="有人打翻了旧碗")
            record_source_needs(coordinator, [changed], provenance)
            coordinator.execute(changed, invoke)
            self.assertEqual(len(invoked), 3)

    def test_equal_card_is_delivered_once_and_different_versions_remain(self):
        card = {"target": "阿青", "sections": {"one": "完整原文"}}
        context = {"frozen_scene_cards": [{"digest": "abc", "card": card}],
                   "work_cards": [{"source": "cards/a.json", "card": card},
                                  {"card": {**card, "sections": {"one": "另一版本"}}}]}
        projected = deduplicate_cards(context)
        self.assertEqual(projected["frozen_scene_cards"][0]["card"], card)
        self.assertNotIn("card", projected["work_cards"][0])
        self.assertEqual(projected["work_cards"][0]["card_ref"]["digest"], "abc")
        self.assertIn("card", projected["work_cards"][1])
        self.assertIn("card", context["work_cards"][0])

    def test_invitation_exact_contained_details_do_not_repeat_or_truncate(self):
        text = "你在门边，刚听见铜靴说话。" + "完整长过程。" * 2000
        task = {"kind": "environment", "target": "门边", "purpose": "完整长过程。",
                "cue": "铜靴说话", "working_context": "你在门边", "author_prompt": text}
        rendered = natural_material_invitation(task)
        self.assertEqual(rendered.count("你在门边"), 1)
        self.assertIn(text, rendered)
        self.assertEqual(task["author_prompt"], text)
