from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.runtime.role_conversation import RoleConversationResult
from literary_engineering_studio.application.config import default_config
from literary_engineering_studio.application.scene_performance_preferences import get_scene_performance_preferences
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio.runtimes.scene_performance import scene_performance_materials
from literary_engineering_studio_engine.public.literary import (
    parse_actor_material,
    parse_actor_scene_material,
    parse_environment_material,
    parse_performance_plan,
    parse_relay_plan,
    parse_relay_scene_check,
    render_actor_prompt,
    render_actor_scene_prompt,
    render_environment_prompt,
    render_performance_plan_prompt,
    render_relay_plan_prompt,
    render_relay_scene_check_prompt,
    render_performance_materials,
)
from tests.test_lean_kernel_v2_pi_runtime import _Gateway, _brief


def _plan() -> dict[str, object]:
    return {
        "scene_id": "scene_0001",
        "beats": [{
            "beat_id": "b1", "event": "妹妹已经发现抽屉被打开；信在昨夜被取走",
        }],
        "unknown_slots": ["门外的具体天气尚未确认"],
    }


def _relay_plan() -> dict[str, object]:
    return {
        "scene_id": "scene_0001",
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
            self.calls.append((role, prompt))
            protagonist = "# 我在场：character/protagonist" in prompt
            answer = json.dumps({
                "scene_id": "scene_0001", "speaker": "character/protagonist" if protagonist else "character/sister",
                "entries": ([
                    {"beat_id": "b1", "spoken": "信是我拿的。你先别把门关上。", "first_person_action": "我把信留在桌沿，没有推向她。", "private_impulse": "我怕她现在就走。"},
                    *([{"beat_id": "b2", "spoken": "你不想听，我就等你。", "first_person_action": "我收回伸向信的手。", "private_impulse": "我不能逼她听完。"}] if self.repeat_actor else []),
                ] if protagonist else [
                    {"beat_id": "b1", "spoken": "门我没关。信呢？", "first_person_action": "我站在门口。", "private_impulse": "我要听他亲口承认。"},
                ]),
            }, ensure_ascii=False)
        elif role == "environment-writer":
            self.calls.append((role, prompt))
            answer = json.dumps({
                "scene_id": "scene_0001",
                "passages": [{"beat_id": "b1", "focal_character": "", "description": "门缝里的光落在桌沿，信纸的边缘仍在阴影里。", "scene_function": "让人物之间的距离可见"}],
            }, ensure_ascii=False)
        else:
            return super().run(workspace, prompt, role=role, timeout=timeout, event_sink=event_sink, cancel_event=cancel_event)
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
        self.assertIn("不指定台词、句式、情绪、手势", prompt)
        self.assertIn("incoming_handoff", prompt)
        plan = parse_relay_plan(_relay_plan(), brief)
        self.assertEqual(plan["schema"], "arcvellum/scene-relay-plan/v1")
        self.assertEqual(plan["milestones"][0]["milestone_id"], "m1")
        self.assertEqual(plan["actor_knowledge"][1]["quotes"], ["妹妹已经发现抽屉被打开"])
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

    def test_actor_task_is_first_person_and_uses_character_voice(self) -> None:
        voice = {
            "speaker": "姐姐", "role": "档案员", "belief": "承认比辩解有用",
            "wants": "留住妹妹", "avoids": "承认自己害怕被抛下",
            "stable_voice": {"rhythm": "平时长句绕开请求，着急时说‘你先别走。’", "signature_patterns": ["你先别走。"]},
            "voice_state": {"interlocutors": ["妹妹"], "known_facts": ["昨夜拿了信"]},
        }
        prompt = render_actor_prompt(_brief().to_dict(), _plan()["beats"][0], voice)
        self.assertIn("我从第一个时刻一直活到最后一个时刻", prompt)
        self.assertIn("平时长句绕开请求", prompt)
        self.assertIn("我平时的说话倾向", prompt)
        self.assertIn("不是要照念的台词", prompt)
        self.assertIn("first_person_action", prompt)
        self.assertIn("private_impulse", prompt)
        self.assertNotIn("subtext_effect", prompt)
        self.assertNotIn("你先别走。", prompt)
        self.assertIn("我自行决定何时开口、岔开、反问、沉默", prompt)
        self.assertNotIn("speech_act", prompt)
        self.assertIn("同一锚点可有多项", prompt)

    def test_director_leaves_micro_tactics_to_character_actor(self) -> None:
        prompt = render_performance_plan_prompt(_brief().to_dict(), {}, "昨夜拿了信。")
        self.assertIn("导演没有替我", render_actor_scene_prompt(_brief().to_dict(), _plan()["beats"], {"speaker": "character/protagonist"}))
        self.assertIn("不要指定谁说话、说什么", prompt)
        self.assertIn("角色可以自行选择", prompt)
        self.assertNotIn("response_boundary", prompt)
        self.assertNotIn("speech_act", prompt)
        self.assertNotIn("voice_turn", prompt)
        self.assertIn("不要二次改写成 actor_tasks 或 environment_task", prompt)

    def test_actor_scene_prompt_keeps_one_identity_across_beats(self) -> None:
        beats = [_plan()["beats"][0], {**_plan()["beats"][0], "beat_id": "b2", "event": "妹妹走到门边"}]
        prompt = render_actor_scene_prompt(_brief().to_dict(), beats, {"speaker": "character/protagonist", "stable_voice": {"vocabulary": "总用家里的旧称呼", "rhythm": "越急越绕"}})
        self.assertIn("我从第一个时刻一直活到最后一个时刻", prompt)
        self.assertIn("不必每拍制造手势或职业解释", prompt)
        self.assertIn("越急越绕", prompt)
        self.assertIn('"beat_id": "b2"', prompt)
        self.assertIn("同一锚点可有多项", prompt)
        self.assertIn("此刻可偏离", prompt)
        self.assertNotIn("personal_pressure", prompt)

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
        self.assertIn("本场尚未发生的情节边界（不是本轮交付指令）", prompt)
        self.assertIn("可以回避、拒绝、设条件或暂时沉默", prompt)
        self.assertIn("我可以试探、说谎、误记或猜测", prompt)
        self.assertNotIn("本轮待兑现", prompt)
        self.assertIn("主人公承认自己拿走了信", prompt)
        self.assertIn("零至 2 项", prompt)
        self.assertNotIn("绝不可进入公共日志", prompt)
        self.assertIn("不自动成为已证实的世界事实", prompt)
        early_prompt = render_actor_scene_prompt(
            brief, _plan()["beats"], {"speaker": "character/protagonist"},
            public_log=[], knowledge_quotes=["信在昨夜被取走"], max_entries=2,
        )
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
        self.assertIn("主创只给你视角与事实边界", prompt)
        self.assertIn("自行挑真正需要环境语言的位置", prompt)
        self.assertNotIn("Main Creator's Scene-Specific Perception Boundary", prompt)
        self.assertIn("门外的具体天气尚未确认", prompt)
        self.assertIn("普通、不承担证据作用的感官质感仍由你自由选择", prompt)
        self.assertIn("长短由场景决定", prompt)
        self.assertNotIn("150—300", prompt)

    def test_plan_rejects_director_owned_micro_tasks(self) -> None:
        plan = _plan()
        plan["actor_tasks"] = [{"speaker": "character/protagonist"}]
        with self.assertRaisesRegex(ValueError, "must not assign"):
            parse_performance_plan(plan, _brief().to_dict())
        plan = _plan()
        plan["environment_task"] = {"focus_beats": ["b1"]}
        with self.assertRaisesRegex(ValueError, "must not assign"):
            parse_performance_plan(plan, _brief().to_dict())

    def test_unknown_slots_are_factual_gaps_not_micro_direction(self) -> None:
        plan = parse_performance_plan(_plan(), _brief().to_dict())
        self.assertEqual(plan["unknown_slots"], ["门外的具体天气尚未确认"])
        prompt = render_actor_scene_prompt(_brief().to_dict(), _plan()["beats"], {"speaker": "character/protagonist"}, plan["unknown_slots"])
        self.assertIn("门外的具体天气尚未确认", prompt)
        self.assertIn("即时反应由我自己决定", prompt)
        self.assertIn("unknown_slots", render_performance_plan_prompt(_brief().to_dict(), {}, ""))
        for malformed in (None, ["重复空位", "重复空位"], ["空位"] * 9, [1]):
            payload = _plan()
            payload["unknown_slots"] = malformed
            with self.subTest(malformed=malformed), self.assertRaisesRegex(ValueError, "unknown_slots"):
                parse_performance_plan(payload, _brief().to_dict())

    def test_actor_scene_allows_self_chosen_entries_and_silence(self) -> None:
        beats = [_plan()["beats"][0], {**_plan()["beats"][0], "beat_id": "b2"}]
        first = {"beat_id": "b1", "spoken": "是我。", "first_person_action": "我站住。", "private_impulse": "我怕。"}
        second = {**first, "beat_id": "b2", "spoken": "你听我说。"}
        target = {"scene_id": "scene_0001", "speaker": "character/protagonist"}
        result = parse_actor_scene_material({**target, "entries": [first, second]}, _brief().to_dict(), beats)
        self.assertEqual([item["beat_id"] for item in result["entries"]], ["b1", "b2"])
        self.assertEqual(result["entries"][0]["entry_id"], "character/protagonist:1")
        self.assertEqual(parse_actor_scene_material({**target, "entries": []}, _brief().to_dict(), beats)["entries"], [])
        self.assertEqual(len(parse_actor_scene_material({**target, "entries": [first, first]}, _brief().to_dict(), beats)["entries"]), 2)
        with self.assertRaisesRegex(ValueError, "target mismatch"):
            parse_actor_scene_material({**target, "speaker": "character/sister", "entries": [first, second]}, _brief().to_dict(), beats, "character/protagonist")
        with self.assertRaisesRegex(ValueError, "follow known beats"):
            parse_actor_scene_material({**target, "entries": [second, first]}, _brief().to_dict(), beats)
        with self.assertRaisesRegex(ValueError, "bounded list"):
            parse_actor_scene_material({**target, "entries": [first, second]}, _brief().to_dict(), beats, max_entries=1)

    def test_experimental_feature_is_opt_in(self) -> None:
        self.assertEqual(default_config()["application"]["scene_performance_agents"], {"enabled": False, "max_actor_calls": 4})

    def test_malformed_saved_limit_is_clamped_without_breaking_settings(self) -> None:
        self.assertEqual(get_scene_performance_preferences({"application": {"scene_performance_agents": {"enabled": True, "max_actor_calls": "bad"}}}), {"enabled": True, "max_actor_calls": 4})
        self.assertEqual(get_scene_performance_preferences({"application": {"scene_performance_agents": {"enabled": True, "max_actor_calls": 99}}}), {"enabled": True, "max_actor_calls": 4})

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

    def test_runtime_invokes_independent_agents_then_main_writer_and_caches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gateway = _PerformanceGateway()
            events = []
            runtime = PiSceneTransactionRuntime(
                {"application": {"scene_performance_agents": {"enabled": True, "max_actor_calls": 4}}},
                project_root=root, data_root=root / ".studio", gateway=gateway,
                event_sink=lambda event, data: events.append(event),
            )
            first = runtime.create_scene("performance-tx", _brief())
            second = runtime.create_scene("performance-tx", _brief())
            roles = [role for role, _ in gateway.calls]
            self.assertEqual(roles[:5], ["worker", "character-actor", "character-actor", "environment-writer", "worker"])
            for role, prompt in gateway.calls[1:4]:
                self.assertIn("门外的具体天气尚未确认", prompt, role)
            self.assertIn("Character And Environment Candidate Materials", gateway.calls[4][1])
            self.assertIn("信是我拿的", gateway.calls[4][1])
            self.assertIn("门我没关", gateway.calls[4][1])
            self.assertIn("我把信留在桌沿", gateway.calls[4][1])
            self.assertIn("门缝里的光", gateway.calls[4][1])
            self.assertIn("不把各人声音润平成中性解释", gateway.calls[4][1])
            self.assertIn("可保留它的观察次序和句群呼吸", gateway.calls[4][1])
            self.assertEqual(first, second)
            self.assertEqual(runtime.metrics.cache_hits, 1)
            self.assertIn("scene.performance.actor", events)
            self.assertIn("scene.performance.environment", events)

    def test_runtime_calls_repeating_character_once_for_whole_scene(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gateway = _PerformanceGateway(repeat_actor=True)
            runtime = PiSceneTransactionRuntime(
                {"application": {"scene_performance_agents": {"enabled": True, "max_actor_calls": 2}}},
                project_root=root, data_root=root / ".studio", gateway=gateway,
            )
            runtime.create_scene("performance-grouped", _brief())
            self.assertEqual([role for role, _ in gateway.calls[:5]], ["worker", "character-actor", "character-actor", "environment-writer", "worker"])
            self.assertEqual(sum(role == "character-actor" for role, _ in gateway.calls), 2)
            self.assertIn("你不想听，我就等你。", gateway.calls[4][1])

    def test_grouped_actor_material_is_reused_from_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gateway = _PerformanceGateway(repeat_actor=True)
            settings = {"application": {"scene_performance_agents": {"enabled": True, "max_actor_calls": 2}}}
            def invoke(prompt: str, role: str) -> str:
                return gateway.run(root, prompt, role=role, timeout=30).answer
            kwargs = {
                "brief": _brief().to_dict(), "expression": {}, "sources": "", "style_reference": "",
                "cache_root": root / "cache", "config": settings, "invoke": invoke,
            }
            first = scene_performance_materials(**kwargs)
            second = scene_performance_materials(**kwargs)
            self.assertEqual(first, second)
            self.assertEqual([role for role, _ in gateway.calls], ["worker", "character-actor", "character-actor", "environment-writer"])

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
