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
    render_actor_prompt,
    render_actor_scene_prompt,
    render_performance_plan_prompt,
    render_performance_materials,
)
from tests.test_lean_kernel_v2_pi_runtime import _Gateway, _brief


def _plan() -> dict[str, object]:
    return {
        "scene_id": "scene_0001",
        "beats": [{
            "beat_id": "b1", "event": "妹妹发现抽屉被打开后，主人公承认取信",
            "speaker": "character/protagonist", "speech_act": "承认昨夜取走信，同时试探妹妹是否信他",
            "information": "承认取信，不声称妹妹已经原谅", "action_boundary": "可把信放在桌上",
            "response_boundary": "妹妹的反应留给主创", "environment_need": "门口与桌面的距离制造迟疑",
        }],
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
                plan["beats"][0]["speaker"] = "character/outsider"
            if self.repeat_actor:
                plan["beats"].append({
                    **plan["beats"][0], "beat_id": "b2",
                    "event": "妹妹停在门边，主人公又试着把话说完",
                })
            answer = json.dumps(plan, ensure_ascii=False)
        elif role == "character-actor":
            self.calls.append((role, prompt))
            answer = json.dumps({
                "scene_id": "scene_0001", "speaker": "character/protagonist",
                "performances": [
                    {"beat_id": "b1", "spoken": "信是我拿的。你先别把门关上。", "first_person_action": "我把信留在桌沿，没有推向她。", "private_impulse": "我怕她现在就走。"},
                    *([{"beat_id": "b2", "spoken": "你不想听，我就等你。", "first_person_action": "我收回伸向信的手。", "private_impulse": "我不能逼她听完。"}] if self.repeat_actor else []),
                ],
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
    def test_actor_task_is_first_person_and_uses_character_voice(self) -> None:
        voice = {
            "speaker": "姐姐", "role": "档案员", "belief": "承认比辩解有用",
            "wants": "留住妹妹", "avoids": "承认自己害怕被抛下",
            "stable_voice": {"rhythm": "平时长句绕开请求，着急时说‘你先别走。’", "signature_patterns": ["你先别走。"]},
            "voice_state": {"interlocutors": ["妹妹"], "known_facts": ["昨夜拿了信"]},
        }
        prompt = render_actor_prompt(_brief().to_dict(), _plan()["beats"][0], voice)
        self.assertIn("从现在起，我就是这个人", prompt)
        self.assertIn("平时长句绕开请求", prompt)
        self.assertIn("我的稳定说话方式", prompt)
        self.assertIn("我不知道导演的台词计划", prompt)
        self.assertIn("first_person_action", prompt)
        self.assertIn("private_impulse", prompt)
        self.assertNotIn("subtext_effect", prompt)
        self.assertNotIn("你先别走。", prompt)
        self.assertIn("此刻怎样争取、回避、还口或沉默", prompt)
        self.assertNotIn("承认昨夜取走信，同时试探妹妹是否信他", prompt)
        self.assertNotIn("承认取信，不声称妹妹已经原谅", prompt)

    def test_director_leaves_micro_tactics_to_character_actor(self) -> None:
        prompt = render_performance_plan_prompt(_brief().to_dict(), {}, "昨夜拿了信。")
        self.assertIn("互动目标与压力", prompt)
        self.assertIn("由扮演该人物的演员自行选择", prompt)
        self.assertIn("不是整场解释清单", prompt)

    def test_actor_scene_prompt_keeps_one_identity_across_beats(self) -> None:
        beats = [_plan()["beats"][0], {**_plan()["beats"][0], "beat_id": "b2", "event": "妹妹走到门边"}]
        prompt = render_actor_scene_prompt(_brief().to_dict(), beats, {"stable_voice": {"vocabulary": "总用家里的旧称呼", "rhythm": "越急越绕"}})
        self.assertIn("从第一个节拍一直活到最后一个节拍", prompt)
        self.assertIn("我的语言，优先于顺口的中性答案", prompt)
        self.assertIn("越急越绕", prompt)
        self.assertIn('"beat_id": "b2"', prompt)
        self.assertIn("每拍恰好一项", prompt)

    def test_actor_scene_requires_all_assigned_beats_in_order(self) -> None:
        beats = [_plan()["beats"][0], {**_plan()["beats"][0], "beat_id": "b2"}]
        first = {"beat_id": "b1", "spoken": "是我。", "first_person_action": "我站住。", "private_impulse": "我怕。"}
        second = {**first, "beat_id": "b2", "spoken": "你听我说。"}
        target = {"scene_id": "scene_0001", "speaker": "character/protagonist"}
        result = parse_actor_scene_material({**target, "performances": [first, second]}, _brief().to_dict(), beats)
        self.assertEqual([item["beat_id"] for item in result], ["b1", "b2"])
        with self.assertRaisesRegex(ValueError, "every assigned beat"):
            parse_actor_scene_material({**target, "performances": [first]}, _brief().to_dict(), beats)
        with self.assertRaisesRegex(ValueError, "target mismatch"):
            parse_actor_scene_material({**target, "speaker": "character/sister", "performances": [first, second]}, _brief().to_dict(), beats)
        with self.assertRaisesRegex(ValueError, "target mismatch"):
            parse_actor_scene_material({**target, "performances": [second, first]}, _brief().to_dict(), beats)

    def test_experimental_feature_is_opt_in(self) -> None:
        self.assertEqual(default_config()["application"]["scene_performance_agents"], {"enabled": False, "max_actor_calls": 4})

    def test_malformed_saved_limit_is_clamped_without_breaking_settings(self) -> None:
        self.assertEqual(get_scene_performance_preferences({"application": {"scene_performance_agents": {"enabled": True, "max_actor_calls": "bad"}}}), {"enabled": True, "max_actor_calls": 4})
        self.assertEqual(get_scene_performance_preferences({"application": {"scene_performance_agents": {"enabled": True, "max_actor_calls": 99}}}), {"enabled": True, "max_actor_calls": 4})

    def test_material_block_has_a_hard_prompt_budget(self) -> None:
        with self.assertRaisesRegex(ValueError, "prompt budget"):
            render_performance_materials(_plan(), [], {"passages": [{"description": "雨" * 16_000}]})

    def test_plan_rejects_unplanned_speaker(self) -> None:
        payload = _plan()
        payload["beats"][0]["speaker"] = "character/outsider"
        with self.assertRaisesRegex(ValueError, "outside scene participants"):
            parse_performance_plan(payload, _brief().to_dict())

    def test_actor_and_environment_reject_wrong_targets(self) -> None:
        beat = _plan()["beats"][0]
        with self.assertRaisesRegex(ValueError, "target mismatch"):
            parse_actor_material({"beat_id": "b2", "speaker": beat["speaker"], "candidates": []}, beat)
        with self.assertRaisesRegex(ValueError, "dialogue/action"):
            parse_actor_material({"beat_id": "b1", "speaker": beat["speaker"], "candidates": [{"spoken": "我知道。", "visible_action": "他点头。"}]}, beat)
        with self.assertRaisesRegex(ValueError, "unknown beat"):
            parse_environment_material({"scene_id": "scene_0001", "passages": [{"beat_id": "b9", "description": "雨。"}]}, _brief().to_dict(), [beat])
        with self.assertRaisesRegex(ValueError, "contains dialogue"):
            parse_environment_material({"scene_id": "scene_0001", "passages": [{"beat_id": "b1", "description": "门外的雨落着。她说：“别走。”"}]}, _brief().to_dict(), [beat])
        with self.assertRaisesRegex(ValueError, "outside scene participants"):
            parse_environment_material({"scene_id": "scene_0001", "passages": [{"beat_id": "b1", "focal_character": "character/outsider", "description": "门外下雨。"}]}, _brief().to_dict(), [beat])

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
            self.assertEqual(roles[:4], ["worker", "character-actor", "environment-writer", "worker"])
            self.assertIn("Character And Environment Candidate Materials", gateway.calls[3][1])
            self.assertIn("信是我拿的", gateway.calls[3][1])
            self.assertIn("我把信留在桌沿", gateway.calls[3][1])
            self.assertIn("门缝里的光", gateway.calls[3][1])
            self.assertIn("不要在组织正文时把各人的声音统一润平", gateway.calls[3][1])
            self.assertEqual(first, second)
            self.assertEqual(runtime.metrics.cache_hits, 1)
            self.assertIn("scene.performance.actor", events)
            self.assertIn("scene.performance.environment", events)

    def test_runtime_calls_repeating_character_once_for_whole_scene(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gateway = _PerformanceGateway(repeat_actor=True)
            runtime = PiSceneTransactionRuntime(
                {"application": {"scene_performance_agents": {"enabled": True, "max_actor_calls": 1}}},
                project_root=root, data_root=root / ".studio", gateway=gateway,
            )
            runtime.create_scene("performance-grouped", _brief())
            self.assertEqual([role for role, _ in gateway.calls[:4]], ["worker", "character-actor", "environment-writer", "worker"])
            self.assertEqual(sum(role == "character-actor" for role, _ in gateway.calls), 1)
            self.assertIn("你不想听，我就等你。", gateway.calls[3][1])

    def test_grouped_actor_material_is_reused_from_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gateway = _PerformanceGateway(repeat_actor=True)
            settings = {"application": {"scene_performance_agents": {"enabled": True, "max_actor_calls": 1}}}
            def invoke(prompt: str, role: str) -> str:
                return gateway.run(root, prompt, role=role, timeout=30).answer
            kwargs = {
                "brief": _brief().to_dict(), "expression": {}, "sources": "", "style_reference": "",
                "cache_root": root / "cache", "config": settings, "invoke": invoke,
            }
            first = scene_performance_materials(**kwargs)
            second = scene_performance_materials(**kwargs)
            self.assertEqual(first, second)
            self.assertEqual([role for role, _ in gateway.calls], ["worker", "character-actor", "environment-writer"])

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
