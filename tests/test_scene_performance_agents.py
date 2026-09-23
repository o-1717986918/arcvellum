from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.runtime.role_conversation import RoleConversationResult
from literary_engineering_studio.application.config import default_config
from literary_engineering_studio.application.scene_performance_preferences import get_scene_performance_preferences
from literary_engineering_studio.runtimes.pi_scene_transaction import PiSceneTransactionRuntime
from literary_engineering_studio_engine.public.literary import (
    parse_actor_material,
    parse_environment_material,
    parse_performance_plan,
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
    def __init__(self, *, bad_plan: bool = False):
        super().__init__()
        self.bad_plan = bad_plan

    def run(self, workspace, prompt, *, role, timeout, event_sink=None, cancel_event=None):
        if prompt.startswith("# Scene Performance Direction"):
            self.calls.append((role, prompt))
            plan = _plan()
            if self.bad_plan:
                plan["beats"][0]["speaker"] = "character/outsider"
            answer = json.dumps(plan, ensure_ascii=False)
        elif role == "character-actor":
            self.calls.append((role, prompt))
            answer = json.dumps({
                "beat_id": "b1", "speaker": "character/protagonist",
                "candidates": [{"spoken": "信是我拿的。你先别把门关上。", "visible_action": "他把信留在桌沿，没有推向她。", "subtext_effect": "承认同时请求继续对话"}],
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
            self.assertIn("门缝里的光", gateway.calls[3][1])
            self.assertEqual(first, second)
            self.assertEqual(runtime.metrics.cache_hits, 1)
            self.assertIn("scene.performance.actor", events)
            self.assertIn("scene.performance.environment", events)

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
