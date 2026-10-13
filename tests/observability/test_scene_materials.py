import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from literary_engineering_studio.observability.scene_materials import scene_material_detail
from literary_engineering_studio.observability.scene_rehearsals import scene_rehearsal_index


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class SceneMaterialInspectionTests(unittest.TestCase):
    def test_transport_statistics_preserve_calls_and_reuse_without_query_writes(self):
        path=self.cache/'v2/natural-answers/source/one.transport.json'
        write(path,{'schema':'arcvellum/natural-transport/v1','record_id':'one','operation':'creator',
            'mode':'reused','initial_mode':'model','model_calls':1,'reuse_count':3,'requested_thinking':'off'})
        before=path.read_bytes()
        result=scene_material_detail(self.root,[self.tx],'tx-one')
        self.assertEqual(result['transport']['model_calls'],1)
        self.assertEqual(result['transport']['reuse_count'],3)
        self.assertEqual(path.read_bytes(),before)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / "scene-transactions" / "tx-one"
        self.tx = SimpleNamespace(transaction_id="tx-one", scene_id="scene_0001",
                                  status=SimpleNamespace(value="committed"), brief=SimpleNamespace(objective="认识世界"))

    def test_complete_long_discarded_material_and_private_fiction_are_available(self):
        identity = "t1:1"
        filename = hashlib.sha256(identity.encode()).hexdigest()[:24] + ".json"
        long = "森林换季了。\n" * 1500
        write(self.cache / "materials" / "index.json", {"entries": [{"candidate_id": identity, "kind": "actor", "file": filename}]})
        write(self.cache / "materials" / filename, {"candidate_id": identity, "kind": "actor", "target": "甲",
              "content": {"entry_id": identity, "speaker": "甲", "spoken": long, "private_impulse": "我在期待节日。"}})
        write(self.cache / "scene_creator_memory.json", {"material_decisions": [{"candidate_id": identity,
              "decision": "discard", "reason": "本段采用时间概述。"}]})
        result = scene_material_detail(self.root, [self.tx], "tx-one")
        self.assertEqual(result["materials"][0]["spoken"], long)
        self.assertEqual(result["materials"][0]["private_impulse"], "我在期待节日。")
        self.assertEqual(result["materials"][0]["decision"], "discard")
        self.assertTrue(result["materials"][0]["complete"])
        self.assertEqual(len(scene_rehearsal_index(self.root, [self.tx])), 1)

    def test_v2_calls_keep_original_delivery_attachments_and_all_candidates(self):
        raw = "# 秋日\n\n树林举行了一场节庆。\n\n# 札记\n讲述一整季。"
        write(self.cache / "v2/calls/one.json", {"sequence": 1, "request_id": "request-one",
              "request": {"kind": "event-narration", "target": "森林", "purpose": "介绍节庆", "scene_moment": "一整季"},
              "attachment_manifest": [{"path": "canon/world.yaml", "file_sha256": "abc"}], "answer": raw,
              "candidates": [{"candidate_id": "event-one", "text": raw, "basis": "confirmed", "source_note": "世界档案"}]})
        result = scene_material_detail(self.root, [self.tx], "tx-one")
        self.assertEqual(result["calls"][0]["raw_response"], raw)
        self.assertEqual(result["materials"][0]["text"], raw)
        self.assertEqual(result["materials"][0]["attachments"][0]["file_sha256"], "abc")

    def test_membership_and_tampered_paths_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, "does not belong"):
            scene_material_detail(self.root, [], "tx-one")
        write(self.cache / "materials/index.json", {"entries": [{"candidate_id": "x", "file": "../outside.json"}]})
        result = scene_material_detail(self.root, [self.tx], "tx-one")
        self.assertEqual(result["materials"], [])
        self.assertTrue(result["warnings"])

    def test_failed_first_delivery_stays_listed_and_original_response_is_readable(self):
        raw = "森林的历史原稿。来源：已确认规则与创作提案。"
        write(self.cache / "describer-first.received.json", {"answer": raw,
              "request": {"kind": "event-narration", "target": "森林", "purpose": "世界开场"},
              "payload": {"candidates": []}})
        self.tx.status.value = "blocked"
        result = scene_material_detail(self.root, [self.tx], "tx-one")
        self.assertEqual(result["calls"][0]["raw_response"], raw)
        self.assertEqual(result["calls"][0]["delivery_status"], "received")
        self.assertEqual(len(scene_rehearsal_index(self.root, [self.tx])), 1)
