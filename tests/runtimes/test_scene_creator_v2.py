"""Focused v2 security and continuity contracts; the prompt text remains dormant."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from literary_engineering_studio.application.creator_persona import CreatorPersonaStore
from literary_engineering_studio.runtimes.scene_creator_briefing import build_scene_creator_briefing
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.scene_creator_memory import SceneCreatorMemoryV1
from literary_engineering_studio.runtime.role_conversation import RoleConversationResult
from literary_engineering_studio.runtimes.scene_creator_v2_materials import (
    SceneCreatorV2MaterialCoordinator, assert_v2_prompts_ready,
)
from literary_engineering_studio.runtimes.scene_creator_workspace import SceneCreatorWorkspace
from literary_engineering_studio_engine.public.literary import (
    LengthTarget, RhythmDirective, SceneBrief, SceneRisk, SceneRiskLevel, StyleMountRef,
    parse_creator_material_plan, parse_scene_material_requests_v3,
    parse_scene_material_requests_v4,
)
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
from tests.actor_card_fixtures import actor_card_payload


class SceneCreatorV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "work"
        self.project.mkdir()
        (self.project / "project.yaml").write_text("creative_brief:\n  premise: 雨中的信\n", encoding="utf-8")
        (self.project / "canon").mkdir()
        (self.project / "canon/world_rules.yaml").write_text("雨会留下痕迹。\n", encoding="utf-8")
        (self.project / "characters").mkdir()
        (self.project / "characters/阿青.yaml").write_text("姓名：阿青\n秘密：信已烧毁\n", encoding="utf-8")
        self.studio = self.root / "studio"

    def test_archive_mount_and_scratch_isolation(self) -> None:
        workspace = SceneCreatorWorkspace(self.project, self.studio)
        self.assertIn("characters/阿青.yaml", [row["path"] for row in workspace.list_archive()["entries"]])
        self.assertEqual(workspace.search_archive("信已烧毁")["matches"][0]["line"], 2)
        whole = workspace.freeze_attachments([{"path": "characters/阿青.yaml", "knowledge": "reference"}], kind="actor")
        part = workspace.freeze_attachments([{"path": "characters/阿青.yaml", "start_line": 1,
                                              "end_line": 1, "knowledge": "known"}], kind="actor")
        self.assertIn("秘密", whole[0]["content"])
        self.assertNotIn("秘密", part[0]["content"])
        self.assertEqual(part[0]["line_range"], [1, 1])
        page = workspace.read_archive("characters/阿青.yaml", max_chars=5)
        self.assertFalse(page["complete"])
        self.assertEqual(workspace.read_archive("characters/阿青.yaml", offset=page["next_offset"])["content"],
                         (self.project / "characters/阿青.yaml").read_text(encoding="utf-8")[5:])
        with self.assertRaisesRegex(ValueError, "context budget"):
            workspace.freeze_attachments([{"path": "characters/阿青.yaml", "knowledge": "known"}],
                                         kind="actor", budget_chars=3)
        with self.assertRaises(ValueError):
            workspace.read_archive("../outside.txt")
        workspace.write_scratch("chapter/notes.md", "保留疑问")
        self.assertEqual(SceneCreatorWorkspace(self.project, self.studio).read_scratch("chapter/notes.md"), "保留疑问")
        with self.assertRaises(ValueError):
            workspace.write_scratch("../canon/world_rules.yaml", "改写")
        self.assertIn("雨会留下痕迹", (self.project / "canon/world_rules.yaml").read_text(encoding="utf-8"))

    def test_actor_history_is_built_from_creator_adopted_material(self) -> None:
        workspace = SceneCreatorWorkspace(self.project, self.studio)
        layers = {key: "designed" for key in (
            "scene.v2.material.shared.protocol", "scene.v2.material.output.protocol")}
        layers["scene.v2.material.actor"] = prompt_layer_spec("scene.v2.material.actor").default_text
        coordinator = SceneCreatorV2MaterialCoordinator(
            self.root / "tx-history", workspace, layers, scene_id="s1")
        coordinator.save_plan(parse_creator_material_plan({"material_plan": {
            "required_kinds": ["actor"], "reason": "承接人物上一轮回应"}}))

        request = parse_scene_material_requests_v3({"material_requests": [{
            "kind": "actor", "target": "阿青", "purpose": "回应追问", "scene_moment": "她听见追问时",
            "cue": "有人问信去了哪里", "author_prompt": "写出阿青当下的回应。",
            "character_card": actor_card_payload(), "archive_attachments": [],
        }]}, ["阿青"])[0]
        first, = coordinator.execute(request, lambda _call: {
            "candidates": [{"spoken": "信呢？", "first_person_action": "我捏住信封。",
                            "private_impulse": "我怕她已经走了。", "focus": "迟疑"}],
            "__answer": "我捏住信封。‘信呢？’我问。陶婶说：‘回家吧。’",
        })
        followup = parse_scene_material_requests_v3({"material_requests": [{
            "kind": "actor", "target": "阿青", "purpose": "接住回应后的压力",
            "scene_moment": "陶婶听见追问后停手时", "cue": "陶婶没有立刻回答",
            "author_prompt": "从阿青听到停顿后的感受继续。", "archive_attachments": [],
        }]}, ["阿青"])[0]
        memory = SceneCreatorMemoryV1(
            scene_id="s1", material_decisions=[{"candidate_id": first["candidate_id"],
                "decision": "use", "reason": "让追问成为本轮已发生的来话"}],
            pending_request={"material_requests": [followup.to_dict()]})
        runtime = PiSceneTransactionRuntime({}, project_root=self.project, data_root=self.studio)
        invoked = []
        runtime._invoke_v2_material = lambda call, _transaction_id: invoked.append(call) or {
            "candidates": [{"spoken": "我还没说完。", "focus": "迟疑"}],
            "__answer": "我还没说完。",
        }
        brief = SceneBrief("s1", "寻找信", "让追问形成压力", ("阿青",), (), (), (),
            RhythmDirective(), LengthTarget(), StyleMountRef(), SceneRisk(SceneRiskLevel.LOW), ())
        runtime._fulfill_v2_pending(memory, self.root / "scene_creator_memory.json", brief,
            coordinator, "tx-history")

        self.assertEqual(len(invoked), 1)
        self.assertEqual(invoked[0].history, (("主创选用的本角色上一轮表达",
            "台词：信呢？\n动作：我捏住信封。\n内心冲动：我怕她已经走了。"),))

    def test_persona_version_and_briefing_provenance(self) -> None:
        store = CreatorPersonaStore(self.studio)
        self.assertEqual(store.save(self.project, "让人物语言呈现克制之下的强烈情绪，并持续维护读者对遗失信件的疑问。",
                                    reason="作品初始要求")["version"], 1)
        with self.assertRaisesRegex(ValueError, "changed user direction"):
            store.save(self.project, "改为轻快且明亮的叙述，让人物关系变得温暖而流动。", reason="没有新的用户方向")
        (self.project / "project.yaml").write_text("creative_brief:\n  premise: 雨里的新标题\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed user direction"):
            store.save(self.project, "改为轻快且明亮的叙述，让人物关系变得温暖而流动。", reason="只有档案改动")
        direction = self.project / "workflow/studio/user_directions.jsonl"
        direction.parent.mkdir(parents=True)
        direction.write_text('{"message":"更丰沛的人声"}\n', encoding="utf-8")
        (direction.parent / "user_directions.md").write_text("用户希望更丰沛的人声。\n", encoding="utf-8")
        self.assertEqual(store.save(self.project, "让对话更丰沛，同时维持误会与人物关系的连续性。",
                                    reason="用户明确更新人声要求")["version"], 2)
        previous = self.project / "drafts/scenes/s1.md"
        previous.parent.mkdir(parents=True)
        previous.write_text("上一场正文。\n最后一行是雨里的脚步。", encoding="utf-8")
        delta = self.project / "workflow/scene_deltas/s1.json"
        delta.parent.mkdir(parents=True)
        delta.write_text(json.dumps({"next_handoff": ["脚步声仍在"],
                                     "reader_question_updates": ["谁拿了信"]}, ensure_ascii=False), encoding="utf-8")
        brief = SceneBrief("s2", "寻找信", "读者意识到误会", ("阿青",), ("雨会留下痕迹",),
                           ("上一场遗失信",), ("兑现遗失的承诺",), RhythmDirective(), LengthTarget(),
                           StyleMountRef(), SceneRisk(SceneRiskLevel.LOW),
                           ("drafts/scenes/s1.md", "workflow/scene_deltas/s1.json", "canon/world_rules.yaml"))
        packet = build_scene_creator_briefing(brief, SceneCreatorWorkspace(self.project, self.studio), store)
        self.assertEqual(packet["creator_persona"]["version"], 2)
        self.assertEqual(packet["canon_constraints"]["items"], ["雨会留下痕迹"])
        by_name = {row["name"]: row for row in packet["source_entries"]}
        self.assertIn("脚步", by_name["previous_committed_prose"]["content"])
        self.assertIn("谁拿了信", by_name["previous_scene_delta"]["content"])
        self.assertEqual(by_name["whole_work_intent"]["status"], "missing")

    def test_required_calls_and_frozen_attachments(self) -> None:
        workspace = SceneCreatorWorkspace(self.project, self.studio)
        plan = parse_creator_material_plan({"material_plan": {
            "required_kinds": ["actor", "environment"], "reason": "先听人物，再观察雨声"}})
        actor = parse_scene_material_requests_v3({"material_requests": [{
            "kind": "actor", "target": "阿青", "purpose": "维持误会", "scene_moment": "她发现空信封时",
            "cue": "只知道信封是空的", "author_prompt": "让她根据自己的处境自主回应。",
            "character_card": actor_card_payload(),
            "archive_attachments": [
                {"path": "characters/阿青.yaml", "start_line": 1, "end_line": 1, "knowledge": "known"},
                {"path": "characters/阿青.yaml", "start_line": 2, "end_line": 2, "knowledge": "reference"},
            ]}]}, ["阿青"])[0]
        layers = {key: "designed" for key in (
            "scene.v2.material.shared.protocol", "scene.v2.material.output.protocol",
            "scene.v2.material.actor", "scene.v2.material.environment")}
        layers["scene.v2.material.actor"] = prompt_layer_spec("scene.v2.material.actor").default_text
        coordinator = SceneCreatorV2MaterialCoordinator(self.root / "transaction", workspace, layers,
                                                         scene_id="s2", actor_personas={"阿青": "稳定人设"})
        coordinator.save_plan(plan)
        calls = []
        def invoke(call):
            calls.append(call)
            return {"candidates": [{"spoken": "信呢？", "first_person_action": "我捏住信封。",
                                    "focus": "停顿"}], "__answer": "{}"}
        candidate = coordinator.execute(actor, invoke)[0]
        prompt = json.loads(calls[0].prompt)
        self.assertEqual(len(prompt["role_known_archive"]), 1)
        self.assertEqual(len(prompt["director_reference_archive"]), 1)
        with self.assertRaisesRegex(ValueError, "environment"):
            coordinator.assert_ready_for_prose()
        (self.project / "characters/阿青.yaml").write_text("姓名：阿青\n秘密：信并未烧毁\n", encoding="utf-8")
        self.assertEqual(coordinator.execute(actor, invoke), [candidate])
        self.assertEqual(len(calls), 1)
        environment = parse_scene_material_requests_v3({"material_requests": [{
            "kind": "environment", "target": "", "purpose": "让雨带出迟疑",
            "scene_moment": "打开信封后", "cue": "窗外下雨", "author_prompt": "给出可用于正文的感官段落。",
            "archive_attachments": []}]}, ["阿青"])[0]
        coordinator.execute(environment, lambda _call: {"candidates": [{"text": "雨声在窗沿放慢，房间像在等她说话。",
                                                                  "focus": "听觉节奏"}], "__answer": "{}"})
        coordinator.assert_ready_for_prose()
        self.assertTrue((coordinator.root / "materials/index.json").is_file())

    def test_failed_call_retries_with_prepared_archive_snapshot(self) -> None:
        workspace = SceneCreatorWorkspace(self.project, self.studio)
        request = parse_scene_material_requests_v3({"material_requests": [{
            "kind": "event-narration", "target": "遗失的信", "purpose": "解释空信封",
            "scene_moment": "角色离开后", "cue": "只叙述已知事实",
            "author_prompt": "提供带来源边界的叙述候选。",
            "archive_attachments": [{"path": "characters/阿青.yaml"}],
        }]}, ["阿青"])[0]
        layers = {key: "designed" for key in (
            "scene.v2.material.shared.protocol", "scene.v2.material.output.protocol",
            "scene.v2.material.event-narration")}
        coordinator = SceneCreatorV2MaterialCoordinator(self.root / "retry", workspace, layers, scene_id="s1")
        coordinator.save_plan(parse_creator_material_plan({"material_plan": {
            "required_kinds": ["event-narration"], "reason": "补足来源明确的叙述"}}))
        def interrupted(_call):
            raise RuntimeError("worker interrupted")
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            coordinator.execute(request, interrupted)
        (self.project / "characters/阿青.yaml").write_text("姓名：阿青\n秘密：信并未烧毁\n", encoding="utf-8")
        seen = []
        coordinator.execute(request, lambda call: seen.append(json.loads(call.prompt)) or {
            "candidates": [{"text": "被烧毁的信只剩下一个空信封。", "focus": "事件遗痕",
                            "basis": "attributed", "source_note": "人物档案转述"}]})
        self.assertIn("信已烧毁", seen[0]["other_archive"][0]["content"])

    def test_selected_candidate_excerpt_is_frozen_into_later_natural_invitation(self):
        workspace = SceneCreatorWorkspace(self.project, self.studio)
        layers = {
            "scene.v2.transport.extractor": "整理模板",
            "scene.v2.material.actor": prompt_layer_spec("scene.v2.material.actor").default_text,
            "scene.v2.material.scene-description": prompt_layer_spec(
                "scene.v2.material.scene-description").default_text,
        }
        coordinator = SceneCreatorV2MaterialCoordinator(
            self.root / "material-chain", workspace, layers, scene_id="s1")
        coordinator.save_plan(parse_creator_material_plan({"material_plan": {
            "required_kinds": ["actor", "scene-description"], "reason": "先听人物，再组织动作空间"}}))
        actor, = parse_scene_material_requests_v4({"material_requests": [{
            "kind": "actor", "target": "阿青", "purpose": "她怎样接住旧信的话题",
            "scene_moment": "空信封落到掌心时", "cue": "信封是空的",
            "author_prompt": "让阿青从自己的处境里回应这只空信封。",
            "character_card": actor_card_payload(),
            "archive_attachments": [{"path": "characters/阿青.yaml", "start_line": 1,
                                    "end_line": 1, "knowledge": "known"}],
        }]}, ["阿青"])
        actor_material = coordinator.execute(actor, lambda _call: {
            "candidates": [{"spoken": "信还在。", "first_person_action": "我把信封按在碗底。",
                            "focus": "按住空信封"}],
        })[0]
        excerpt = actor_material["text"]
        scene, = parse_scene_material_requests_v4({"material_requests": [{
            "kind": "scene-description", "target": "碗边的这一刻",
            "purpose": "让迟疑落在手和桌面的距离上",
            "scene_moment": "信封被按在碗底之后", "cue": "人物尚未离开桌边",
            "author_prompt": "沿着手、信封与桌面的距离写出这一刻。",
            "working_context": "阿青已把信封按在碗底；这次沿着这个动作继续构图。",
            "material_attachments": [{"candidate_id": actor_material["candidate_id"],
                                     "start_char": 0, "end_char": len(excerpt)}],
            "archive_attachments": [{"path": "canon/world_rules.yaml"}],
        }]}, ["阿青"])
        seen = []
        def interrupted(call):
            seen.append(call)
            raise RuntimeError("temporary role failure")
        with self.assertRaisesRegex(RuntimeError, "temporary role failure"):
            coordinator.execute(scene, interrupted)
        actor_record_path, = [path for path in (coordinator.root / "calls").glob("*.json")
                              if json.loads(path.read_text(encoding="utf-8"))["request"]["kind"] == "actor"]
        actor_record = json.loads(actor_record_path.read_text(encoding="utf-8"))
        actor_record["candidates"][0]["text"] = "来源后来发生变化的候选文本。"
        actor_record_path.write_text(json.dumps(actor_record, ensure_ascii=False), encoding="utf-8")
        coordinator.execute(scene, lambda call: seen.append(call) or {
            "candidates": [{"text": "碗底压着信封，阿青的手还留在上面。", "focus": "手未离开"}],
        })

        prompt = seen[-1].prompt
        self.assertIn(scene.working_context, prompt)
        self.assertIn(excerpt, prompt)
        self.assertNotIn("来源后来发生变化", prompt)
        self.assertIn(actor_material["candidate_id"], prompt)
        self.assertIn("雨会留下痕迹", prompt)
        self.assertNotIn('"kind"', prompt)
        records = [json.loads(path.read_text(encoding="utf-8"))
                   for path in (coordinator.root / "calls").glob("*.json")]
        saved = next(record for record in records
                     if record["request"]["kind"] == "scene-description")
        selection = saved["material_attachments"][0]
        self.assertEqual(selection["char_range"], [0, len(excerpt)])
        self.assertEqual(selection["content_sha256"], sha256(excerpt.encode("utf-8")).hexdigest())

    def test_material_attachment_must_resolve_within_current_transaction(self):
        workspace = SceneCreatorWorkspace(self.project, self.studio)
        layers = {"scene.v2.transport.extractor": "整理模板",
                  "scene.v2.material.scene-description": "系统"}
        coordinator = SceneCreatorV2MaterialCoordinator(
            self.root / "missing-material", workspace, layers, scene_id="s1")
        coordinator.save_plan(parse_creator_material_plan({"material_plan": {
            "required_kinds": ["scene-description"], "reason": "把已发生动作放回空间"}}))
        request, = parse_scene_material_requests_v4({"material_requests": [{
            "kind": "scene-description", "target": "桌边", "purpose": "衔接动作",
            "scene_moment": "放下碗以后", "cue": "碗已经放下",
            "author_prompt": "沿着已经发生的动作安排空间。",
            "material_attachments": [{"candidate_id": "v2:missing:1"}],
        }]}, ["阿青"])

        with self.assertRaisesRegex(ValueError, "unavailable in this transaction"):
            coordinator.execute(request, lambda _call: self.fail("must resolve before the agent call"))

    def test_each_nonactor_call_receives_only_its_selected_archive_material(self):
        (self.project / "canon/alternate.yaml").write_text("另一条档案只用于第二次观察。\n", encoding="utf-8")
        workspace = SceneCreatorWorkspace(self.project, self.studio)
        layers = {"scene.v2.transport.extractor": "整理模板",
                  "scene.v2.material.environment": prompt_layer_spec(
                      "scene.v2.material.environment").default_text}
        coordinator = SceneCreatorV2MaterialCoordinator(
            self.root / "per-call-archive", workspace, layers, scene_id="s1")
        coordinator.save_plan(parse_creator_material_plan({"material_plan": {
            "required_kinds": ["environment"], "reason": "按场景需要观察不同物件"}}))

        def request(path, moment):
            value, = parse_scene_material_requests_v4({"material_requests": [{
                "kind": "environment", "target": "", "purpose": "呈现物件的使用痕迹",
                "scene_moment": moment, "cue": "人物仍在屋里",
                "author_prompt": "从物件的质地和周围的光写出这一刻。",
                "archive_attachments": [{"path": path}],
            }]}, ["阿青"])
            return value

        coordinator.execute(request("canon/world_rules.yaml", "望向窗边时"), lambda _call: {
            "candidates": [{"text": "窗沿留下几道雨水。", "focus": "水痕"}],
        })
        calls = []
        coordinator.execute(request("canon/alternate.yaml", "回看桌面时"), lambda call: calls.append(call) or {
            "candidates": [{"text": "桌面留下一圈淡淡的热痕。", "focus": "热痕"}],
        })

        self.assertEqual(calls[0].history, ())
        self.assertIn("另一条档案只用于第二次观察", calls[0].prompt)
        self.assertNotIn("雨会留下痕迹", calls[0].prompt)

    def test_prompt_placeholders_block_activation(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "prompt design is incomplete"):
            assert_v2_prompts_ready({"scene.v2.creator.identity": "[PENDING_PROMPT_DESIGN: identity]"})
        brief = SceneBrief("s1", "寻找信", "误会尚未解开", ("阿青",), (), (), (),
                           RhythmDirective(), LengthTarget(), StyleMountRef(),
                           SceneRisk(SceneRiskLevel.LOW), ())
        runtime = PiSceneTransactionRuntime(
            {"application": {"scene_creator_v2": {"enabled": True}}},
            project_root=self.project, data_root=self.studio,
            prompt_snapshot_provider=lambda ids, root: {
                "texts": {"scene.v2.creator.identity": "[PENDING_PROMPT_DESIGN: identity]"},
                "digest": "pending-test",
            },
        )
        with self.assertRaisesRegex(RuntimeError, "prompt design is incomplete"):
            runtime.create_scene("tx-pending", brief)
        self.assertFalse((self.studio / "scene-transactions/tx-pending/scene_creator_v2_mode.json").exists())

    def test_complete_drafts_do_not_enable_v2_by_default(self) -> None:
        from literary_engineering_studio_engine.public.prompting import list_prompt_layer_specs
        layers = {spec.layer_id: spec.default_text for spec in list_prompt_layer_specs()
                  if spec.layer_id.startswith("scene.v2.") or spec.layer_id == "project_agent.creator_persona.v2"}
        self.assertEqual(len(layers), 21)
        assert_v2_prompts_ready(layers)
        runtime = PiSceneTransactionRuntime({}, project_root=self.project, data_root=self.studio)
        self.assertFalse(runtime._uses_creator_v2("tx-default"))

    def test_frozen_legacy_v2_transaction_uses_agent_before_prose(self) -> None:
        CreatorPersonaStore(self.studio).save(
            self.project, "保持误会的张力，让对话和环境共同承接前一场的疑问。", reason="作品初始创作意图")
        brief = SceneBrief("s1", "寻找信", "误会尚未解开", ("阿青",), (), (), (),
                           RhythmDirective(), LengthTarget(), StyleMountRef(),
                           SceneRisk(SceneRiskLevel.LOW), ())

        class Gateway:
            def __init__(self):
                self.creator_calls = 0
                self.material_calls = 0

            def run(self, _root, prompt, **_kwargs):
                envelope = json.loads(prompt)
                task = json.loads(envelope["prompt"])
                self.creator_calls += 1
                if self.creator_calls == 1:
                    answer = {"material_plan": {"required_kinds": ["environment"], "reason": "借雨声延续迟疑"},
                              "material_requests": [{
                                  "kind": "environment", "target": "", "purpose": "承接迟疑",
                                  "scene_moment": "打开信封时", "cue": "雨打在窗上",
                                  "author_prompt": "提供可改写的环境候选。", "archive_attachments": [],
                              }]}
                else:
                    identifier = re.search(r"v2:[a-f0-9]+:1", task["material_index"]).group()
                    answer = {"prose": "雨敲着窗。阿青把空信封放回桌上，没回答那句追问。",
                              "decision_summary": "用雨声承接迟疑。",
                              "material_decisions": [{"candidate_id": identifier, "decision": "adapt",
                                                       "reason": "改写节奏以贴合人物沉默"}],
                              "scene_delta": {"next_handoff": ["信的去向尚未揭晓"]}}
                return RoleConversationResult("pi-worker", "run", "test/model",
                                              json.dumps(answer, ensure_ascii=False))

            def run_role_turn(self, _root, **_kwargs):
                self.material_calls += 1
                answer = {"candidates": [{"text": "窗上的雨点先轻后重，把等待拉得很长。",
                                          "focus": "雨声和等待"}]}
                return RoleConversationResult("pi-worker", "run", "test/model",
                                              json.dumps(answer, ensure_ascii=False))

        gateway = Gateway()
        runtime = PiSceneTransactionRuntime(
            {"application": {"scene_creator_v2": {"enabled": True}}},
            project_root=self.project, data_root=self.studio, gateway=gateway,
            prompt_snapshot_provider=lambda ids, _root: {
                "schema": "arcvellum/prompt-assembly/v1", "digest": "test-designed",
                "layers": [], "texts": {key: "designed" for key in ids},
            },
        )
        # A pre-rebuild transaction retains its JSON contract and frozen text.
        frozen_path = self.studio / "scene-transactions/tx-live/prompt_assembly_v2.json"
        frozen_path.parent.mkdir(parents=True)
        from literary_engineering_studio_engine.public.prompting import list_prompt_layer_specs
        frozen_path.write_text(json.dumps({"schema": "arcvellum/prompt-assembly/v1", "digest": "old-v2",
            "texts": {spec.layer_id: "designed" for spec in list_prompt_layer_specs()
                      if (spec.layer_id.startswith("scene.v2.") and spec.layer_id != "scene.v2.transport.extractor")
                      or spec.layer_id == "project_agent.creator_persona.v2"}}, ensure_ascii=False), encoding="utf-8")
        result = runtime.create_scene("tx-live", brief)
        self.assertIn("空信封", result.prose)
        self.assertEqual((gateway.creator_calls, gateway.material_calls), (2, 1))
        self.assertTrue((self.studio / "scene-transactions/tx-live/v2/material_plan.json").is_file())


if __name__ == "__main__":
    unittest.main()
