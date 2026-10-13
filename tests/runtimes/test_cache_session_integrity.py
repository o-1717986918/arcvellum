import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from literary_engineering_studio.runtimes.source_repair_budget import SourceRepairBudget, text_digest
from literary_engineering_studio.runtimes.natural_repair_progress import SourceRepairProgress
from literary_engineering_studio.runtimes.natural_transport_repair import NaturalSourceClarificationError
from literary_engineering_studio.runtimes.scene_cache_layout import source_scope, validate_frozen_sources
from literary_engineering_studio.runtimes.natural_field_repair import field_repair_task


class CacheSessionIntegrityTests(unittest.TestCase):
    def test_restarts_and_combined_sources_share_the_original_four_call_budget(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); source="original author source"
            for index in range(4):
                budget=SourceRepairBudget(root,"creator",text_digest(source))
                budget.claim("transport" if index%2 else "source-author",str(index))
                source += "\npatch"
                budget.alias(text_digest(source))
            with self.assertRaisesRegex(ValueError,"budget exhausted"):
                SourceRepairBudget(root,"creator",text_digest(source)).claim("source-author","again")

    def test_restart_cannot_repeat_failed_field_values_without_progress(self):
        with TemporaryDirectory() as tmp:
            error=NaturalSourceClarificationError("invalid",fields=("/scene_delta",),payload={"scene_delta":{"value":1}})
            SourceRepairProgress(Path(tmp),"creator","source").register(error)
            with self.assertRaises(NaturalSourceClarificationError):
                SourceRepairProgress(Path(tmp),"creator","source").register(error)

    def test_field_repair_keeps_all_values_but_moves_mutating_digest_to_the_suffix(self):
        context={"prose":"原文", "request_layout":"stable-prefix-v2"}
        first=field_repair_task("source1",{"prose":"原文","scene_delta":{}},["/scene_delta"],context)
        second=field_repair_task("source2",{"prose":"原文","scene_delta":{}},["/scene_delta"],context)
        self.assertEqual(list(first)[-1],"source_sha256")
        first.pop("source_sha256"); second.pop("source_sha256")
        self.assertEqual(first,second)

    def test_evidence_repair_and_review_use_the_same_current_body_scope(self):
        class Runtime:
            def _cache_path(self,*args): return Path("unused")
        body="当前正文"; digest=sha256(body.encode()).hexdigest()
        self.assertEqual(source_scope(Runtime(),"t",json.dumps({"prose":body})),
                         source_scope(Runtime(),"t",json.dumps({"context":{"prose_source":{"sha256":digest}}})))

    def test_changed_canon_and_scene_brief_reject_frozen_context(self):
        class Brief:
            def to_dict(self):return {"scene_id":"one"}
        with TemporaryDirectory() as tmp:
            root=Path(tmp);(root/"canon.json").write_text("pending",encoding="utf-8")
            packet={"scene_brief":Brief().to_dict(),"canon_sources":[{"path":"canon.json","file_sha256":sha256(b"pending").hexdigest()}]}
            validate_frozen_sources(packet,root,Brief())
            (root/"canon.json").write_text("applied",encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,"Canon"):
                validate_frozen_sources(packet,root,Brief())
