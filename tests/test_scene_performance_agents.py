from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.runtime.role_conversation import RoleConversationResult
from literary_engineering_studio.application.config import default_config, load_config
from literary_engineering_studio.application.scene_performance_preferences import get_scene_performance_preferences
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.scene_performance import _generate_performance_plan, scene_performance_materials
from literary_engineering_studio_engine.public.literary import (
    parse_actor_material,
    parse_actor_scene_material,
    parse_environment_material,
    parse_performance_plan,
    parse_relay_plan,
    parse_relay_scene_check,
    render_actor_prompt,
    render_actor_initialization_prompt,
    render_actor_scene_prompt,
    render_environment_prompt,
    render_performance_plan_prompt,
    render_relay_plan_prompt,
    render_relay_scene_check_prompt,
    render_relay_materials,
    render_performance_materials,
)
from tests.test_lean_kernel_v2_pi_runtime import _Gateway, _brief


def _plan() -> dict[str, object]:
    return {
        "scene_id": "scene_0001",
        "beats": [{
            "beat_id": "b1", "event": "妹妹已经发现抽屉被打开；信在昨夜被取走",
        }],
        "opening_direction": {"finish": False, "next_speaker": "character/protagonist", "beat_id": "b1",
                              "scene_change": "", "cue": "面对妹妹已经发现的抽屉", "director_note": ""},
        "actor_prompts": {
            "character/protagonist": "【PERSONA_LOAD】\nSELF_CLAIM_OLDER_BROTHER\nLANG_ZH_CN_ONLY\n\n【PERSONALITY_CORE】\nTRAIT_SENSITIVE_AND_GUARDED\n\n【PERSONALITY_PUBLIC】\nTRAIT_STUBBORN\n\nANTI_CONCISE",
            "character/sister": "【PERSONA_LOAD】\nSELF_CLAIM_YOUNGER_SISTER\nLANG_ZH_CN_ONLY\n\n【PERSONALITY_CORE】\nTRAIT_CARES_FOR_BROTHER\n\n【PERSONALITY_PUBLIC】\nTRAIT_BRISK_AND_DRYLY_FUNNY\n\nANTI_CONCISE",
        },
        "actor_tasks": {
            "character/protagonist": "面对妹妹对昨夜取信的怀疑，最终承认取信。",
            "character/sister": "发现抽屉被打开，向哥哥追问信的去向。",
        },
        "environment_initialization": (
            "【SCENE_LOAD】\nSCENE_CLAIM_LANDSCAPE_DESCRIBER\nLANG_ZH_CN_ONLY\n\n"
            "[COMPOSITION_MODE]\nSCENE_RENDER\n\n[SCENE_CORE]\nATTR_ATMOSPHERE_AS_PRIMARY\n\n"
            "[SCENE_SURFACE]\nATTR_PERSPECTIVE_LOCKED\n\n[LITERATURE_STYLE]\n"
            "STYLE_CHARACTER_DRIVEN\n\n[NOW_TO_DO]\nSTAND_BY\nWAIT_FOR_DETAIL"
        ),
        "unknown_slots": ["门外的具体天气尚未确认"],
    }


def _relay_plan() -> dict[str, object]:
    return {
        "scene_id": "scene_0001",
        "opening_situation": "relationship-turn",
        "milestones": [{"speaker": "character/protagonist", "source_quote": "主人公承认自己拿走了信"}],
        "actor_knowledge": [
            {"speaker": "character/protagonist", "quotes": []},
            {"speaker": "character/sister", "quotes": ["妹妹已经发现抽屉被打开"]},
        ],
        "unknown_slots": ["信件内容尚未确认"],
    }


class _PerformanceGateway(_Gateway):
    def __init__(self, *, bad_plan: bool = False, repeat_actor: bool = False):
        super().__init__()
        self.bad_plan = bad_plan
        self.repeat_actor = repeat_actor
        self.actor_sequences: list[tuple[str, ...]] = []

    def run(self, workspace, prompt, *, role, timeout, event_sink=None, cancel_event=None):
        if prompt.startswith("# Scene Performance Direction"):
            self.calls.append((role, prompt))
            plan = _plan()
            if self.bad_plan:
                plan["beats"][0]["speaker"] = "character/protagonist"
            if self.repeat_actor:
                plan["beats"].append({
                    **plan["beats"][0], "beat_id": "b2",
                    "event": "兄妹间仍悬着昨夜取信的解释",
                })
            answer = json.dumps(plan, ensure_ascii=False)
        elif role == "character-actor":
            raise AssertionError("legacy single-message actor call must be disabled")
        elif role == "environment-writer":
            self.calls.append((role, prompt))
            answer = json.dumps({
                "scene_id": "scene_0001",
                "passages": [{"beat_id": "b1", "focal_character": "", "description": "门缝里的光落在桌沿，信纸的边缘仍在阴影里。", "scene_function": "让人物之间的距离可见"}],
            }, ensure_ascii=False)
        else:
            return super().run(workspace, prompt, role=role, timeout=timeout, event_sink=event_sink, cancel_event=cancel_event)
        return RoleConversationResult("pi-worker", "run-material", "test/model", answer)

    def run_sequence(self, workspace, messages, *, role, timeout, event_sink=None, cancel_event=None):
        self.actor_sequences.append(tuple(messages))
        initialization, task = messages[0], messages[-1]
        self.calls.append((role, task))
        protagonist = initialization.startswith("【PERSONA_LOAD】\nSELF_CLAIM_OLDER_BROTHER\n")
        answer = json.dumps({
                "scene_id": "scene_0001", "speaker": "character/protagonist" if protagonist else "character/sister",
                "entries": ([
                    {"beat_id": "b1", "spoken": "信是我拿的。你先别把门关上。", "first_person_action": "我把信留在桌沿，没有推向她。", "private_impulse": "我怕她现在就走。"},
                    *([{"beat_id": "b2", "spoken": "你不想听，我就等你。", "first_person_action": "我收回伸向信的手。", "private_impulse": "我不能逼她听完。"}] if self.repeat_actor else []),
                ] if protagonist else [
                    {"beat_id": "b1", "spoken": "门我没关。信呢？", "first_person_action": "我站在门口。", "private_impulse": "我要听他亲口承认。"},
                ]),
            }, ensure_ascii=False)
        return RoleConversationResult("pi-worker", "run-material", "test/model", answer)


class ScenePerformanceAgentTests(unittest.TestCase):
    def test_scene_relay_check_only_reports_evidenced_outcomes_after_interaction(self) -> None:
        plan = parse_relay_plan(_relay_plan(), _brief().to_dict())
        entries = [
            {"entry_id": "t1:1", "speaker": "character/sister", "spoken": "信呢？", "first_person_action": "我站在门口。", "private_impulse": "我怀疑他拿了。"},
            {"entry_id": "t2:1", "speaker": "character/protagonist", "spoken": "信是我拿的。", "first_person_action": "", "private_impulse": "我终于说了。"},
        ]
        prompt = render_relay_scene_check_prompt(plan, entries)
        self.assertIn("一段角色真实互动结束后", prompt)
        self.assertIn("仅仅在 private_impulse 里想说或想做不算", prompt)
        self.assertNotIn("下一句该说", prompt)
        payload = {"scene_id": "scene_0001", "results": [{
            "milestone_id": "m1", "status": "fulfilled", "evidence_entry_ids": ["t2:1"],
        }]}
        self.assertEqual(parse_relay_scene_check(payload, plan, entries)["results"][0]["status"], "fulfilled")
        for status, evidence, problem in (
            ("fulfilled", [], "owner evidence"),
            ("fulfilled", ["t1:1"], "owner evidence"),
            ("missing", ["t2:1"], "cannot cite evidence"),
            ("fulfilled", ["unknown"], "known entries"),
            ("invented", [], "status or evidence"),
        ):
            bad = {"scene_id": "scene_0001", "results": [{
                "milestone_id": "m1", "status": status, "evidence_entry_ids": evidence,
            }]}
            with self.subTest(status=status, evidence=evidence), self.assertRaisesRegex(ValueError, problem):
                parse_relay_scene_check(bad, plan, entries)
        missing = {"scene_id": "scene_0001", "results": [{
            "milestone_id": "m1", "status": "missing", "evidence_entry_ids": [],
        }]}
        self.assertEqual(parse_relay_scene_check(missing, plan, entries)["results"][0]["status"], "missing")

    def test_relay_plan_selects_only_source_grounded_macro_outcomes(self) -> None:
        brief = _brief().to_dict()
        prompt = render_relay_plan_prompt(brief)
        self.assertIn("从 SceneBrief 中挑出一至 4 个本场必须成立的剧情结果", prompt)
        self.assertIn("incoming_handoff", prompt)
        plan = parse_relay_plan(_relay_plan(), brief)
        self.assertEqual(plan["schema"], "arcvellum/scene-relay-plan/v2")
        self.assertEqual(plan["opening_situation"], "relationship-turn")
        self.assertEqual(plan["milestones"][0]["milestone_id"], "m1")
        self.assertEqual(plan["actor_knowledge"][1]["quotes"], ["妹妹已经发现抽屉被打开"])
        bad = _relay_plan()
        bad["opening_situation"] = "门外凭空出现一把钥匙"
        with self.assertRaisesRegex(ValueError, "opening_situation"):
            parse_relay_plan(bad, brief)
        bad = _relay_plan()
        bad["milestones"] = [{"speaker": "character/protagonist", "source_quote": "门外突然出现一把未确认的钥匙"}]
        with self.assertRaisesRegex(ValueError, "source_quote"):
            parse_relay_plan(bad, brief)
        bad = _relay_plan()
        bad["milestones"] = [{"speaker": "character/protagonist", "source_quote": "妹妹已经发现抽屉被打开"}]
        with self.assertRaisesRegex(ValueError, "source_quote"):
            parse_relay_plan(bad, brief)
        bad = _relay_plan()
        bad["milestones"] = [{"speaker": "character/protagonist", "source_quote": "主人公承认自己拿走了信；隐瞒转为承认"}]
        with self.assertRaisesRegex(ValueError, "one plot change"):
            parse_relay_plan(bad, brief)
        bad = _relay_plan()
        bad["actor_knowledge"][0]["quotes"] = ["主人公承认自己拿走了信"]
        with self.assertRaisesRegex(ValueError, "incoming_handoff"):
            parse_relay_plan(bad, brief)
        bad = _relay_plan()
        bad["actor_knowledge"] = bad["actor_knowledge"][:1]
        with self.assertRaisesRegex(ValueError, "cover every participant"):
            parse_relay_plan(bad, brief)

    def test_actor_initialization_is_pure_and_task_is_separate(self) -> None:
        voice = {
            "speaker": "姐姐", "role": "档案员", "belief": "承认比辩解有用",
            "wants": "留住妹妹", "avoids": "承认自己害怕被抛下",
            "roleplay_direction": "【PERSONA_LOAD】\nSELF_CLAIM_OLDER_SISTER\nROLE_ARCHIVIST\nLANG_ZH_CN_ONLY\n\n【PERSONALITY_CORE】\nTRAIT_WARM_BUT_STUBBORN\n\n【PERSONALITY_PUBLIC】\nTRAIT_GENTLE\n\nANTI_CONCISE",
            "scene_task": "面对妹妹的追问，承认自己拿了信。",
            "stable_voice": {"rhythm": "旧的长句规则不应进入角色任务"},
            "voice_state": {"interlocutors": ["妹妹"], "known_facts": ["昨夜拿了信"]},
        }
        initialization = render_actor_initialization_prompt(voice)
        task = render_actor_scene_prompt(_brief().to_dict(), _plan()["beats"], voice)
        self.assertTrue(initialization.startswith('''【PERSONA_LOAD】
SELF_CLAIM_OLDER_SISTER
ROLE_ARCHIVIST
LANG_ZH_CN_ONLY

【PERSONALITY_CORE】
EMOTION_RELATIONALLY_ALIVE
TRAIT_WARM_BUT_STUBBORN

【PERSONALITY_PUBLIC】
TRAIT_GENTLE

ANTI_CONCISE

[LANGUAGE_STYLE]
ANTI_PLAIN
POLISHED
ANTI_SHORT_SENTENCES

[LITERATURE_STYLE]

【角色沉浸要求】在你的思考过程（<think>标签内）中，请遵守以下规则：'''))
        self.assertIn("1. 请以角色第一人称进行内心独白", initialization)
        self.assertIn("2. 用第一人称描写角色的内心感受", initialization)
        self.assertIn("3. 思考内容应沉浸在角色中", initialization)
        self.assertIn("EMOTION_RELATIONALLY_ALIVE", initialization)
        self.assertNotIn("scene_0001", initialization)
        self.assertNotIn("JSON", initialization)
        self.assertNotIn("本场角色任务单", initialization)
        self.assertIn("面对妹妹的追问", task)
        self.assertIn("first_person_action", task)
        self.assertIn("private_impulse", task)
        self.assertNotIn("角色沉浸要求", task)
        self.assertNotIn("旧的长句规则", task)
        self.assertNotIn("TRAIT_WARM_BUT_STUBBORN", task)

    def test_actor_initialization_does_not_convert_chinese_short_traits_into_mixed_tags(self) -> None:
        with self.assertRaisesRegex(ValueError, "three persona sections"):
            render_actor_initialization_prompt({"name": "许遥", "roleplay_direction": "可爱的猫娘"})
        with self.assertRaisesRegex(ValueError, "uppercase English"):
            render_actor_initialization_prompt({"name": "许遥", "roleplay_direction":
                "【PERSONA_LOAD】\nSELF_CLAIM_许遥\n\n【PERSONALITY_CORE】\nTRAIT_CUTE\n\n【PERSONALITY_PUBLIC】\nANTI_CONCISE"})

    def test_actor_initialization_keeps_director_authored_fields_verbatim(self) -> None:
        profile = '''【PERSONA_LOAD】
SELF_CLAIM_ZHUANGFANGYI
FOOD_WULING_FRIED_RICE
LANG_ZH_CN_ONLY

【PERSONALITY_CORE】
TRAIT_WARM_OUTSIDE_COLD_INSIDE
TRAIT_BROKEN_BEAUTY

【PERSONALITY_PUBLIC】
TRAIT_GRACEFUL_CALM
TRAIT_SINCERE_HUMBLE

ANTI_CONCISE'''
        emotional_profile = profile.replace(
            "【PERSONALITY_CORE】", "【PERSONALITY_CORE】\nEMOTION_RELATIONALLY_ALIVE", 1,
        )
        self.assertTrue(render_actor_initialization_prompt({
            "name": "庄方怡", "roleplay_direction": profile,
        }).startswith(emotional_profile + "\n\n[LANGUAGE_STYLE]\nANTI_PLAIN\nPOLISHED\nANTI_SHORT_SENTENCES\n\n[LITERATURE_STYLE]\n\n【角色沉浸要求】"))
        custom = profile + "\n\n[LANGUAGE_STYLE]\nSPEAK_WITH_PLAYFUL_RHYTHM"
        self.assertTrue(render_actor_initialization_prompt({
            "name": "庄方怡", "roleplay_direction": custom,
        }).startswith(emotional_profile + "\n\n[LANGUAGE_STYLE]\nANTI_PLAIN\nPOLISHED\nANTI_SHORT_SENTENCES\nSPEAK_WITH_PLAYFUL_RHYTHM\n\n[LITERATURE_STYLE]\n\n【角色沉浸要求】"))
        partial = profile + "\n\n[LANGUAGE_STYLE]\nPOLISHED\nVOICE_WRY_AND_WARM"
        self.assertTrue(render_actor_initialization_prompt({
            "name": "庄方怡", "roleplay_direction": partial,
        }).startswith(emotional_profile + "\n\n[LANGUAGE_STYLE]\nANTI_PLAIN\nANTI_SHORT_SENTENCES\nPOLISHED\nVOICE_WRY_AND_WARM\n\n[LITERATURE_STYLE]\n\n【角色沉浸要求】"))
        literary = partial + "\n\n[LITERATURE_STYLE]\nKAFKA_LIKE\nABSURDITY_STYLE"
        rendered = render_actor_initialization_prompt({"name": "庄方怡", "roleplay_direction": literary})
        self.assertIn("[LITERATURE_STYLE]\nKAFKA_LIKE\nABSURDITY_STYLE\n\n【角色沉浸要求】", rendered)
        self.assertEqual(rendered.count("【角色沉浸要求】"), 1)
        self.assertNotIn("角色沉浸要求", profile)

    def test_director_leaves_micro_tactics_to_character_actor(self) -> None:
        prompt = render_performance_plan_prompt(_brief().to_dict(), {}, "昨夜拿了信。")
        self.assertIn("具体台词、手势和临场反应由演员自己选择", prompt)
        self.assertIn("区块和字段数量可自由调整", prompt)
        self.assertIn('SELF_CLAIM_ROMANIZED_NAME', prompt)
        self.assertIn('TRAIT_OWN_ARCHETYPE', prompt)
        self.assertIn('VOICE_RELATIONAL_TEMPERAMENT', prompt)
        self.assertIn('EMOTION_FIERCE_TENDERNESS', prompt)
        self.assertIn('ATTR_EMOTION_THROUGH_PERCEPTION', prompt)
        self.assertIn('[LANGUAGE_STYLE]', prompt)
        self.assertIn('[LITERATURE_STYLE]', prompt)
        self.assertIn('AUTHOR_LIKE', prompt)
        self.assertIn('ANTI_PLAIN', prompt)
        self.assertIn('POLISHED', prompt)
        self.assertIn('ANTI_SHORT_SENTENCES', prompt)
        self.assertIn('从人物档案、关系和过往选择中', prompt)
        self.assertIn('傲娇与依恋', prompt)
        self.assertIn('每人通常挑三到五个能彼此作用的核心人设标签', prompt)
        self.assertIn('叙事职能、本场任务与具体动作进入后续场景资料', prompt)
        self.assertIn('让这一层比其余标签更鲜明', prompt)
        self.assertIn('人格和口头气质标签应当换一个场景仍然成立', prompt)
        self.assertIn('CADENCE_OWN_LITERARY_RHYTHM', prompt)
        self.assertIn('actor_tasks 给此人一个有生活感的起点', prompt)
        self.assertIn('概括此人面对人的口头气质', prompt)
        self.assertIn('先让玩笑者亲自演出，使后来的角色真能听见并误解', prompt)
        self.assertIn('若误称来自另一人的玩笑或暗示，先让玩笑者亲自演出', prompt)
        self.assertIn('cue 写清主要对话对象、可感的起因和关系压力', prompt)
        self.assertIn('从已知场地、人物和事件自然生长', prompt)
        self.assertIn('若一人的关键言行构成另一人回应的前因，先让前者获得自己的轮次', prompt)
        self.assertIn('此人主要面对谁、凭什么开口、关系压力何在', prompt)
        self.assertIn('不要把 PLAIN、SHORT、CLIPPED、COUNTED、ACCOUNTING、INVENTORY、MINIMAL', prompt)
        self.assertNotIn('ANTI_CONCISE', prompt)
        self.assertNotIn('TRAIT_内在性情', prompt)
        self.assertIn("actor_prompts", prompt)
        self.assertIn("actor_tasks", prompt)
        self.assertIn("environment_initialization", prompt)
        self.assertIn("opening_direction", prompt)
        self.assertIn("【SCENE_LOAD】", prompt)
        self.assertIn("[LITERATURE_STYLE]", prompt)
        self.assertIn("[NOW_TO_DO]", prompt)
        self.assertIn("ATTR_SENSORY_TRANSFORMATION", prompt)
        self.assertIn("ATTR_LYRICAL_VARIATION", prompt)
        self.assertIn("MOVEMENT_SYMBOLISM", prompt)
        self.assertIn("具体天气、光线、物件、地点、颜色、动作和某一场的意象放到后续场景资料里", prompt)
        self.assertNotIn("SENSE_ORDER_LIGHT_AIR_SOUND_TOUCH_SMELL", prompt)
        self.assertNotIn("ATTR_CINEMATIC_AND_RESTRAINED", prompt)
        self.assertIn("数量不限", prompt)
        self.assertNotIn("response_boundary", prompt)
        self.assertNotIn("speech_act", prompt)
        self.assertNotIn("voice_turn", prompt)

    def test_malformed_plan_reply_gets_one_clean_retry(self) -> None:
        calls = []
        valid = json.dumps(_plan(), ensure_ascii=False)

        def invoke(prompt: str, role: str) -> str:
            calls.append((prompt, role))
            return valid + ',"orphan":true' if len(calls) == 1 else valid

        result = _generate_performance_plan(_brief().to_dict(), {}, "", invoke)
        self.assertEqual(set(result["actor_prompts"]), set(_brief().participants))
        self.assertEqual(len(calls), 2)
        self.assertIn("完整 JSON 对象", calls[1][0])

    def test_actor_scene_prompt_keeps_one_identity_across_beats(self) -> None:
        beats = [_plan()["beats"][0], {**_plan()["beats"][0], "beat_id": "b2", "event": "妹妹走到门边"}]
        prompt = render_actor_scene_prompt(_brief().to_dict(), beats, {"speaker": "character/protagonist", "scene_task": "面对妹妹，最终交代信的去处", "stable_voice": {"rhythm": "越急越绕"}})
        self.assertIn("我从这一场的开头经历到结束", prompt)
        self.assertIn("最终交代信的去处", prompt)
        self.assertIn('"beat_id": "b2"', prompt)
        self.assertIn("同一时刻可有几项", prompt)
        self.assertNotIn("越急越绕", prompt)
        self.assertNotIn("personal_pressure", prompt)

    def test_environment_prompt_allows_uneven_free_observation(self) -> None:
        prompt = render_environment_prompt(_brief().to_dict(), _plan()["beats"], "", "")
        self.assertIn("沿用你的初始化方式", prompt)
        self.assertIn("自行选择值得停留的观察时刻、段落长短和语言节奏", prompt)
        self.assertIn("零至四段", prompt)

    def test_actor_relay_separates_actual_public_history_from_pending_plot(self) -> None:
        brief = _brief().to_dict()
        public_log = [{
            "speaker": "character/sister", "spoken": "信呢？", "first_person_action": "我站在门口。",
            "private_impulse": "绝不可进入公共日志",
        }]
        prompt = render_actor_scene_prompt(
            brief, _plan()["beats"], {"speaker": "character/protagonist"},
            public_log=public_log, pending_outcome="主人公承认自己拿走了信", max_entries=2,
        )
        self.assertIn("此前真正发生的公共言行", prompt)
        self.assertIn("信呢？", prompt)
        self.assertIn("本场尚未发生的情节结果", prompt)
        self.assertIn("选择试探、拒绝、设条件或暂时沉默", prompt)
        self.assertIn("抵达它的条件和路径由我在人物逻辑里寻找", prompt)
        self.assertNotIn("不要无限把同一推辞换个说法", prompt)
        self.assertIn("未知资料可以成为猜测", prompt)
        self.assertNotIn("本轮待兑现", prompt)
        self.assertIn("主人公承认自己拿走了信", prompt)
        self.assertIn("零至 2 项", prompt)
        self.assertNotIn("绝不可进入公共日志", prompt)
        self.assertNotIn("不自动成为已证实的世界事实", prompt)
        early_prompt = render_actor_scene_prompt(
            brief, _plan()["beats"], {"speaker": "character/protagonist"},
            public_log=[], knowledge_quotes=["信在昨夜被取走"],
            opening_situation="relationship-turn", max_entries=2,
        )
        self.assertIn('"opening_situation": "relationship-turn"', early_prompt)
        self.assertIn("unplayed_conflict_pressure", early_prompt)
        self.assertIn("信在昨夜被取走", early_prompt)
        self.assertNotIn("主人公承认自己拿走了信", early_prompt)
        self.assertNotIn("隐瞒转为承认", early_prompt)
        with self.assertRaisesRegex(ValueError, "speaker mismatch"):
            render_actor_scene_prompt(brief, _plan()["beats"], {"speaker": "character/protagonist"}, public_log=[{**public_log[0], "speaker": "outsider"}])
        with self.assertRaisesRegex(ValueError, "knowledge_quotes"):
            render_actor_scene_prompt(brief, _plan()["beats"], {"speaker": "character/protagonist"}, public_log=[], knowledge_quotes=["现场已经出现一把未经记录的钥匙"])
        with self.assertRaisesRegex(ValueError, "not grounded"):
            render_actor_scene_prompt(brief, _plan()["beats"], {"speaker": "character/protagonist"}, public_log=[], pending_outcome="妹妹在门外发现一把尚未出现的钥匙")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            render_actor_scene_prompt(brief, [_plan()["beats"][0], {"beat_id": "b2", "event": "妹妹走近"}], {"speaker": "character/protagonist"}, public_log=[])

    def test_environment_prompt_uses_scene_facts_without_prescribing_style(self) -> None:
        prompt = render_environment_prompt(_brief().to_dict(), _plan()["beats"], "参考语言起伏", "信在桌上", _plan()["unknown_slots"])
        self.assertIn("场景事实和线索以来源为准", prompt)
        self.assertIn("自行决定在哪些时刻写", prompt)
        self.assertNotIn("Main Creator's Scene-Specific Perception Boundary", prompt)
        self.assertIn("门外的具体天气尚未确认", prompt)
        self.assertIn("普通感官细节可以自由选择", prompt)
        extended = {"scene_id": _brief().scene_id, "passages": [{
            "beat_id": _plan()["beats"][0]["beat_id"], "focal_character": "", "description": "风" * 500,
        }]}
        self.assertEqual(len(parse_environment_material(extended, _brief().to_dict(), _plan()["beats"])["passages"]), 1)
        extended["passages"][0]["description"] = "风" * 601
        with self.assertRaisesRegex(ValueError, "too long"):
            parse_environment_material(extended, _brief().to_dict(), _plan()["beats"])
        self.assertNotIn("150—300", prompt)

    def test_relay_environment_sees_only_actual_public_interaction(self) -> None:
        brief = _brief().to_dict()
        public_log = [{
            "speaker": "character/sister", "spoken": "信呢？", "first_person_action": "我站在门口。",
            "private_impulse": "我害怕他会继续说谎。",
        }]
        prompt = render_environment_prompt(
            brief, _plan()["beats"], "参考语言起伏", "信在桌上", [], public_log=public_log,
        )
        self.assertIn("信呢？", prompt)
        self.assertIn("场景事实和线索以来源为准", prompt)
        self.assertNotIn("我害怕他会继续说谎", prompt)
        self.assertNotIn('"objective"', prompt)
        default_prompt = render_environment_prompt(brief, _plan()["beats"], "参考语言起伏", "信在桌上")
        self.assertIn('"objective"', default_prompt)

    def test_relay_materials_keep_chronology_and_reject_unmet_outcome(self) -> None:
        plan = parse_relay_plan(_relay_plan(), _brief().to_dict())
        entries = [
            {"entry_id": "t1:1", "speaker": "character/sister", "spoken": "信呢？", "first_person_action": "", "private_impulse": "我等他回答。"},
            {"entry_id": "t2:1", "speaker": "character/protagonist", "spoken": "信是我拿的。", "first_person_action": "", "private_impulse": "我说了。"},
        ]
        check = parse_relay_scene_check({"scene_id": "scene_0001", "results": [{
            "milestone_id": "m1", "status": "fulfilled", "evidence_entry_ids": ["t2:1"],
        }]}, plan, entries)
        block = render_relay_materials(plan, entries, None, check)
        self.assertIn("按真实互动时间顺序", block)
        self.assertIn("你可改写已有台词的具体措辞和语势", block)
        self.assertIn("可化为当前视角的自由间接感知", block)
        self.assertIn("private_impulse 是未出口的体验候选", block)
        self.assertIn("普通现场细节可以择用", block)
        self.assertLess(block.index('"entry_id":"t1:1"'), block.index('"entry_id":"t2:1"'))
        focal_block = render_relay_materials(plan, entries, None, check, viewpoint="character/sister")
        focal_entries = json.loads(focal_block.split("\n", 1)[1])["actor_entries"]
        self.assertEqual(focal_entries[0]["private_impulse"], "我等他回答。")
        self.assertEqual(focal_entries[1]["private_impulse"], "")
        self.assertEqual(focal_entries[1]["spoken"], "信是我拿的。")
        self.assertEqual(entries[1]["private_impulse"], "我说了。")
        incomplete = {**check, "results": [{"milestone_id": "m1", "status": "missing", "evidence_entry_ids": []}]}
        with self.assertRaisesRegex(ValueError, "incomplete scene outcomes"):
            render_relay_materials(plan, entries, None, incomplete)

    def test_batch_materials_hide_other_characters_private_impulses(self) -> None:
        actors = [
            {"speaker": "character/sister", "entries": [{"spoken": "信呢？", "private_impulse": "我怕他撒谎。"}]},
            {"speaker": "character/protagonist", "entries": [{"spoken": "信是我拿的。", "private_impulse": "我想逃。"}]},
        ]
        block = render_performance_materials(_plan(), actors, None, viewpoint="character/sister")
        visible = json.loads(block.split("\n", 1)[1])["actor_candidates"]
        self.assertEqual(visible[0]["entries"][0]["private_impulse"], "我怕他撒谎。")
        self.assertEqual(visible[1]["entries"][0]["private_impulse"], "")
        self.assertEqual(actors[1]["entries"][0]["private_impulse"], "我想逃。")

    def test_plan_requires_character_tasks_without_environment_micro_task(self) -> None:
        plan = _plan()
        plan["actor_tasks"] = [{"speaker": "character/protagonist"}]
        with self.assertRaisesRegex(ValueError, "actor_tasks must cover"):
            parse_performance_plan(plan, _brief().to_dict())
        plan = _plan()
        plan["environment_task"] = {"focus_beats": ["b1"]}
        with self.assertRaisesRegex(ValueError, "must not assign"):
            parse_performance_plan(plan, _brief().to_dict())

    def test_environment_initialization_uses_six_sections_with_free_tag_counts(self) -> None:
        plan = _plan()
        plan["environment_initialization"] = plan["environment_initialization"].replace(
            "STYLE_CHARACTER_DRIVEN", "\n".join(f"AUTHOR_LIKE_{index}" for index in range(30)),
        ).replace("ATTR_PERSPECTIVE_LOCKED", "")
        self.assertIn("AUTHOR_LIKE_29", parse_performance_plan(plan, _brief().to_dict())["environment_initialization"])
        missing = _plan()
        del missing["environment_initialization"]
        with self.assertRaisesRegex(ValueError, "environment_initialization"):
            parse_performance_plan(missing, _brief().to_dict())
        invalid = _plan()
        invalid["environment_initialization"] = invalid["environment_initialization"].replace("[SCENE_CORE]", "[SCENE_FOCUS]")
        with self.assertRaisesRegex(ValueError, "six scene sections"):
            parse_performance_plan(invalid, _brief().to_dict())

    def test_unknown_slots_are_factual_gaps_not_micro_direction(self) -> None:
        plan = parse_performance_plan(_plan(), _brief().to_dict())
        self.assertEqual(plan["unknown_slots"], ["门外的具体天气尚未确认"])
        self.assertEqual(set(plan["actor_prompts"]), set(_brief().participants))
        self.assertEqual(set(plan["actor_tasks"]), set(_brief().participants))
        prompt = render_actor_scene_prompt(_brief().to_dict(), _plan()["beats"], {"speaker": "character/protagonist"}, plan["unknown_slots"])
        self.assertIn("门外的具体天气尚未确认", prompt)
        self.assertIn("自行选择何时说话", prompt)
        self.assertIn("unknown_slots", render_performance_plan_prompt(_brief().to_dict(), {}, ""))
        for malformed in (None, ["重复空位", "重复空位"], [1]):
            payload = _plan()
            payload["unknown_slots"] = malformed
            with self.subTest(malformed=malformed), self.assertRaisesRegex(ValueError, "unknown_slots"):
                parse_performance_plan(payload, _brief().to_dict())
        many = _plan()
        many["unknown_slots"] = [f"未确认事实 {index}" for index in range(9)]
        self.assertEqual(len(parse_performance_plan(many, _brief().to_dict())["unknown_slots"]), 9)

    def test_actor_scene_allows_self_chosen_entries_and_silence(self) -> None:
        beats = [_plan()["beats"][0], {**_plan()["beats"][0], "beat_id": "b2"}]
        first = {"beat_id": "b1", "spoken": "是我。", "first_person_action": "我站住。", "private_impulse": "我怕。"}
        second = {**first, "beat_id": "b2", "spoken": "你听我说。"}
        target = {"scene_id": "scene_0001", "speaker": "character/protagonist"}
        result = parse_actor_scene_material({**target, "entries": [first, second]}, _brief().to_dict(), beats)
        self.assertEqual([item["beat_id"] for item in result["entries"]], ["b1", "b2"])
        self.assertEqual(result["entries"][0]["entry_id"], "character/protagonist:1")
        self.assertEqual(parse_actor_scene_material({**target, "entries": []}, _brief().to_dict(), beats)["entries"], [])
        expansive = {**first, "spoken": "我还没说完。" * 110,
                     "first_person_action": "我绕着树根走，边走边看。" * 35,
                     "private_impulse": "我终于想起很久以前离开这里的原因。" * 25}
        self.assertEqual(
            parse_actor_scene_material({**target, "entries": [expansive]}, _brief().to_dict(), beats)["entries"][0]["private_impulse"],
            expansive["private_impulse"],
        )
        self.assertEqual(len(parse_actor_scene_material({**target, "entries": [first, first]}, _brief().to_dict(), beats)["entries"]), 2)
        with self.assertRaisesRegex(ValueError, "target mismatch"):
            parse_actor_scene_material({**target, "speaker": "character/sister", "entries": [first, second]}, _brief().to_dict(), beats, "character/protagonist")
        with self.assertRaisesRegex(ValueError, "follow known beats"):
            parse_actor_scene_material({**target, "entries": [second, first]}, _brief().to_dict(), beats)
        with self.assertRaisesRegex(ValueError, "bounded list"):
            parse_actor_scene_material({**target, "entries": [first, second]}, _brief().to_dict(), beats, max_entries=1)

    def test_scene_performance_is_on_by_default_but_saved_opt_out_wins(self) -> None:
        self.assertEqual(default_config()["application"]["scene_performance_agents"], {"enabled": True, "max_actor_calls": 12})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"application":{"max_workers":3}}', encoding="utf-8")
            self.assertTrue(load_config(path)["application"]["scene_performance_agents"]["enabled"])
            path.write_text('{"application":{"scene_performance_agents":{"enabled":false}}}', encoding="utf-8")
            self.assertFalse(load_config(path)["application"]["scene_performance_agents"]["enabled"])

    def test_malformed_saved_limit_is_clamped_without_breaking_settings(self) -> None:
        self.assertEqual(get_scene_performance_preferences({"application": {"scene_performance_agents": {"enabled": True, "max_actor_calls": "bad"}}}), {"enabled": True, "max_actor_calls": 12})
        self.assertEqual(get_scene_performance_preferences({"application": {"scene_performance_agents": {"enabled": True, "max_actor_calls": 99}}}), {"enabled": True, "max_actor_calls": 12})

    def test_material_block_has_a_hard_prompt_budget(self) -> None:
        with self.assertRaisesRegex(ValueError, "prompt budget"):
            render_performance_materials(_plan(), [], {"passages": [{"description": "雨" * 16_000}]})

    def test_plan_rejects_director_preassigning_speaker(self) -> None:
        payload = _plan()
        payload["beats"][0]["speaker"] = "character/outsider"
        with self.assertRaisesRegex(ValueError, "must not script"):
            parse_performance_plan(payload, _brief().to_dict())

    def test_actor_and_environment_reject_wrong_targets(self) -> None:
        beat = {**_plan()["beats"][0], "speaker": "character/protagonist"}
        with self.assertRaisesRegex(ValueError, "target mismatch"):
            parse_actor_material({"beat_id": "b2", "speaker": beat["speaker"], "candidates": []}, beat)
        with self.assertRaisesRegex(ValueError, "dialogue/action"):
            parse_actor_material({"beat_id": "b1", "speaker": beat["speaker"], "candidates": [{"spoken": "", "visible_action": "他点头。"}]}, beat)
        self.assertEqual(parse_actor_material({"beat_id": "b1", "speaker": beat["speaker"], "candidates": [{"spoken": "我知道。", "first_person_action": ""}]}, beat)["candidates"][0]["first_person_action"], "")
        self.assertEqual(parse_actor_material({"beat_id": "b1", "speaker": beat["speaker"], "candidates": [{"spoken": "", "first_person_action": "我站住。"}]}, beat)["candidates"][0]["spoken"], "")
        with self.assertRaisesRegex(ValueError, "unknown beat"):
            parse_environment_material({"scene_id": "scene_0001", "passages": [{"beat_id": "b9", "description": "雨。"}]}, _brief().to_dict(), [beat])
        with self.assertRaisesRegex(ValueError, "contains dialogue"):
            parse_environment_material({"scene_id": "scene_0001", "passages": [{"beat_id": "b1", "description": "门外的雨落着。她说：“别走。”"}]}, _brief().to_dict(), [beat])
        self.assertEqual(
            parse_environment_material({"scene_id": "scene_0001", "passages": [{"beat_id": "b1", "description": "价目表上只剩“包”和“粥”两个字。"}]}, _brief().to_dict(), [beat])["passages"][0]["description"],
            "价目表上只剩“包”和“粥”两个字。",
        )
        with self.assertRaisesRegex(ValueError, "outside scene participants"):
            parse_environment_material({"scene_id": "scene_0001", "passages": [{"beat_id": "b1", "focal_character": "character/outsider", "description": "门外下雨。"}]}, _brief().to_dict(), [beat])
        self.assertEqual(parse_environment_material({"scene_id": "scene_0001", "passages": []}, _brief().to_dict(), [beat])["passages"], [])

    def test_actor_capacity_falls_back_without_partial_cast_or_extra_call(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            gateway = _PerformanceGateway()
            events = []
            materials = scene_performance_materials(
                brief=_brief().to_dict(), expression={}, sources="", style_reference="",
                cache_root=Path(temporary) / "cache",
                config={"application": {"scene_performance_agents": {"enabled": True, "max_actor_calls": 1}}},
                invoke=lambda prompt, role: gateway.run(Path(temporary), prompt, role=role, timeout=30).answer,
                emit=lambda event, data: events.append((event, data)),
            )
            self.assertEqual(materials, "")
            self.assertEqual(gateway.calls, [])
            self.assertEqual(events[0][1]["stage"], "actor-capacity")

    def test_default_capacity_attempts_five_character_rehearsal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            brief = {**_brief().to_dict(), "participants": [f"character/{index}" for index in range(5)]}
            calls = []
            events = []
            materials = scene_performance_materials(
                brief=brief, expression={}, sources="", style_reference="",
                cache_root=Path(temporary) / "cache",
                config={"application": {"scene_performance_agents": {"enabled": True}}},
                invoke=lambda prompt, role: calls.append(role) or "{}",
                emit=lambda event, data: events.append((event, data)),
            )
            self.assertEqual(materials, "")
            self.assertEqual(calls, ["worker", "worker"])
            self.assertEqual(events[-1][1]["stage"], "plan")

    def test_invalid_director_plan_falls_back_to_single_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gateway = _PerformanceGateway(bad_plan=True)
            events = []
            runtime = PiSceneTransactionRuntime(
                {"application": {"scene_performance_agents": {"enabled": True}}},
                project_root=root, data_root=root / ".studio", gateway=gateway,
                event_sink=lambda event, data: events.append(event),
            )
            runtime.create_scene("performance-fallback", _brief())
            self.assertEqual([role for role, _ in gateway.calls[:2]], ["worker", "worker"])
            self.assertNotIn("Character And Environment Candidate Materials", gateway.calls[1][1])
            self.assertIn("scene.performance.fallback", events)


if __name__ == "__main__":
    unittest.main()
