"""Cache regressions preserve literary inputs, versions and historical completed work."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from literary_engineering_studio.runtimes.natural_creator_prompt import STABLE_PREFIX_LAYOUT, stable_creator_prompt
from literary_engineering_studio.runtimes.natural_transport_context import extraction_context
from literary_engineering_studio.runtimes.scene_material_cache import material_source_digests, material_source_bindings, cached_scene_result
from literary_engineering_studio.runtimes.scene_creator_natural import _creator_guidance
from literary_engineering_studio.runtimes.pi_scene_payload import creative_result_from_payload
from literary_engineering_studio.runtimes.semantic_cache import semantic_cache_digest, prior_review_context
from literary_engineering_studio.runtimes.scene_review_continuity import review_continuity
from literary_engineering_studio.application.creator_persona import CreatorPersonaStore
from literary_engineering_studio_engine.public.literary import VerificationReport
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
from tests.runtimes.test_less_ai_tone_experiment import runtime, brief
from tests.runtimes.test_scene_natural_output import NaturalGateway


def prefix_length(a, b):
    return next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))


class CacheHitOptimizationTests(unittest.TestCase):
    def test_migration_identities_share_one_source_capture(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); folder = root / "calls"; folder.mkdir()
            (folder / "one.json").write_text("{}", encoding="utf-8")
            before = b'{ "text": "original" }'; after = b'{"text":"changed"}'
            with patch.object(Path, "read_bytes", side_effect=[before, after]) as read:
                canonical, historical = material_source_bindings(root)
            name = str(Path("calls") / "one.json")
            self.assertEqual(historical[name], sha256(before).hexdigest())
            self.assertEqual(canonical[name], sha256(b'{"text":"original"}').hexdigest())
            self.assertEqual(read.call_count, 1)

    def test_stable_layout_preserves_all_values_and_exposes_a_longer_prefix(self):
        keys = ("bootstrap", "create", "revise", "delegation", "actor-card", "archive", "sandbox", "selection")
        layers = {f"scene.v2.creator.{key}": prompt_layer_spec(f"scene.v2.creator.{key}").default_text for key in keys}
        context = {"briefing": {"scene_brief": {"participants": ["乙", "甲"]}, "creator_persona": {"text": "人物自己的声音"}},
            "creator_memory": {"阶段": "取材", "札记": "尚缺回应"}, "material_index": "目录",
            "actor_card_context": {"frozen_scene_cards": [{"card": {"sections": {"声音": "完整原文" * 300}}}]}}
        changed = deepcopy(context); changed["creator_memory"]["札记"] = "已经收到回应"
        old = _creator_guidance(layers, "create", include_actor=False) + "\n\n本次创作资料：\n" + json.dumps(context, ensure_ascii=False)
        old_changed = _creator_guidance(layers, "revise", include_actor=False) + "\n\n本次创作资料：\n" + json.dumps(changed, ensure_ascii=False)
        new = stable_creator_prompt(layers, "create", context, include_actor=False)
        new_changed = stable_creator_prompt(layers, "revise", changed, include_actor=False)
        self.assertGreater(prefix_length(new, new_changed), prefix_length(old, old_changed))
        parsed = json.loads(new.split("本次创作资料：\n")[1])
        self.assertEqual(parsed.pop("phase_guidance"), layers["scene.v2.creator.create"])
        self.assertEqual(parsed, context)
        self.assertEqual(context["creator_memory"]["札记"], "尚缺回应")
        card_prompt = stable_creator_prompt(layers, "create", context, include_actor=True)
        self.assertEqual(json.loads(card_prompt.split("本次创作资料：\n")[1])["actor_card_design_guidance"],
                         layers["scene.v2.creator.actor-card"])

    def test_new_layout_is_frozen_and_existing_snapshot_does_not_upgrade(self):
        with TemporaryDirectory() as tmp:
            adapter = runtime(Path(tmp))
            snapshot = adapter._v2_prompt_snapshot("new")
            self.assertEqual(snapshot["creator_prompt_layout"], STABLE_PREFIX_LAYOUT)
            snapshot.pop("creator_prompt_layout")
            path = adapter._cache_path("new", "prompt_assembly_v2.json")
            path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(adapter._v2_prompt_snapshot("new"), snapshot)
            self.assertNotIn("creator_prompt_layout", adapter._v2_prompt_snapshot("new"))

    def test_json_layout_does_not_invalidate_but_content_order_and_knowledge_do(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); folder = root / "materials"; folder.mkdir()
            path = folder / "one.json"
            value = {"text": "原文\n完整保留。", "knowledge": "known", "history": ["甲", "乙"]}
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
            original = material_source_digests(root)
            raw = material_source_digests(root, legacy_bytes=True)
            path.write_text(json.dumps(dict(reversed(list(value.items()))), ensure_ascii=False), encoding="utf-8")
            self.assertEqual(material_source_digests(root), original)
            self.assertNotEqual(material_source_digests(root, legacy_bytes=True), raw)
            for delta in ({"text": "原文完整保留。"}, {"knowledge": "reference"}, {"history": ["乙", "甲"]}):
                path.write_text(json.dumps({**value, **delta}, ensure_ascii=False), encoding="utf-8")
                self.assertNotEqual(material_source_digests(root), original)

    def test_ambiguous_json_stays_byte_bound(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); folder = root / "calls"; folder.mkdir()
            path = folder / "one.json"
            raw = b'{"text":"old","text":"new"}'
            path.write_bytes(raw)
            self.assertEqual(material_source_digests(root)[str(Path("calls") / "one.json")], sha256(raw).hexdigest())

    def test_real_adapter_reuses_old_binding_and_cosmetic_edits_without_new_calls(self):
        with TemporaryDirectory() as tmp:
            adapter = runtime(Path(tmp), gateway=NaturalGateway())
            adapter._config["application"]["scene_creator_v2"] = {"enabled": True}
            CreatorPersonaStore(Path(tmp) / "data").save(adapter._project_root,
                "沿人物的迟疑与生活中的物件组织故事，让等待具有具体的声音。", reason="初始作者意图")
            scene = brief(); transaction = "cache-migrate"
            result = adapter.create_scene(transaction, scene)
            verification = VerificationReport(scene.scene_id, len(result.prose))
            review = adapter.review_scene(transaction, scene, result, verification)
            cache_root = adapter._cache_path(transaction, "")
            canonical = next(cache_root.glob("review_result_v3_*.json"))
            snapshot, briefing, workspace = adapter._v2_context(transaction, scene)
            coordinator = adapter._v2_coordinator(transaction, scene, snapshot["texts"], workspace)
            memory = adapter._creator_memory(transaction, scene)
            sources = {"materials": material_source_digests(coordinator.root, legacy_bytes=True),
                       "creator_intent": memory.intent.to_dict(), "material_decisions": memory.current_decisions(),
                       "unresolved_questions": memory.unresolved_questions}
            continuity = prior_review_context(review_continuity(cache_root, result.prose))
            digest = semantic_cache_digest("review", brief=scene, result=result, verification=verification,
                briefing=briefing, snapshot=snapshot, sources=sources, continuity=continuity)
            historical = cache_root / f"review_result_v3_{digest}.json"
            self.assertNotEqual(canonical, historical)
            historical.write_bytes(canonical.read_bytes())
            canonical.unlink()
            gateway = adapter._gateway
            counts = (gateway.creator_calls, gateway.material_calls, gateway.extract_calls)
            self.assertEqual(adapter.review_scene(transaction, scene, result, verification), review)
            self.assertTrue(canonical.with_suffix(".reuse.json").is_file())
            material = next(path for path in (coordinator.root / "materials").glob("*.json") if path.name != "index.json")
            data = json.loads(material.read_text(encoding="utf-8"))
            material.write_text(json.dumps(dict(reversed(list(data.items()))), ensure_ascii=False, indent=4), encoding="utf-8")
            self.assertEqual(adapter.review_scene(transaction, scene, result, verification), review)
            self.assertEqual((gateway.creator_calls, gateway.material_calls, gateway.extract_calls), counts)

    def test_validated_legacy_result_migrates_without_invocation(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); current = root / "current.json"; legacy = root / "legacy.json"
            body = "他攒姓，给未出生的孩子留名字。"
            legacy.write_text(json.dumps({"prose": body, "decision_summary": "保留奇幻词义",
                                         "scene_delta": {}}, ensure_ascii=False), encoding="utf-8")
            result = cached_scene_result(current, legacy, creative_result_from_payload)
            self.assertEqual(result.prose, body)
            self.assertTrue(current.with_suffix(".reuse.json").is_file())
            self.assertEqual(cached_scene_result(current, root / "missing.json", creative_result_from_payload).prose, body)
            self.assertTrue(legacy.is_file())
            current.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                cached_scene_result(current, legacy, creative_result_from_payload)

    def test_need_contract_is_part_of_extraction_identity(self):
        basic = extraction_context("creator", {"available_material_ids": []})
        strict = extraction_context("creator", {"available_material_ids": [], "material_need_contract": "v1"})
        self.assertNotEqual(basic, strict)
        self.assertEqual(strict["material_need_contract"], "v1")
