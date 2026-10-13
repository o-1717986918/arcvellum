"""Offline regressions for frozen prose, current choices and focused editing."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from literary_engineering_studio.runtimes.natural_field_repair import apply_field_patch
from literary_engineering_studio.runtimes.natural_transport_repair import NaturalExtractionError
from literary_engineering_studio.runtimes.scene_creator_memory import SceneCreatorMemoryV1
from literary_engineering_studio.runtimes.scene_creator_workspace import SceneCreatorWorkspace
from literary_engineering_studio.runtimes.scene_creator_material_context import freeze_material_selections
from literary_engineering_studio.runtimes.scene_creator_v2_materials import _adopted_actor_history
from literary_engineering_studio.runtimes.semantic_cache import semantic_cache_digest
from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
from literary_engineering_studio.runtime.role_conversation import RoleConversationResult
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
from literary_engineering_studio_engine.public.literary import CreativeResult,SceneDelta,VerificationReport
from literary_engineering_studio_engine.public.literary import parse_scene_material_requests_v4
from tests.runtimes.test_less_ai_tone_experiment import brief,runtime
from tests.runtimes.test_scene_natural_output import REQUEST


class CostOptimizationTests(unittest.TestCase):
    def test_only_original_reviewer_can_withdraw_an_unsupported_finding_and_change_verdict_in_scope(self):
        frozen={"decision":"revise","summary":"旧判断","strengths":[{"claim":"有效优点","evidence":"当前正文"}],
                "major_issues":[{"title":"无依据问题","evidence":"不存在"}]}
        fields=("/major_issues/0","/decision","/summary")
        reply={"patches":[{"path":"/major_issues/0","op":"remove"},
            {"path":"/decision","value":"pass"},{"path":"/summary","value":"原审读者确认撤回无依据问题"}]}
        result=apply_field_patch(frozen,reply,fields)
        self.assertEqual(result["major_issues"],[])
        self.assertEqual(result["strengths"],frozen["strengths"])
        self.assertEqual(result["decision"],"pass")
        self.assertEqual(frozen["decision"],"revise")
    def test_adapt_history_uses_actual_body_landing_and_does_not_promote_indirect_reference(self):
        rows=[{"candidates":[{"candidate_id":"one","text":"尚未实际发生的完整提案","source_delivery":"original-v2"}]}]
        choices={"one":{"decision":"adapt","prose_excerpt":"阿青在门边停下。","prose_excerpt_verified":True}}
        history=_adopted_actor_history(rows,{"one"},choices)
        self.assertEqual(history[0][1],"阿青在门边停下。")
        choices={"one":{"decision":"adapt","indirect_use":"仅借人物理解组织结构"}}
        self.assertEqual(_adopted_actor_history(rows,{"one"},choices),())
    def test_mechanical_trailing_spaces_are_local_and_preserve_words_and_paragraphs(self):
        with TemporaryDirectory() as tmp:
            adapter=runtime(Path(tmp))
            prose="他攒姓。  \n\n阿青仍在等。"
            result=CreativeResult(prose,"等待",SceneDelta())
            path=adapter._cache_path("format","editor-focus/"+sha256(prose.encode()).hexdigest()+".json")
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"focus":[{"issue":"清理段末空格","excerpt":prose,"operation":"trailing-whitespace"}]}),encoding="utf-8")
            value=adapter._tone_result("format",brief(),result,adapter._tone_mount("format",brief()),"create")
            self.assertEqual(value.prose,"他攒姓。\n\n阿青仍在等。")
            self.assertEqual(result.prose,prose)
            self.assertEqual(adapter._gateway.calls,[])
    def test_repeated_candidate_mounts_merge_without_changing_original_ranges(self):
        identifier="v2:abc:1"
        request,=parse_scene_material_requests_v4({"material_requests":[{**REQUEST,"material_attachments":[
            {"candidate_id":identifier,"start_char":0,"end_char":5},
            {"candidate_id":identifier,"start_char":3,"end_char":8}]}]},[])
        rows=freeze_material_selections(request.material_attachments,
            {identifier:{"kind":"environment","text":"abcdefghij","target":"雨"}})
        self.assertEqual(len(rows),1)
        self.assertEqual((rows[0]["content"],rows[0]["char_range"]),("abcdefgh",[0,8]))
        self.assertEqual(len(rows[0]["original_selectors"]),2)
    def test_field_patch_keeps_body_and_review_judgment(self):
        frozen = {"prose":"他攒姓，给未出生的孩子留名字。","decision":"revise",
                  "major_issues":[{"title":"声音","evidence":"错引"}]}
        patch = {"patches":[{"path":"/major_issues/0/evidence","value":"他攒姓"}]}
        fixed = apply_field_patch(frozen,patch,("/major_issues/0/evidence",))
        self.assertEqual((fixed["prose"],fixed["decision"]),(frozen["prose"],"revise"))
        self.assertEqual(frozen["major_issues"][0]["evidence"],"错引")
        for field in ("/prose","/decision","/major_issues"):
            with self.subTest(field=field),self.assertRaises(NaturalExtractionError):
                apply_field_patch(frozen,{"patches":[{"path":field,"value":"改写"}]},("/major_issues/0/evidence",))

    def test_saved_field_patch_replays_without_model_and_preserves_parent(self):
        with TemporaryDirectory() as tmp:
            processor = NaturalOutputProcessor(Path(tmp),prompt_layer_spec("scene.v2.transport.extractor").default_text,
                lambda *_:self.fail("whole JSON patch is locally recoverable"))
            source = "请修声音。引句：攒盘缠。"
            prose = "他攒姓，给未出生的孩子留名字。"
            frozen = {"decision":"revise","summary":"保留设定","major_issues":[
                {"title":"声音","evidence":"攒盘缠","reader_effect":"距离","direction":"靠近人物"}]}
            reply = json.dumps({"patches":[{"path":"/major_issues/0/evidence","value":"他攒姓"}]},ensure_ascii=False)
            kwargs = dict(kind="review",context={"prose":prose},payload=frozen,fields=("/major_issues/0/evidence",))
            first = processor.process_field_repair(source,reply,**kwargs)
            again = processor.process_field_repair(source,reply,**kwargs)
            self.assertEqual(again["decision"],"revise")
            self.assertEqual(first["major_issues"][0]["evidence"],"他攒姓")
            self.assertEqual(again["__transport"]["model_calls"],0)
            self.assertEqual(first["field_repair_provenance"]["parent_source_sha256"],sha256(source.encode()).hexdigest())

    def test_complete_history_and_last_decision_projection(self):
        memory = SceneCreatorMemoryV1("s1")
        memory.material_decisions = [{"candidate_id":str(i),"decision":"use","reason":"长"*300} for i in range(60)]
        memory.material_decisions.extend([{"candidate_id":"1","decision":"discard","reason":"改稿舍弃"},
                                         {"candidate_id":"2","decision":"adapt","reason":"保留结构"},
                                         {"candidate_id":"3","decision":"defer","reason":"留待下章"}])
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/"memory.json"; memory.save(path)
            restored = SceneCreatorMemoryV1.load(path,"s1")
        self.assertEqual(len(restored.material_decisions),63)
        current = {row["candidate_id"]:row for row in restored.current_decisions()}
        self.assertEqual((current["1"]["decision"],current["2"]["decision"],current["3"]["decision"]),("discard","adapt","defer"))
        self.assertEqual(len(current["0"]["reason"]),300)
        self.assertEqual(len(json.loads(restored.render_context())["material_decisions"]),60)

    def test_overlapping_mounts_merge_with_sources_and_knowledge_partitions(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)/"work";root.mkdir();(root/"project.yaml").write_text("title: test",encoding="utf-8")
            (root/"facts.md").write_text("甲\n乙\n丙\n",encoding="utf-8")
            workspace=SceneCreatorWorkspace(root,Path(tmp)/"data")
            rows=[{"path":"facts.md","start_line":1,"end_line":2,"knowledge":"known"},
                  {"path":"facts.md","start_line":2,"end_line":3,"knowledge":"known"},
                  {"path":"facts.md","start_line":2,"end_line":3,"knowledge":"reference"}]
            merged=workspace.freeze_attachments(rows,kind="actor")
            self.assertEqual(len(merged),2)
            self.assertEqual((merged[0]["content"],merged[0]["line_range"]),("甲\n乙\n丙\n",[1,3]))
            self.assertEqual(merged[1]["knowledge"],"reference")
            self.assertEqual(len(merged[0]["original_selectors"]),2)
            with self.assertRaises(ValueError):
                workspace.freeze_attachments([{"path":"facts.md"},{"path":"facts.md","start_line":1,"end_line":99}],kind="environment")

    def test_adapt_enters_actor_history_and_later_discard_leaves(self):
        with TemporaryDirectory() as tmp:
            adapter=runtime(Path(tmp),enabled=False)
            memory=SceneCreatorMemoryV1("s1")
            memory.pending_request={"material_requests":[REQUEST]}
            memory.material_decisions=[{"candidate_id":"used","decision":"use","reason":"回应"},
                {"candidate_id":"adapted","decision":"adapt","reason":"化用"},
                {"candidate_id":"used","decision":"discard","reason":"后稿舍下"}]
            received=[]
            coordinator=SimpleNamespace(material_scope={},root=Path(tmp)/"coordinator",
                execute=lambda *args,**kw:received.append(kw["adopted_candidate_ids"]))
            adapter._fulfill_v2_pending(memory,Path(tmp)/"memory.json",brief(),coordinator,"tx")
            self.assertEqual(received,[{"adapted"}])

    def test_cache_binds_body_style_sources_and_review_but_not_effort(self):
        value=dict(brief=brief(),result=CreativeResult("攒姓","意图",SceneDelta()),
            verification=VerificationReport("s1",2),briefing={"style":"原风格"},snapshot={"digest":"a","texts":{"review":"合同"}},
            sources={"known":"a","reference":"b"},continuity={"completed_revisions":0,"open_issues":[{"id":"x"}]})
        original=semantic_cache_digest("review",**value)
        changed=deepcopy(value);changed["continuity"]["completed_revisions"]=99
        self.assertEqual(original,semantic_cache_digest("review",**changed))
        for key,replacement in (("briefing",{"style":"新风格"}),("sources",{"known":"c","reference":"b"}),
                                ("continuity",{"open_issues":[{"id":"y"}]})):
            changed={**value,key:replacement}
            self.assertNotEqual(original,semantic_cache_digest("review",**changed))

    def test_fantasy_word_edit_stays_a_candidate_without_new_author_loop(self):
        class Gateway:
            calls=0
            def run(self,root,prompt,**kwargs):
                self.calls+=1
                value=json.loads(prompt)
                if value["call_purpose"]=="local-edit":
                    answer="原片段「攒姓」，改为「攒盘缠」。建议靠近日常。"
                else:
                    answer=json.dumps({"edits":[{"rule_id":"9","before":"攒姓","after":"攒盘缠","reason":"靠近日常"}],"summary":"一条候选"},ensure_ascii=False)
                return RoleConversationResult("pi-worker","test","test/model",answer)
        with TemporaryDirectory() as tmp:
            gateway=Gateway();adapter=runtime(Path(tmp),gateway=gateway)
            prose="他攒姓，给未出生的孩子留名字。";result=CreativeResult(prose,"奇幻姓名制度",SceneDelta())
            digest=sha256(prose.encode()).hexdigest()
            path=adapter._cache_path("tx","editor-focus/"+digest+".json")
            path.parent.mkdir(parents=True);path.write_text(json.dumps({"focus":[{"issue":"这个词的语气","excerpt":prose}]}),encoding="utf-8")
            mount=adapter._tone_mount("tx",brief())
            self.assertIs(adapter._tone_result("tx",brief(),result,mount,"create"),result)
            self.assertEqual(adapter._tone_candidates("tx",prose)["candidates"][0]["after"],"攒盘缠")
            adapter._tone_result("tx",brief(),result,mount,"create")
            self.assertEqual(gateway.calls,2)
            self.assertEqual(result.prose,prose)
