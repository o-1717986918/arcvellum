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
    def test_adopting_existing_recovered_claims_is_idempotent_and_refreshes_stale_instances(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);old=SourceRepairBudget(root,'creator','clipped');full=SourceRepairBudget(root,'creator','full')
            old.claim('transport','old');full.claim('source-author','full')
            full.alias('full-with-patch')
            old.alias('full');old.alias('full')
            nested=SourceRepairBudget(root,'creator','full-with-patch')
            self.assertEqual(nested.origin,'clipped')
            full.claim('transport','third');nested.claim('source-author','fourth')
            with self.assertRaisesRegex(ValueError,'budget exhausted'):
                old.claim('source-author','fifth')
            self.assertEqual(len(json.loads(full._path('full').read_text())['calls']),1)
            self.assertEqual(json.loads(old.path.read_text())['lineage_members'],['full'])
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

    def test_exhausted_author_budget_is_explicit_and_keeps_exact_repair_scope(self):
        with TemporaryDirectory() as tmp:
            progress=SourceRepairProgress(Path(tmp),'creator','source')
            for value in range(4):
                progress.register(NaturalSourceClarificationError('bad link',
                    fields=('/consistency_record/facts/0/delta_summary',),
                    payload={'consistency_record':{'facts':[{'delta_summary':str(value)}]}}))
            failure=NaturalSourceClarificationError('bad link',
                fields=('/consistency_record/facts/0/delta_summary',),
                payload={'consistency_record':{'facts':[{'delta_summary':'new'}]}})
            with self.assertRaisesRegex(NaturalSourceClarificationError,'original source repair budget exhausted') as caught:
                progress.register(failure)
            self.assertEqual(caught.exception.fields,failure.fields)
            self.assertEqual(len(json.loads(progress.budget.path.read_text())['calls']),4)

    def test_granular_author_patch_preserves_valid_facts_and_rejects_broad_rewrite(self):
        from literary_engineering_studio.runtimes.natural_field_repair import apply_field_patch
        frozen={'prose':'当前正文','consistency_record':{'facts':[
            {'delta_summary':'差一个标点'},{'subject':'已正确事实','value':'保留'}]}}
        path='/consistency_record/facts/0/delta_summary'
        reply={'patches':[{'path':path,'op':'replace','value':'差一个标点。'}]}
        result=apply_field_patch(frozen,reply,[path])
        self.assertEqual(result['consistency_record']['facts'][1],frozen['consistency_record']['facts'][1])
        with self.assertRaises(ValueError):
            apply_field_patch(frozen,{'patches':[{'path':'/consistency_record','value':{}}]},[path])

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
            with self.assertRaisesRegex(RuntimeError,"scene source revision changed:.*Canon") as caught:
                validate_frozen_sources(packet,root,Brief())
            from unittest.mock import MagicMock
            from literary_engineering_studio.automation.lean_scene_loop import LeanSceneRunCoordinator
            from literary_engineering_studio_engine.public.literary import SceneExecutionMode, SceneTransactionStatus
            coordinator=object.__new__(LeanSceneRunCoordinator);coordinator.project=root;coordinator.service=MagicMock()
            coordinator.data_root=root/'studio-data'
            coordinator.service.prepare.return_value=MagicMock(scene_id='one',transaction_id='new',
                                                               status=SceneTransactionStatus.PREPARED,last_error='')
            stale=MagicMock(review=None,last_error=str(caught.exception),scene_id='one',mode=SceneExecutionMode.STANDARD)
            step=coordinator._resume_blocked(stale)
            self.assertEqual(step.action,'reprepared')
            self.assertEqual(step.transaction_id,'new')
            coordinator.service.resume.assert_not_called()
