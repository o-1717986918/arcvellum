from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.runtime.role_conversation import RoleConversationResult
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.scene_interaction import perform_scene_interaction, new_scene_session, continue_scene_actor, _character_context, _generate_direction, _actor_turn
from literary_engineering_studio.runtimes.scene_performance import _cached_payload, _try_interaction, scene_performance_materials
from literary_engineering_studio.runtimes.scene_performance_ownership import compact_performance_materials
from literary_engineering_studio_engine.public.literary import (
    parse_interaction_direction, parse_scene_material_requests, render_actor_interaction_prompt,
    render_interaction_direction_prompt, render_interaction_materials,
)
from literary_engineering_studio_engine.literary.scene.transaction import VerificationReport
from literary_engineering_studio_engine.literary.scene.roleplay.relay_context import validated_public_log
from tests.test_lean_kernel_v2_pi_runtime import _Gateway, _brief


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
    def test_long_first_reply_still_reaches_other_characters_with_director_cues(self):
        speakers = ["character/a", "character/b", "character/c"]
        brief, plan = _fixture(speakers)
        remaining = iter([speakers[1], speakers[2], ""])
        direction_prompts = []

        def invoke(prompt, _role):
            direction_prompts.append(prompt)
            speaker = next(remaining)
            return json.dumps({"finish": not bool(speaker), "next_speaker": speaker,
                               "beat_id": "b1" if speaker else "", "scene_change": "",
                               "cue": f"回应 {speakers[0]} 刚才的话", "director_note": ""})

        def actor(_initialization, _initialization_answer, _history, prompt):
            speaker = prompt.rsplit('"speaker":"', 1)[1].split('"', 1)[0]
            spoken = "我" * 512 if speaker == speakers[0] else f"我是{speaker}。"
            return json.dumps({"scene_id": brief["scene_id"], "speaker": speaker, "entries": [
                {"beat_id": "b1", "spoken": spoken, "first_person_action": "", "private_impulse": ""},
            ]}, ensure_ascii=False), ""

        with tempfile.TemporaryDirectory() as directory:
            block = perform_scene_interaction(brief, {}, plan, "", None, Path(directory), "long-first",
                                              invoke, actor, _cached_payload, None)
        packet = json.loads(block.split("\n", 1)[1])
        self.assertEqual([entry["speaker"] for entry in packet["actor_entries"]], speakers)
        self.assertEqual(len(direction_prompts), 3)
        self.assertIn("我" * 512, direction_prompts[0])
        self.assertIn(speakers[1], direction_prompts[1])

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

    def test_direction_retries_once_after_malformed_model_answer(self):
        brief, plan = _fixture(["纪蔚"])
        calls = []

        def invoke(prompt, role):
            calls.append((prompt, role))
            return "not json" if len(calls) == 1 else json.dumps(plan["opening_direction"], ensure_ascii=False)

        result = _generate_direction("# Scene Interaction Direction", brief, plan, invoke)
        self.assertEqual(result["next_speaker"], "纪蔚")
        self.assertEqual(len(calls), 2)

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

    def test_direction_and_actor_prompts_keep_addressee_and_evidence_visible(self):
        brief, plan = _fixture(["江岫", "阿澍", "温泠"])
        public = [{"speaker": "江岫", "spoken": "他们两位像新婚的。", "first_person_action": ""}]
        director = render_interaction_direction_prompt(brief, plan, public, 1, "")
        self.assertIn("主要在对谁说话", director)
        self.assertIn("先辨认", director)
        self.assertIn("scene_change 承载环境、物件及已演言行引起的外部后果", director)
        self.assertIn("先把轮次交给此人", director)
        self.assertIn("他们两位像新婚的", director)
        direction = {"next_speaker": "阿澍", "beat_id": "b1", "scene_change": "",
                     "cue": "听见江岫打趣，向温泠求证。"}
        actor = render_actor_interaction_prompt(brief, plan, direction, public, "")
        self.assertIn("这次主要面对谁", actor)
        self.assertIn("他们两位像新婚的", actor)
        self.assertIn("向温泠求证", actor)

    def test_actor_life_context_enters_first_turn_and_persists_in_history(self):
        brief, plan = _fixture(["纪蔚"])
        calls = []

        def direct(_prompt, _role):
            return json.dumps({"finish": len(calls) >= 2, "next_speaker": "纪蔚", "beat_id": "b1",
                               "scene_change": "", "cue": "她决定如何回应", "director_note": ""}, ensure_ascii=False)

        def act(_initialization, _answer, history, prompt):
            calls.append((history, prompt))
            return json.dumps({"scene_id": brief["scene_id"], "speaker": "纪蔚", "entries": [{
                "beat_id": "b1", "spoken": "这封信我认得。", "first_person_action": "", "private_impulse": "",
            }]}, ensure_ascii=False), ""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "characters").mkdir()
            (root / "characters" / "纪蔚.yaml").write_text(
                "name: 纪蔚\nbackground_story:\n  hidden_wound: 她欠朋友一个夜班。\n", encoding="utf-8")
            (root / "cache").mkdir()
            perform_scene_interaction(brief, {}, plan, "", None, root / "cache", "life-context",
                                      direct, act, _cached_payload, None, root)
        self.assertIn("她欠朋友一个夜班", calls[0][1])
        self.assertNotIn("她欠朋友一个夜班", calls[1][1])
        self.assertIn("她欠朋友一个夜班", calls[1][0][0][0])

    def test_author_handoff_treats_rehearsal_as_selectable_material(self):
        brief, plan = _fixture(["character/solo"])
        block = render_interaction_materials(plan, [], [{
            "entry_id": "t1:1", "speaker": "character/solo", "beat_id": "b1",
            "spoken": "信是我的。", "first_person_action": "我压住信封。", "private_impulse": "我害怕。",
        }], None, viewpoint=brief["viewpoint"])
        self.assertIn("挑出真正改变关系的回合", block)
        self.assertIn("避免逐条把 spoken 与 first_person_action 排成引号加说话动作的清单", block)
        self.assertIn('"entry_id":"t1:1"', block)

    def test_author_handoff_keeps_new_events_once_but_omits_repeated_director_notes(self):
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
        self.assertIn("该轮新进入的外部情势候选", block)

    def test_author_handoff_retains_distinct_external_changes_in_order(self):
        _, plan = _fixture(["character/a", "character/b"])
        turns = [
            {"turn": 1, "next_speaker": "character/a", "beat_id": "b1", "scene_change": "窗外传来敲门声", "entry_ids": ["t1:1"]},
            {"turn": 2, "next_speaker": "character/b", "beat_id": "b1", "scene_change": "门被风吹开", "entry_ids": ["t2:1"]},
        ]
        block = render_interaction_materials(plan, turns, [], None)
        packet = json.loads(block.split("\n", 1)[1])
        self.assertEqual([turn["scene_change"] for turn in packet["director_turns"]],
                         ["窗外传来敲门声", "门被风吹开"])

    def test_long_rehearsal_uses_recent_public_stage_without_blocking(self):
        brief, plan = _fixture(["character/solo"])
        public = [{"speaker": "character/solo", "spoken": f"第{index}轮", "first_person_action": "我放下信。"}
                  for index in range(26)]
        direction = plan["opening_direction"]
        director = render_interaction_direction_prompt(brief, plan, public, 26, "")
        actor = render_actor_interaction_prompt(brief, plan, direction, public, "")
        self.assertIn("让发起者先表演，下一位才能接住其具体内容", director)
        for prompt in (director, actor):
            self.assertIn("第25轮", prompt)
            self.assertNotIn('"spoken": "第0轮"', prompt)

    def test_one_actor_turn_can_return_three_entries(self):
        brief, plan = _fixture(["character/solo"])

        def finish(_prompt, _role):
            return json.dumps({"finish": True, "next_speaker": "", "beat_id": "", "scene_change": "",
                               "cue": "", "director_note": ""}, ensure_ascii=False)

        def actor(_initialization, _initialization_answer, _history, _prompt):
            return json.dumps({"scene_id": brief["scene_id"], "speaker": "character/solo", "entries": [
                {"beat_id": "b1", "spoken": f"第{index}句话。", "first_person_action": "", "private_impulse": ""}
                for index in range(3)]}, ensure_ascii=False), ""

        with tempfile.TemporaryDirectory() as directory:
            block = perform_scene_interaction(brief, {}, plan, "", None, Path(directory), "three-entries",
                                              finish, actor, _cached_payload, None)
        self.assertEqual(len(json.loads(block.split("\n", 1)[1])["actor_entries"]), 3)

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
        self.assertNotIn("信被打开", compact)
        self.assertNotIn("我害怕", compact)
        self.assertNotIn("actor_prompts", compact)
        self.assertNotIn("B" * 1000, compact)

    def test_production_runtime_hands_interaction_to_main_creator(self):
        class Gateway(_Gateway):
            def __init__(self):
                super().__init__()
                self.directions = iter(["character/protagonist", ""])
                self.actor_turns = []

            def run(self, workspace, prompt, *, role, timeout, event_sink=None, cancel_event=None):
                if prompt.startswith("# Scene Performance Direction"):
                    self.calls.append((role, prompt))
                    _, plan = _fixture(["character/protagonist", "character/sister"])
                    plan["opening_direction"]["next_speaker"] = "character/sister"
                    answer = json.dumps(plan, ensure_ascii=False)
                elif prompt.startswith("# Scene Interaction Direction"):
                    self.calls.append((role, prompt))
                    speaker = next(self.directions)
                    answer = json.dumps({"finish": not bool(speaker), "next_speaker": speaker,
                                         "beat_id": "b1" if speaker else "", "scene_change": "",
                                         "cue": "信已经打开", "director_note": "关系需要转向"}, ensure_ascii=False)
                elif role == "environment-writer":
                    self.calls.append((role, prompt))
                    answer = json.dumps({"scene_id": "scene_0001", "passages": [
                        {"beat_id": "b1", "description": "门边的光沿着信封的折痕移动。"},
                    ]}, ensure_ascii=False)
                else:
                    return super().run(workspace, prompt, role=role, timeout=timeout,
                                       event_sink=event_sink, cancel_event=cancel_event)
                return RoleConversationResult("pi-worker", "run-interaction", "test/model", answer)

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
            creator_prompts = [prompt for role, prompt in gateway.calls
                               if role == "worker" and "## Character And Environment Candidate Materials" in prompt]
            self.assertEqual(len(gateway.actor_turns), 2)
            self.assertEqual(len(creator_prompts), 1)
            environment_prompts = [json.loads(prompt) for role, prompt in gateway.calls if role == "environment-writer"]
            self.assertEqual(environment_prompts[0]["schema"], "arcvellum/environment-conversation/v1")
            self.assertTrue(environment_prompts[0]["initialization"].startswith("【SCENE_LOAD】"))
            self.assertTrue(environment_prompts[0]["prompt"].startswith("# Independent Environment Writing"))
            self.assertIn("你把信拿走了？", creator_prompts[0])
            self.assertIn("是我拿的，先听我说完。", creator_prompts[0])
            self.assertIn('"director_turns"', creator_prompts[0])
            self.assertIn('"environment_candidates"', creator_prompts[0])
            self.assertNotIn('"actor_prompts"', creator_prompts[0])
            self.assertNotIn('"environment_initialization"', creator_prompts[0])
            self.assertIn("设定展开", creator_prompts[0])
            self.assertIn("对白可绕路、说错或沉默，服务眼前的关系", creator_prompts[0])
            self.assertTrue(all("[LANGUAGE_STYLE]\nANTI_PLAIN\nPOLISHED\nANTI_SHORT_SENTENCES" in call[1]
                                for call in gateway.actor_turns))
            self.assertTrue(all("[LITERATURE_STYLE]" in call[1] and "【角色沉浸要求】" in call[1]
                                for call in gateway.actor_turns))
            self.assertTrue(all("面对他人时，我有权试探" in call[-1]
                                for call in gateway.actor_turns))
            self.assertTrue(result.prose)
            self.assertGreater(runtime.metrics.provider_calls, 4)

    def test_single_actor_interacts_with_scene_without_fictional_partner(self):
        brief, plan = _fixture(["character/solo"])
        plan["beats"].append({"beat_id": "b2", "event": "下一轮才会出现的外部变化"})
        turns = iter(["character/solo", ""])
        histories = []
        seen_directions = []
        emitted = []

        def invoke(prompt, role):
            self.assertEqual(role, "worker")
            seen_directions.append(prompt)
            speaker = next(turns)
            return json.dumps({
                "finish": not bool(speaker), "next_speaker": speaker, "beat_id": "b1" if speaker else "",
                "scene_change": "信封里的纸滑出来" if speaker else "", "cue": "现在怎么办？",
                "director_note": "主创判断这封信对后续世界状态的影响。",
            }, ensure_ascii=False)

        def actor(initialization, initialization_answer, history, prompt):
            histories.append(history)
            self.assertIn("SELF_CLAIM_ACTOR", initialization)
            self.assertNotIn("character/other", prompt)
            self.assertIn("周围可感的空间素材", prompt)
            answer = json.dumps({"scene_id": brief["scene_id"], "speaker": "character/solo", "entries": [
                {"beat_id": "b1", "spoken": "这信怎么会在这里？", "first_person_action": "我把纸压在桌上。",
                 "private_impulse": "我不敢翻到背面。"},
                {"beat_id": "b2", "spoken": "未来的变化已经发生。", "first_person_action": "",
                 "private_impulse": "我先把未来写了。"},
            ]}, ensure_ascii=False)
            return answer, ""  # 初始化允许没有可见回复。

        with tempfile.TemporaryDirectory() as directory:
            session_path = Path(directory) / "performance-interaction-session-digest.json"

            def emit(event, data):
                self.assertTrue(session_path.is_file())
                self.assertEqual(json.loads(session_path.read_text(encoding="utf-8"))["directions"][-1]["turn"], data["turn"])
                emitted.append((event, data))

            block = perform_scene_interaction(
                brief, {}, plan, "", {"passages": [{"beat_id": "b1", "description": "桌沿有冷光。"}]},
                Path(directory), "digest", invoke, actor, _cached_payload, emit,
            )
        packet = json.loads(block.split("\n", 1)[1])
        self.assertEqual(len(packet["actor_entries"]), 2)
        self.assertTrue(all(item["beat_id"] == "b1" for item in packet["actor_entries"]))
        self.assertNotIn("未来的变化已经发生", json.dumps(packet["actor_entries"], ensure_ascii=False))
        self.assertEqual([row["next_speaker"] for row in packet["director_turns"]], ["character/solo"] * 2)
        self.assertEqual([len(item) for item in histories], [0, 1])
        self.assertEqual(len(seen_directions), 2)  # 次轮与结束；首轮已并入场景编排。
        self.assertIn("这信怎么会在这里", seen_directions[-1])
        self.assertNotIn("我不敢翻到背面", seen_directions[-1])
        self.assertNotIn("actor_prompts", seen_directions[-1])
        self.assertNotIn("environment_initialization", seen_directions[-1])
        self.assertEqual(len(emitted), 2)
        self.assertIn("这信怎么会在这里", emitted[0][1]["turn_entries"][0]["spoken"])
        self.assertNotIn("private_impulse", json.dumps(emitted, ensure_ascii=False))

    def test_environment_material_survives_actor_silence(self):
        brief, plan = _fixture(["character/solo"])
        environment = {"passages": [{"beat_id": "b1", "description": "桌沿有冷光。"}]}

        def invoke(prompt, role):
            return json.dumps({"finish": True, "next_speaker": "", "beat_id": ""})

        def actor(initialization, initialization_answer, history, prompt):
            return json.dumps({"scene_id": brief["scene_id"], "speaker": "character/solo", "entries": []}), ""

        with tempfile.TemporaryDirectory() as directory:
            block = perform_scene_interaction(
                brief, {}, plan, "", environment, Path(directory), "digest", invoke, actor, _cached_payload, None,
            )
            fallback = _try_interaction(
                brief, {}, plan, [], "", environment, Path(directory), "digest", invoke, None, None,
            )
            failed_actor = _try_interaction(
                brief, {}, plan, ["character/solo"], "", environment, Path(directory), "different-digest", invoke,
                lambda *args: (_ for _ in ()).throw(RuntimeError("actor failed")), None,
            )
        self.assertIn("桌沿有冷光", block)
        self.assertIn("桌沿有冷光", fallback)
        self.assertIn("桌沿有冷光", failed_actor)

    def test_failed_later_turn_preserves_completed_actor_material_and_resumes(self):
        brief, plan = _fixture(["character/solo"])
        actor_calls = []
        direction_calls = []

        def invoke(prompt, role):
            direction_calls.append(prompt)
            return json.dumps({"finish": len(direction_calls) > 1,
                               "next_speaker": "character/solo" if len(direction_calls) == 1 else "",
                               "beat_id": "b1" if len(direction_calls) == 1 else "",
                               "scene_change": "门外有人来了", "cue": "我认得脚步声"}, ensure_ascii=False)

        def actor(initialization, initialization_answer, history, prompt):
            actor_calls.append(prompt)
            if len(actor_calls) == 2:
                raise RuntimeError("conversation returned no answer")
            return json.dumps({"scene_id": brief["scene_id"], "speaker": "character/solo", "entries": [
                {"beat_id": "b1", "spoken": "先让我听完。" if not history else "我听见他来了。",
                 "first_person_action": "", "private_impulse": ""},
            ]}, ensure_ascii=False), ""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            salvaged = _try_interaction(
                brief, {}, plan, ["character/solo"], "", None, root, "digest",
                invoke, actor, None,
            )
            self.assertIn("先让我听完。", salvaged)
            self.assertEqual(len(json.loads(salvaged.split("\n", 1)[1])["actor_entries"]), 1)
            resumed = perform_scene_interaction(
                brief, {}, plan, "", None, root, "digest", invoke, actor, _cached_payload, None,
            )
        self.assertEqual(len(json.loads(resumed.split("\n", 1)[1])["actor_entries"]), 2)
        self.assertEqual(len(actor_calls), 3)  # The completed first turn was not regenerated.

    def test_creator_requests_actor_continuation_and_environment_then_writes(self):
        class Gateway(_Gateway):
            def __init__(self):
                super().__init__()
                self.create_prompts = []
                self.actor_histories = []
                self.environment_prompts = []
                self.direction_calls = 0

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
                    self.direction_calls += 1
                    return RoleConversationResult("pi-worker", "direction", "test/model", json.dumps(
                        {"finish": True, "next_speaker": "", "beat_id": "", "scene_change": "", "cue": "", "director_note": ""}))
                if prompt.startswith("# Scene Create"):
                    self.create_prompts.append(prompt)
                    if len(self.create_prompts) == 1:
                        answer = {"material_requests": [
                            {"kind": "actor", "speaker": "character/solo", "beat_id": "b1", "cue": "看见对方仍在等回答"},
                            {"kind": "environment", "beat_id": "b1", "cue": "雨光在信封上的变化"},
                        ]}
                    else:
                        answer = {"prose": "他说：“你还等着，我怎么能装作没看见？”窗上的雨光漫到信封背面。",
                                  "decision_summary": "看见与回应使关系变化。", "scene_delta": {}, "material_requests": []}
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
            self.assertEqual(gateway.actor_histories, [0, 1])
            self.assertEqual(gateway.direction_calls, 1)
            self.assertEqual(len(gateway.create_prompts), 2)
            self.assertIn("你还等着，我怎么能装作没看见？", gateway.create_prompts[1])
            self.assertIn("窗上的雨光慢慢漫到信封背面", gateway.create_prompts[1])
            self.assertEqual(len(gateway.environment_prompts), 2)
            self.assertTrue(all(item["initialization"].startswith("【SCENE_LOAD】")
                                for item in gateway.environment_prompts))
            self.assertEqual(runtime.metrics.provider_calls,
                             len(gateway.calls) + len(gateway.environment_prompts)
                             + len(gateway.actor_histories) + 1)

    def test_material_requests_follow_known_roles_and_beats(self):
        brief, plan = _fixture(["character/solo"])
        requests = parse_scene_material_requests({"material_requests": [
            {"kind": "actor", "speaker": "character/solo", "cue": "多说些眼前的事"},
            {"kind": "environment", "cue": "观察雨后的桌面"},
        ]}, brief, plan)
        self.assertEqual([item["kind"] for item in requests], ["actor", "environment"])
        self.assertEqual([item["beat_id"] for item in requests], ["b1", "b1"])
        self.assertEqual(requests[0]["scene_change"], "")
        from_entry = parse_scene_material_requests({"material_requests": [
            {"kind": "actor", "speaker": "character/solo", "beat_id": "t2:1", "cue": "继续回应"},
        ]}, brief, plan, actor_entries=[{"entry_id": "t2:1", "beat_id": "b1", "speaker": "character/solo"}])
        self.assertEqual(from_entry[0]["beat_id"], "b1")
        with self.assertRaisesRegex(ValueError, "speaker"):
            parse_scene_material_requests({"material_requests": [{"kind": "actor", "speaker": "unknown", "cue": "说话"}]}, brief, plan)
        with self.assertRaisesRegex(ValueError, "known beat"):
            parse_scene_material_requests({"material_requests": [{"kind": "environment", "beat_id": "b9", "cue": "观察"}]}, brief, plan)

    def test_creator_can_add_a_new_change_between_turns_of_same_actor(self):
        brief, plan = _fixture(["character/solo"])
        requests = parse_scene_material_requests({"material_requests": [
            {"kind": "actor", "speaker": "character/solo", "beat_id": "b1",
             "scene_change": "门外传来一声敲门", "cue": "我认得这个敲门习惯"},
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
                if prompt.startswith("# Scene Revision"):
                    self.revision_prompts.append(prompt)
                    answer = ({"material_requests": [{"kind": "actor", "speaker": "character/protagonist",
                                                     "cue": "再回应妹妹一次"}]}
                              if len(self.revision_prompts) == 1 else
                              {"prose": "他说：“我会把信交给你。”", "decision_summary": "修订关系转折。",
                               "scene_delta": {}, "material_requests": []})
                    return RoleConversationResult("pi-worker", "revision", "test/model", json.dumps(answer, ensure_ascii=False))
                return super().run(workspace, prompt, role=role, timeout=timeout,
                                   event_sink=event_sink, cancel_event=cancel_event)

        original = "一级角色候选\n" + json.dumps({"actor_entries": [
            {"entry_id": "t1:1", "speaker": "character/protagonist", "spoken": "信是我拿的。",
             "first_person_action": "", "private_impulse": ""},
        ]}, ensure_ascii=False)
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
            with patch("literary_engineering_studio.runtimes.pi_scene_transaction.scene_performance_materials",
                       return_value=original):
                candidate = runtime.create_scene("tx-revision-request", brief)
            with patch("literary_engineering_studio.runtimes.pi_scene_transaction.fulfill_scene_material_requests",
                       return_value=supplemented) as fulfill:
                revised = runtime.revise_scene("tx-revision-request", brief, candidate,
                                               VerificationReport(brief.scene_id, len(candidate.prose)), None, attempt=1)
            self.assertEqual(fulfill.call_count, 1)
            self.assertIn("我会把信交给你", gateway.revision_prompts[1])
            self.assertIn("我会把信交给你", revised.prose)

    def test_retry_reuses_requested_materials_without_replaying_preparation(self):
        supplemented = "环境候选\n" + json.dumps({"actor_entries": [], "environment_candidates": {
            "passages": [{"beat_id": "b1", "description": "雨停了。"}],
        }}, ensure_ascii=False)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            brief = replace(_brief(), length=type(_brief().length)(100, 0, 200))
            runtime = PiSceneTransactionRuntime(
                {"application": {"scene_performance_agents": {"enabled": True}}},
                project_root=root, data_root=root / ".studio", gateway=_Gateway(),
            )
            request = json.dumps({"material_requests": [{"kind": "environment", "cue": "看看雨后"}]}, ensure_ascii=False)
            with patch("literary_engineering_studio.runtimes.pi_scene_transaction.scene_performance_materials",
                       return_value="") as prepare, patch(
                           "literary_engineering_studio.runtimes.pi_scene_transaction.fulfill_scene_material_requests",
                           return_value=supplemented,
                       ) as fulfill, patch.object(runtime, "_run", side_effect=[request, RuntimeError("temporary provider stop")]):
                with self.assertRaisesRegex(RuntimeError, "temporary provider stop"):
                    runtime.create_scene("tx-resume", brief)
            self.assertEqual(prepare.call_count, 1)
            self.assertEqual(fulfill.call_count, 1)
            final = json.dumps({"prose": "雨停了。", "decision_summary": "雨后停留。", "scene_delta": {}}, ensure_ascii=False)
            with patch("literary_engineering_studio.runtimes.pi_scene_transaction.scene_performance_materials",
                       side_effect=AssertionError("preparation replayed")), patch.object(runtime, "_run", return_value=final):
                result = runtime.create_scene("tx-resume", brief)
            self.assertEqual(result.prose, "雨停了。")

    def test_three_actor_order_is_directed_by_scene_not_cyclic_rotation(self):
        speakers = ["character/a", "character/b", "character/c"]
        brief, plan = _fixture(speakers)
        plan["opening_direction"]["next_speaker"] = speakers[1]
        order = iter([speakers[0], speakers[2], speakers[1], ""])
        calls = []

        def invoke(_prompt, _role):
            speaker = next(order)
            return json.dumps({"finish": not bool(speaker), "next_speaker": speaker,
                               "beat_id": "b1" if speaker else "", "scene_change": "", "cue": "回应刚才的话",
                               "director_note": ""})

        def actor(_initialization, _initialization_answer, history, prompt):
            speaker = prompt.rsplit('"speaker":"', 1)[1].split('"', 1)[0]
            calls.append((speaker, len(history), prompt))
            return json.dumps({"scene_id": brief["scene_id"], "speaker": speaker, "entries": [
                {"beat_id": "b1", "spoken": f"我是{speaker}。", "first_person_action": "", "private_impulse": "我有疑心。"},
            ]}, ensure_ascii=False), "初始化完成"

        with tempfile.TemporaryDirectory() as directory:
            block = perform_scene_interaction(
                brief, {}, plan, "", None, Path(directory), "digest", invoke, actor, _cached_payload, None,
            )
        packet = json.loads(block.split("\n", 1)[1])
        self.assertEqual([(speaker, count) for speaker, count, _ in calls],
                         [(speakers[1], 0), (speakers[0], 0), (speakers[2], 0), (speakers[1], 1)])
        self.assertEqual([item["speaker"] for item in packet["actor_entries"]],
                         [speakers[1], speakers[0], speakers[2], speakers[1]])
        self.assertEqual(packet["actor_entries"][0]["private_impulse"], "")

    def test_scene_performance_uses_director_authored_initialization_when_saved_persona_exists(self):
        brief, plan = _fixture(["character/solo"])
        plan["actor_prompts"]["character/solo"] += "\n\n[LANGUAGE_STYLE]\nVOICE_PLAYFUL_WITH_BARBS"
        directions = iter([""])
        initializations = []
        saved = "【PERSONA_LOAD】\nSELF_CLAIM_SOLO\n\n【PERSONALITY_CORE】\nTRAIT_WARY\n\n【PERSONALITY_PUBLIC】\nTRAIT_WRY\n\n[LANGUAGE_STYLE]\nPOLISHED\n\n[LITERATURE_STYLE]\nKAFKA_LIKE"

        def invoke(prompt, role):
            if prompt.startswith("# Scene Performance Direction"):
                return json.dumps(plan, ensure_ascii=False)
            if role == "environment-writer":
                return json.dumps({"scene_id": brief["scene_id"], "passages": []})
            speaker = next(directions)
            return json.dumps({"finish": not bool(speaker), "next_speaker": speaker,
                               "beat_id": "b1" if speaker else "", "scene_change": "", "cue": "",
                               "director_note": ""})

        def actor(initialization, _initialization_answer, _history, _prompt):
            initializations.append(initialization)
            return json.dumps({"scene_id": brief["scene_id"], "speaker": "character/solo", "entries": [
                {"beat_id": "b1", "spoken": "信是给我的。", "first_person_action": "", "private_impulse": ""},
            ]}, ensure_ascii=False), ""

        with tempfile.TemporaryDirectory() as directory:
            block = scene_performance_materials(
                brief=brief, expression={"actor_personas": {"character/solo": saved}}, sources="", style_reference="", cache_root=Path(directory),
                config={"application": {"scene_performance_agents": {"enabled": True, "mode": "whole-scene"}}},
                invoke=invoke,
                invoke_actor_turn=actor,
            )
        self.assertIn("actor_entries", block)
        self.assertIn("信是给我的", block)
        self.assertEqual(len(initializations), 1)
        self.assertIn("VOICE_PLAYFUL_WITH_BARBS", initializations[0])
        self.assertNotIn("KAFKA_LIKE", initializations[0])

    def test_failed_actor_turn_does_not_resume_whole_scene_task_mode(self):
        brief, plan = _fixture(["character/solo"])
        calls = []

        def invoke(prompt, role):
            calls.append((role, prompt))
            if prompt.startswith("# Scene Performance Direction"):
                return json.dumps(plan, ensure_ascii=False)
            if role == "environment-writer":
                return json.dumps({"scene_id": brief["scene_id"], "passages": []})
            return json.dumps({"finish": False, "next_speaker": "character/solo", "beat_id": "b1",
                               "scene_change": "", "cue": "", "director_note": ""})

        def actor(*_args):
            raise RuntimeError("角色对戏暂不可用")

        with tempfile.TemporaryDirectory() as directory:
            block = scene_performance_materials(
                brief=brief, expression={}, sources="", style_reference="", cache_root=Path(directory),
                config={"application": {"scene_performance_agents": {"enabled": True, "mode": "whole-scene"}}},
                invoke=invoke, invoke_actor_turn=actor,
            )
        self.assertEqual(block, "")
        self.assertFalse(any(role == "character-actor" for role, _ in calls))

    def test_direction_rejects_unknown_participant_without_adding_literary_gate(self):
        brief, plan = _fixture(["character/solo"])
        with self.assertRaisesRegex(ValueError, "scene participant"):
            parse_interaction_direction({"finish": False, "next_speaker": "character/stranger",
                                         "beat_id": "b1"}, brief, plan)


if __name__ == "__main__":
    unittest.main()
