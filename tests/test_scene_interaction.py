from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.runtime.role_conversation import RoleConversationResult
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.scene_interaction import new_scene_session, continue_scene_actor, _character_context, _actor_turn
from literary_engineering_studio.runtimes.scene_performance import _cached_payload, fulfill_scene_material_requests
from literary_engineering_studio.runtimes.scene_performance_ownership import author_handoff_materials, compact_performance_materials
from literary_engineering_studio_engine.public.literary import (
    parse_interaction_direction, parse_scene_material_requests, render_actor_interaction_prompt,
    render_interaction_materials,
)
from literary_engineering_studio_engine.literary.scene.transaction import VerificationReport
from literary_engineering_studio_engine.literary.scene.roleplay.relay_context import validated_public_log
from tests.test_lean_kernel_v2_pi_runtime import _Gateway, _brief


def _creator_prompt(prompt: str) -> str:
    try:
        payload = json.loads(prompt)
    except json.JSONDecodeError:
        return prompt
    return str(payload.get("prompt") or prompt) if isinstance(payload, dict) else prompt


def _fixture(participants: list[str]):
    brief = {**_brief().to_dict(), "participants": participants, "viewpoint": participants[0]}
    plan = {
        "scene_id": brief["scene_id"], "beats": [{"beat_id": "b1", "event": "桌上的旧信被打开"}],
        "opening_direction": {"finish": False, "next_speaker": participants[0], "beat_id": "b1",
                              "scene_change": "", "cue": "面对已经打开的信", "director_note": ""},
        "actor_prompts": {
            speaker: "【PERSONA_LOAD】\nSELF_CLAIM_ACTOR\n\n【PERSONALITY_CORE】\nTRAIT_ALERT\n\n【PERSONALITY_PUBLIC】\nTRAIT_EXPRESSIVE"
            for speaker in participants
        },
        "actor_tasks": {speaker: "面对已经打开的信，按自己的关系与处境回应。" for speaker in participants},
        "environment_initialization": (
            "【SCENE_LOAD】\nSCENE_CLAIM_LANDSCAPE_DESCRIBER\n\n[COMPOSITION_MODE]\nSCENE_RENDER\n\n"
            "[SCENE_CORE]\nATTR_ATMOSPHERE_AS_PRIMARY\n\n[SCENE_SURFACE]\nATTR_PERSPECTIVE_LOCKED\n\n"
            "[LITERATURE_STYLE]\nWORK_LIKE_CLASSIC_PROSE\n\n[NOW_TO_DO]\nSTAND_BY"
        ),
        "unknown_slots": [],
    }
    return brief, plan


class SceneInteractionTests(unittest.TestCase):
    def test_actor_request_respects_scene_call_limit_and_reports_unavailable_material(self):
        brief, plan = _fixture(["character/solo"])
        calls = []
        config = {"application": {"scene_performance_agents": {"enabled": True, "max_actor_calls": 0}}}
        payload = {"material_requests": [{"kind": "actor", "target": "character/solo",
                    "purpose": "观察他是否转移话题", "scene_moment": "看见旧信时", "cue": "旧信已打开"}]}
        with tempfile.TemporaryDirectory() as directory:
            with patch("literary_engineering_studio.runtimes.scene_performance._generate_performance_plan", return_value=plan):
                for _ in range(2):
                    block = fulfill_scene_material_requests(
                        brief=brief, expression={}, sources="", style_reference="", payload=payload,
                        cache_root=Path(directory), config=config, invoke=lambda prompt, role: "",
                        invoke_actor_turn=lambda *args: calls.append(args) or ("", ""),
                        request_batch_id="limited",
                    )
        self.assertEqual(calls, [])
        packet = json.loads(block.split("\n", 1)[1])
        self.assertEqual(len(packet["material_notices"]), 1)
        self.assertIn("达到设置上限", packet["material_notices"][0]["reason"])
        self.assertIn("达到设置上限", author_handoff_materials(block))
        self.assertIn("达到设置上限", compact_performance_materials(block))

    def test_describer_first_does_not_plan_actors_but_later_actor_is_initialized(self):
        brief, plan = _fixture(["character/solo"])
        actor_calls = []

        def role_turn(role, initialization, history, prompt):
            return json.dumps({"candidates": [{"text": "昨夜取信的传闻在清晨传遍了巷子。", "focus": "场外事件的传播",
                "basis": "attributed", "source_note": "街坊传闻，尚未核实"}]}, ensure_ascii=False), ""

        def actor_turn(initialization, initialization_answer, history, prompt):
            actor_calls.append(initialization)
            return json.dumps({"scene_id": brief["scene_id"], "speaker": "character/solo", "entries": [
                {"beat_id": "b1", "spoken": "信留在这里。", "first_person_action": "我把信压在桌上。", "private_impulse": ""},
            ]}, ensure_ascii=False), "initialized"

        config = {"application": {"scene_performance_agents": {"enabled": True}}}
        expression = {"actor_personas": {"character/solo":
            "【PERSONA_LOAD】\nSELF_CLAIM_SOLO\n\n【PERSONALITY_CORE】\nTRAIT_WARY\n\n"
            "【PERSONALITY_PUBLIC】\nTRAIT_WRY\n\n[LITERATURE_STYLE]\nKAFKA_LIKE"}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("literary_engineering_studio.runtimes.scene_performance._generate_performance_plan", return_value=plan) as planner:
                first = fulfill_scene_material_requests(
                    brief=brief, expression=expression, sources="", style_reference="",
                    payload={"material_requests": [{"kind": "event-narration", "target": "昨夜取信",
                        "purpose": "延后交代已发生事件", "scene_moment": "按住信时", "cue": "信昨夜被取走"}]},
                    cache_root=root, config=config, invoke=lambda prompt, role: "",
                    invoke_actor_turn=actor_turn, invoke_role_turn=role_turn, request_batch_id="describer",
                )
                planner.assert_not_called()
                second = fulfill_scene_material_requests(
                    brief=brief, expression=expression, sources="", style_reference="",
                    payload={"material_requests": [{"kind": "actor", "target": "character/solo",
                        "purpose": "让他自行选择是否留下信", "scene_moment": "信封被看见后", "cue": "对方望着信封"}]},
                    cache_root=root, config=config, invoke=lambda prompt, role: "",
                    invoke_actor_turn=actor_turn, invoke_role_turn=role_turn, request_batch_id="actor",
                )
            self.assertEqual(planner.call_count, 1)
        self.assertIn("昨夜取信的传闻", first)
        self.assertIn("昨夜取信的传闻", second)
        self.assertIn("信留在这里", second)
        self.assertEqual(len(actor_calls), 1)
        self.assertIn("【PERSONA_LOAD】", actor_calls[0])
        self.assertIn("KAFKA_LIKE", actor_calls[0])
        self.assertNotIn("TRAIT_ALERT", actor_calls[0])

    def test_environment_requests_continue_one_scene_history(self):
        brief, plan = _fixture(["character/solo"])
        histories = []

        def role_turn(role, initialization, history, prompt):
            histories.append(len(history))
            self.assertIn("选择有用的桌沿细节", prompt)
            answer = json.dumps({"scene_id": brief["scene_id"], "passages": [
                {"beat_id": "b1", "description": "桌沿的光缓慢移开。"},
            ]}, ensure_ascii=False)
            return answer, ""

        with tempfile.TemporaryDirectory() as directory:
            with patch("literary_engineering_studio.runtimes.scene_performance._generate_performance_plan", return_value=plan):
                for batch in ("first", "second"):
                    result = fulfill_scene_material_requests(
                        brief=brief, expression={}, sources="", style_reference="",
                        payload={"material_requests": [{"kind": "environment", "cue": "观察桌沿的光",
                                                       "purpose": "让读者感到等待变长", "scene_moment": "信封被放下时"}]},
                        cache_root=Path(directory), config={"application": {"scene_performance_agents": {"enabled": True}}},
                        invoke=lambda prompt, role: "", invoke_actor_turn=None,
                        invoke_role_turn=role_turn, request_batch_id=batch,
                        prompt_layers={"scene.environment.turn": "选择有用的桌沿细节"},
                    )
            packet = json.loads(result.split("\n", 1)[1])
        self.assertEqual(histories, [0, 1])
        self.assertEqual([passage["candidate_id"] for passage in packet["environment_candidates"]["passages"]],
                         ["environment:1", "environment:2"])


    def test_long_character_reply_remains_available_to_the_next_actor(self):
        brief, _plan = _fixture(["character/solo"])
        reply = "她终于肯把话说完。" * 90
        action = "我把纸放下。" * 50
        self.assertEqual(validated_public_log(brief, [{
            "speaker": "character/solo", "spoken": reply, "first_person_action": action,
        }]), [{"speaker": "character/solo", "spoken": reply, "first_person_action": action}])

    def test_actor_rewrites_malformed_json_without_losing_the_scene_turn(self):
        brief, plan = _fixture(["character/solo"])
        prompts = []

        def act(_initialization, _answer, _history, prompt):
            prompts.append(prompt)
            if len(prompts) == 1:
                return '{"scene_id":"scene_0001","speaker":"character/solo","entries":[{"beat_id":"b1","spoken":"我说"真的"","first_person_action":"","private_impulse":""}]}', ""
            return json.dumps({"scene_id": brief["scene_id"], "speaker": "character/solo", "entries": [{
                "beat_id": "b1", "spoken": "我说真的。", "first_person_action": "", "private_impulse": "",
            }]}, ensure_ascii=False), ""

        with tempfile.TemporaryDirectory() as directory:
            result = _actor_turn(brief, plan, plan["opening_direction"], 0, "轮次", "初始化", "",
                                 [], Path(directory), "repair", act, _cached_payload)
        self.assertEqual(len(prompts), 2)
        self.assertIn("JSON 结构或转义", prompts[1])
        self.assertEqual(result["response"]["entries"][0]["spoken"], "我说真的。")


    def test_actor_receives_own_background_after_pure_initialization(self):
        brief, plan = _fixture(["纪蔚"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "characters").mkdir()
            (root / "characters" / "纪蔚.yaml").write_text(
                "name: 纪蔚\nrole: 修复师\nbackground_story:\n  hidden_wound: 她欠朋友一个夜班。\n"
                "bdi:\n  belief: [声音会留下人的选择]\nrelationships: [她与旧友仍有未说的话]\n"
                "speech_style:\n  rhythm: 短句，像交接记录。\n",
                encoding="utf-8",
            )
            context = _character_context(root, "纪蔚")
        direction = plan["opening_direction"]
        prompt = render_actor_interaction_prompt(brief, plan, direction, [], "", context)
        self.assertIn("她欠朋友一个夜班", prompt)
        self.assertIn("声音会留下人的选择", prompt)
        self.assertNotIn("交接记录", prompt)
        self.assertIn("一次真实回应", prompt)
        self.assertNotIn("我在这场戏里的处境", prompt)
        self.assertNotIn("至多四条 JSON 候选", prompt)
        self.assertNotIn("她欠朋友一个夜班", new_scene_session(brief, {}, plan, None)["initializations"]["纪蔚"])

    def test_actor_prompt_keeps_addressee_and_evidence_visible(self):
        brief, plan = _fixture(["江岫", "阿澍", "温泠"])
        public = [{"speaker": "江岫", "spoken": "他们两位像新婚的。", "first_person_action": ""}]
        direction = {"next_speaker": "阿澍", "beat_id": "b1", "scene_change": "",
                     "cue": "听见江岫打趣，向温泠求证。"}
        actor = render_actor_interaction_prompt(brief, plan, direction, public, "")
        self.assertIn("这次主要面对谁", actor)
        self.assertIn("他们两位像新婚的", actor)
        self.assertIn("向温泠求证", actor)


    def test_author_handoff_treats_rehearsal_as_selectable_material(self):
        brief, plan = _fixture(["character/solo"])
        block = render_interaction_materials(plan, [], [{
            "entry_id": "t1:1", "speaker": "character/solo", "beat_id": "b1",
            "spoken": "信是我的。", "first_person_action": "我压住信封。", "private_impulse": "我害怕。",
        }], None, viewpoint=brief["viewpoint"])
        self.assertIn("只读素材文件目录", block)
        self.assertIn("按作者意图把候选分成可用", block)
        self.assertIn('"entry_id":"t1:1"', block)

    def test_author_handoff_keeps_new_events_once_and_omits_repetitive_notes(self):
        _, plan = _fixture(["character/solo"])
        turns = [{"turn": index, "next_speaker": "character/solo", "beat_id": "b1",
                  "director_note": "重复的导演解释" * 60, "scene_change": "重复场景说明" * 60,
                  "entry_ids": [f"t{index}:1"]} for index in range(1, 9)]
        entries = [{"entry_id": f"t{index}:1", "speaker": "character/solo", "beat_id": "b1",
                    "spoken": "信是我的。", "first_person_action": "我压住信封。", "private_impulse": "我害怕。"}
                   for index in range(1, 9)]
        block = render_interaction_materials(plan, turns, entries, None)
        self.assertIn('"director_turns"', block)
        self.assertNotIn("重复的导演解释", block)
        self.assertEqual(block.count("重复场景说明" * 60), 1)
        self.assertIn("scene-context 保存节拍", block)

    def test_author_handoff_retains_distinct_external_changes_in_order(self):
        _, plan = _fixture(["character/a", "character/b"])
        turns = [
            {"turn": 1, "next_speaker": "character/a", "beat_id": "b1", "scene_change": "窗外传来敲门声", "entry_ids": ["t1:1"]},
            {"turn": 2, "next_speaker": "character/b", "beat_id": "b1", "scene_change": "门被风吹开", "entry_ids": ["t2:1"]},
        ]
        block = render_interaction_materials(plan, turns, [], None)
        packet = json.loads(block.rsplit("\n", 1)[1])
        self.assertEqual([turn["scene_change"] for turn in packet["director_turns"]],
                         ["窗外传来敲门声", "门被风吹开"])


    def test_review_material_preserves_actor_evidence_without_repeating_plan(self):
        packet = {
            "plan": {"actor_prompts": {"character/solo": "A" * 3000}},
            "director_turns": [{"turn": 1, "next_speaker": "character/solo", "cue": "B" * 1000,
                                "scene_change": "信被打开", "entry_ids": ["t1:1"]}],
            "actor_entries": [{"entry_id": "t1:1", "speaker": "character/solo", "spoken": "信是我的。",
                               "first_person_action": "我压住信封。", "private_impulse": "我害怕。"}],
            "environment_candidates": {"passages": [{"description": "桌沿有冷光。"}]},
        }
        full = "逐轮推演候选资料。\n" + json.dumps(packet, ensure_ascii=False)
        compact = compact_performance_materials(full)
        self.assertLess(len(compact), len(full) // 2)
        self.assertIn("信是我的。", compact)
        self.assertIn("桌沿有冷光。", compact)
        self.assertIn("信被打开", compact)
        self.assertIn('"cue":"' + "B" * 260, compact)
        self.assertNotIn("我害怕", compact)
        self.assertNotIn("actor_prompts", compact)
        self.assertNotIn("B" * 1000, compact)

        handoff = author_handoff_materials(full)
        self.assertLess(len(handoff), len(full) // 2)
        self.assertIn("信是我的。", handoff)
        self.assertIn("信被打开", handoff)
        self.assertIn("我害怕", handoff)
        self.assertIn("桌沿有冷光。", handoff)
        self.assertNotIn("actor_prompts", handoff)
        self.assertNotIn("B" * 1000, handoff)

    def test_production_runtime_hands_interaction_to_main_creator(self):
        class Gateway(_Gateway):
            def __init__(self):
                super().__init__()
                self.actor_turns = []
                self.create_count = 0
                self.environment_turns = []

            def run(self, workspace, prompt, *, role, timeout, event_sink=None, cancel_event=None):
                if _creator_prompt(prompt).startswith("# Scene Create"):
                    self.create_count += 1
                    if self.create_count == 1:
                        self.calls.append((role, prompt))
                        request = {"material_requests": [
                            {"kind": "actor", "speaker": "character/sister", "cue": "信已经打开",
                             "purpose": "让质问带出妹妹自己的判断", "scene_moment": "看见旧信时"},
                            {"kind": "actor", "speaker": "character/protagonist", "cue": "回应妹妹",
                             "purpose": "让承认显出关系代价", "scene_moment": "妹妹追问后"},
                            {"kind": "environment", "cue": "门边的光",
                             "purpose": "让停顿在空间里可见", "scene_moment": "承认之后"},
                        ]}
                        return RoleConversationResult("pi-worker", "request", "test/model", json.dumps(request, ensure_ascii=False))
                    self.calls.append((role, prompt))
                    return RoleConversationResult("pi-worker", "draft", "test/model", json.dumps({
                        "prose": "她把信放回桌上，说是自己拿的。妹妹没有接话。",
                        "decision_summary": "把人物回应与门边的光编成承认后的停顿。",
                        "scene_delta": {}, "material_decisions": [{
                            "candidate_id": "t1:1", "decision": "adapt",
                            "reason": "保留妹妹的追问，主创补写承认后的沉默",
                        }],
                    }, ensure_ascii=False))
                if prompt.startswith("# Scene Performance Direction"):
                    self.calls.append((role, prompt))
                    _, plan = _fixture(["character/protagonist", "character/sister"])
                    plan["opening_direction"]["next_speaker"] = "character/sister"
                    answer = json.dumps(plan, ensure_ascii=False)
                elif prompt.startswith("# Scene Interaction Direction"):
                    raise AssertionError("the retired automatic interaction path was invoked")
                elif role == "environment-writer":
                    self.calls.append((role, prompt))
                    answer = json.dumps({"scene_id": "scene_0001", "passages": [
                        {"beat_id": "b1", "description": "门边的光沿着信封的折痕移动。"},
                    ]}, ensure_ascii=False)
                else:
                    return super().run(workspace, prompt, role=role, timeout=timeout,
                                       event_sink=event_sink, cancel_event=cancel_event)
                return RoleConversationResult("pi-worker", "run-interaction", "test/model", answer)

            def run_role_turn(self, workspace, *, role, initialization, history, prompt, timeout, event_sink=None):
                self.environment_turns.append((role, initialization, history, prompt))
                answer = {"scene_id": "scene_0001", "passages": [
                    {"beat_id": "b1", "description": "门边的光沿着信封的折痕移动。"},
                ]}
                return RoleConversationResult("pi-worker", "environment", "test/model", json.dumps(answer, ensure_ascii=False))

            def run_actor_turn(self, workspace, *, initialization, initialization_answer,
                               history, prompt, timeout, event_sink=None):
                speaker = prompt.rsplit('"speaker":"', 1)[1].split('"', 1)[0]
                self.actor_turns.append((speaker, initialization, initialization_answer, history, prompt))
                spoken = "你把信拿走了？" if speaker == "character/sister" else "是我拿的，先听我说完。"
                answer = json.dumps({"scene_id": "scene_0001", "speaker": speaker, "entries": [
                    {"beat_id": "b1", "spoken": spoken, "first_person_action": "", "private_impulse": "我很紧张。"},
                ]}, ensure_ascii=False)
                return RoleConversationResult("pi-worker", "run-interaction", "test/model", answer,
                                              "初始化完成")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gateway = Gateway()
            runtime = PiSceneTransactionRuntime(
                {"application": {"scene_performance_agents": {"enabled": True}}},
                project_root=root, data_root=root / ".studio", gateway=gateway,
            )
            result = runtime.create_scene("tx-interaction", _brief())
            creator_prompts = [_creator_prompt(prompt) for role, prompt in gateway.calls
                               if role == "worker" and "## Read-Only Scene Material File Index" in prompt]
            self.assertEqual(len(gateway.actor_turns), 2)
            self.assertEqual(len(creator_prompts), 1)
            self.assertEqual(len(gateway.environment_turns), 1)
            self.assertTrue(gateway.environment_turns[0][1].startswith("【SCENE_LOAD】"))
            self.assertTrue(gateway.environment_turns[0][3].startswith("# Independent Environment Writing"))
            self.assertNotIn("你把信拿走了？", creator_prompts[0])
            self.assertNotIn("是我拿的，先听我说完。", creator_prompts[0])
            self.assertNotIn('"director_turns"', creator_prompts[0])
            self.assertNotIn('"environment_candidates"', creator_prompts[0])
            self.assertIn("scene-context", creator_prompts[0])
            self.assertNotIn('"actor_prompts"', creator_prompts[0])
            self.assertNotIn('"environment_initialization"', creator_prompts[0])
            self.assertIn("希望读者怎样经历这一场", creator_prompts[0])
            self.assertIn("先把作者意图落实成需要观察", creator_prompts[0])
            material_index = json.loads((root / ".studio/scene-transactions/tx-interaction/materials/index.json").read_text(encoding="utf-8"))
            self.assertTrue(any(item["kind"] == "actor" for item in material_index["entries"]))
            self.assertTrue(all("[LANGUAGE_STYLE]\nANTI_PLAIN\nPOLISHED\nANTI_SHORT_SENTENCES" in call[1]
                                for call in gateway.actor_turns))
            self.assertTrue(all("[LITERATURE_STYLE]" in call[1] and "【角色沉浸要求】" in call[1]
                                for call in gateway.actor_turns))
            self.assertTrue(all("面对他人时，我有权试探" in call[-1]
                                for call in gateway.actor_turns))
            self.assertTrue(result.prose)
            self.assertGreater(runtime.metrics.provider_calls, 4)


    def test_creator_requests_actor_continuation_and_environment_then_writes(self):
        class Gateway(_Gateway):
            def __init__(self):
                super().__init__()
                self.create_prompts = []
                self.actor_histories = []
                self.environment_prompts = []

            def run(self, workspace, prompt, *, role, timeout, event_sink=None, cancel_event=None):
                self.calls.append((role, prompt))
                if prompt.startswith("# Scene Performance Direction"):
                    return RoleConversationResult("pi-worker", "plan", "test/model", json.dumps(
                        _fixture(["character/solo"])[1], ensure_ascii=False))
                if role == "environment-writer":
                    envelope = json.loads(prompt)
                    self.environment_prompts.append(envelope)
                    passages = ([{"beat_id": "b1", "description": "窗上的雨光慢慢漫到信封背面。"}]
                                if "Current Creator Request" in envelope["prompt"] else [])
                    return RoleConversationResult("pi-worker", "environment", "test/model", json.dumps(
                        {"scene_id": "scene_0001", "passages": passages}, ensure_ascii=False))
                if prompt.startswith("# Scene Interaction Direction"):
                    raise AssertionError("the retired automatic interaction path was invoked")
                if _creator_prompt(prompt).startswith("# Scene Create"):
                    self.create_prompts.append(_creator_prompt(prompt))
                    if len(self.create_prompts) == 1:
                        answer = {"material_requests": [
                            {"kind": "actor", "speaker": "character/solo", "beat_id": "b1", "cue": "看见对方仍在等回答",
                             "purpose": "显出他回应时的犹疑", "scene_moment": "信被推来后"},
                            {"kind": "environment", "beat_id": "b1", "cue": "雨光在信封上的变化",
                             "purpose": "让等待的时间可感", "scene_moment": "他回答前"},
                        ]}
                    else:
                        answer = {"prose": "他说：“你还等着，我怎么能装作没看见？”窗上的雨光漫到信封背面。",
                                  "decision_summary": "看见与回应使关系变化。", "scene_delta": {}, "material_requests": [],
                                  "material_decisions": [{"candidate_id": "t1:1", "decision": "adapt",
                                                          "reason": "保留自主回应，由主创安排雨光与信封的叙述"}]}
                    return RoleConversationResult("pi-worker", "creator", "test/model", json.dumps(answer, ensure_ascii=False))
                if prompt.startswith("# First-Level Visible Action Source Audit"):
                    return RoleConversationResult("pi-worker", "audit", "test/model", '{"status":"clean","violations":[]}')
                return super().run(workspace, prompt, role=role, timeout=timeout,
                                   event_sink=event_sink, cancel_event=cancel_event)

            def run_actor_turn(self, workspace, *, initialization, initialization_answer,
                               history, prompt, timeout, event_sink=None):
                self.actor_histories.append(len(history))
                spoken = "信给我。" if not history else "你还等着，我怎么能装作没看见？"
                answer = {"scene_id": "scene_0001", "speaker": "character/solo", "entries": [
                    {"beat_id": "b1", "spoken": spoken, "first_person_action": "", "private_impulse": "我有些动摇。"},
                ]}
                return RoleConversationResult("pi-worker", "actor", "test/model", json.dumps(answer, ensure_ascii=False),
                                              "初始化完成")

            def run_role_turn(self, workspace, *, role, initialization, history, prompt, timeout, event_sink=None):
                self.environment_prompts.append({"initialization": initialization, "prompt": prompt, "history": history})
                answer = {"scene_id": "scene_0001", "passages": [
                    {"beat_id": "b1", "description": "窗上的雨光慢慢漫到信封背面。"},
                ]}
                return RoleConversationResult("pi-worker", "environment", "test/model", json.dumps(answer, ensure_ascii=False))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gateway = Gateway()
            brief = replace(_brief(), participants=("character/solo",), length=type(_brief().length)(100, 0, 200))
            runtime = PiSceneTransactionRuntime(
                {"application": {"scene_performance_agents": {"enabled": True}}},
                project_root=root, data_root=root / ".studio", gateway=gateway,
            )
            result = runtime.create_scene("tx-material-requests", brief)
            self.assertIn("雨光漫到信封", result.prose)
            self.assertEqual(gateway.actor_histories, [0])
            self.assertEqual(len(gateway.create_prompts), 2)
            self.assertNotIn("信给我。", gateway.create_prompts[1])
            self.assertNotIn("窗上的雨光慢慢漫到信封背面", gateway.create_prompts[1])
            self.assertIn("scene-context", gateway.create_prompts[1])
            self.assertEqual(len(gateway.environment_prompts), 1)
            self.assertTrue(all(item["initialization"].startswith("【SCENE_LOAD】")
                                for item in gateway.environment_prompts))
            self.assertEqual(runtime.metrics.provider_calls,
                             len(gateway.calls) + len(gateway.environment_prompts)
                             + len(gateway.actor_histories) + 1)

    def test_material_requests_follow_known_roles_and_beats(self):
        brief, plan = _fixture(["character/solo"])
        requests = parse_scene_material_requests({"material_requests": [
            {"kind": "actor", "speaker": "character/solo", "cue": "多说些眼前的事",
             "purpose": "显出他对旧信的回避", "scene_moment": "信打开时"},
            {"kind": "environment", "cue": "观察雨后的桌面",
             "purpose": "让读者感到雨后的空寂", "scene_moment": "停顿时"},
        ]}, brief, plan)
        self.assertEqual([item["kind"] for item in requests], ["actor", "environment"])
        self.assertEqual([item["beat_id"] for item in requests], ["b1", "b1"])
        self.assertEqual(requests[0]["scene_change"], "")
        from_entry = parse_scene_material_requests({"material_requests": [
            {"kind": "actor", "speaker": "character/solo", "beat_id": "t2:1", "cue": "继续回应",
             "purpose": "让承认继续改变信任", "scene_moment": "上一句之后"},
        ]}, brief, plan, actor_entries=[{"entry_id": "t2:1", "beat_id": "b1", "speaker": "character/solo"}])
        self.assertEqual(from_entry[0]["beat_id"], "b1")
        with self.assertRaisesRegex(ValueError, "literary purpose"):
            parse_scene_material_requests({"material_requests": [{
                "kind": "actor", "speaker": "character/solo", "cue": "继续回应",
            }]}, brief, plan)
        with self.assertRaisesRegex(ValueError, "speaker"):
            parse_scene_material_requests({"material_requests": [{"kind": "actor", "speaker": "unknown", "cue": "说话",
                                                                "purpose": "揭示回避", "scene_moment": "此刻"}]}, brief, plan)
        with self.assertRaisesRegex(ValueError, "known beat"):
            parse_scene_material_requests({"material_requests": [{"kind": "environment", "beat_id": "b9", "cue": "观察",
                                                                "purpose": "显示距离", "scene_moment": "此刻"}]}, brief, plan)

    def test_creator_can_add_a_new_change_between_turns_of_same_actor(self):
        brief, plan = _fixture(["character/solo"])
        requests = parse_scene_material_requests({"material_requests": [
            {"kind": "actor", "speaker": "character/solo", "beat_id": "b1",
             "scene_change": "门外传来一声敲门", "cue": "我认得这个敲门习惯",
             "purpose": "让旧关系在敲门声里浮现", "scene_moment": "敲门之后"},
        ]}, brief, plan)
        state = new_scene_session(brief, {}, plan, None)
        prompts = []

        def actor(initialization, initialization_answer, history, prompt):
            prompts.append(prompt)
            return json.dumps({"scene_id": brief["scene_id"], "speaker": "character/solo", "entries": [
                {"beat_id": "b1", "spoken": "你终于来了。", "first_person_action": "", "private_impulse": ""},
            ]}, ensure_ascii=False), ""

        with tempfile.TemporaryDirectory() as directory:
            for request in requests:
                continue_scene_actor(brief, plan, request, state, Path(directory), "digest", actor, _cached_payload)
        self.assertIn("门外传来一声敲门", prompts[0])
        self.assertIn("我认得这个敲门习惯", prompts[0])
        self.assertEqual(state["directions"][0]["scene_change"], "门外传来一声敲门")

    def test_revision_can_request_more_material_and_resume_with_it(self):
        class Gateway(_Gateway):
            def __init__(self):
                super().__init__()
                self.revision_prompts = []

            def run(self, workspace, prompt, *, role, timeout, event_sink=None, cancel_event=None):
                if _creator_prompt(prompt).startswith("# Scene Revision"):
                    self.revision_prompts.append(_creator_prompt(prompt))
                    answer = ({"material_requests": [{"kind": "actor", "speaker": "character/protagonist",
                                                     "cue": "再回应妹妹一次", "purpose": "让承诺显出代价",
                                                     "scene_moment": "妹妹再次追问后"}]}
                              if len(self.revision_prompts) == 1 else
                              {"prose": "他说：“我会把信交给你。”", "decision_summary": "修订关系转折。",
                               "scene_delta": {}, "material_requests": [],
                               "material_decisions": [{"candidate_id": "t2:1", "decision": "use",
                                                       "reason": "角色续演给出关系转折的对白"}]})
                    return RoleConversationResult("pi-worker", "revision", "test/model", json.dumps(answer, ensure_ascii=False))
                return super().run(workspace, prompt, role=role, timeout=timeout,
                                   event_sink=event_sink, cancel_event=cancel_event)

        supplemented = "一级角色候选\n" + json.dumps({"actor_entries": [
            {"entry_id": "t1:1", "speaker": "character/protagonist", "spoken": "信是我拿的。",
             "first_person_action": "", "private_impulse": ""},
            {"entry_id": "t2:1", "speaker": "character/protagonist", "spoken": "我会把信交给你。",
             "first_person_action": "", "private_impulse": ""},
        ]}, ensure_ascii=False)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gateway = Gateway()
            brief = replace(_brief(), length=type(_brief().length)(100, 0, 200))
            runtime = PiSceneTransactionRuntime(
                {"application": {"scene_performance_agents": {"enabled": True}}},
                project_root=root, data_root=root / ".studio", gateway=gateway,
            )
            candidate = runtime.create_scene("tx-revision-request", brief)
            with patch("literary_engineering_studio.runtimes.pi_scene_transaction.fulfill_scene_material_requests",
                       return_value=supplemented) as fulfill:
                revised = runtime.revise_scene("tx-revision-request", brief, candidate,
                                               VerificationReport(brief.scene_id, len(candidate.prose)), None, attempt=1)
            self.assertEqual(fulfill.call_count, 1)
            self.assertNotIn("我会把信交给你", gateway.revision_prompts[1])
            self.assertIn("我会把信交给你", revised.prose)

    def test_retry_reuses_requested_materials_without_replaying_preparation(self):
        supplemented = "环境候选\n" + json.dumps({"actor_entries": [], "environment_candidates": {
            "passages": [{"candidate_id": "environment:1", "beat_id": "b1", "description": "雨停了。"}],
        }}, ensure_ascii=False)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief = replace(_brief(), length=type(_brief().length)(100, 0, 200))
            runtime = PiSceneTransactionRuntime(
                {"application": {"scene_performance_agents": {"enabled": True}}},
                project_root=root, data_root=root / ".studio", gateway=_Gateway(),
            )
            request = json.dumps({"material_requests": [{"kind": "environment", "cue": "看看雨后",
                                                        "purpose": "让雨后的停顿可感", "scene_moment": "争执后"}]}, ensure_ascii=False)
            with patch("literary_engineering_studio.runtimes.pi_scene_transaction.fulfill_scene_material_requests",
                       return_value=supplemented) as fulfill, patch.object(
                           runtime, "_run", side_effect=[request, RuntimeError("temporary provider stop")]):
                with self.assertRaisesRegex(RuntimeError, "temporary provider stop"):
                    runtime.create_scene("tx-resume", brief)
            self.assertEqual(fulfill.call_count, 1)
            final = json.dumps({"prose": "雨停了。", "decision_summary": "雨后停留。", "scene_delta": {},
                                "material_decisions": [{"candidate_id": "environment:1", "decision": "adapt",
                                                        "reason": "保留雨停时的停顿，由主创补写人物动作"}]}, ensure_ascii=False)
            with patch.object(runtime, "_run", return_value=final):
                result = runtime.create_scene("tx-resume", brief)
            self.assertEqual(result.prose, "雨停了。")


    def test_direction_rejects_unknown_participant_without_adding_literary_gate(self):
        brief, plan = _fixture(["character/solo"])
        with self.assertRaisesRegex(ValueError, "scene participant"):
            parse_interaction_direction({"finish": False, "next_speaker": "character/stranger",
                                         "beat_id": "b1"}, brief, plan)


if __name__ == "__main__":
    unittest.main()
