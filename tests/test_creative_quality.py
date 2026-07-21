from pathlib import Path
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None

from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.config import default_config
from literary_engineering_studio_engine.anti_ai_style import style_lint_gate
from literary_engineering_studio_engine.creative_quality import (
    creative_quality_profile_path,
    default_creative_quality_profile,
    load_creative_quality_profile,
    save_creative_quality_profile,
)
from literary_engineering_studio_engine.punctuation_standard import lint_punctuation


class CreativeQualityProfileTests(unittest.TestCase):
    def test_profile_is_versioned_only_when_semantics_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.joinpath("project.yaml").write_text("project:\n  title: test\n", encoding="utf-8")
            first = save_creative_quality_profile(root, default_creative_quality_profile())
            same = save_creative_quality_profile(root, first)
            changed_payload = dict(same)
            changed_payload["thresholds"] = dict(same["thresholds"])
            changed_payload["thresholds"]["dash_per_100_units"] = 5
            changed = save_creative_quality_profile(root, changed_payload)
            self.assertEqual(same["revision"], first["revision"])
            self.assertEqual(changed["revision"], first["revision"] + 1)
            self.assertNotEqual(changed["digest"], first["digest"])
            self.assertTrue(creative_quality_profile_path(root).exists())

    def test_rule_mode_can_turn_creative_warning_off_without_disabling_engine_gates(self):
        profile = default_creative_quality_profile()
        text = "他嘴角微扬。" * 12
        self.assertNotEqual(style_lint_gate(text, profile=profile)["status"], "pass")
        profile["rule_modes"]["plain-narration-banned-expression"] = "off"
        self.assertEqual(style_lint_gate(text, profile=profile)["status"], "pass")

    def test_dash_threshold_and_message_use_same_units(self):
        profile = default_creative_quality_profile()
        text = ("他说完了。" * 99) + "门开了——灯还亮着。"
        self.assertFalse(any(item.rule == "dash-overuse" for item in lint_punctuation(text, profile=profile)))
        profile["thresholds"]["dash_per_100_units"] = 0.5
        issues = lint_punctuation(text, profile=profile)
        dash = next(item for item in issues if item.rule == "dash-overuse")
        self.assertIn("每 100 个叙事单元", dash.message)
        self.assertIn("0.5", dash.message)

    def test_custom_banned_phrase_is_detected(self):
        profile = default_creative_quality_profile()
        profile["custom_banned_phrases"] = ["命运的齿轮"]
        gate = style_lint_gate("命运的齿轮开始转动。" * 4, profile=profile)
        self.assertEqual(gate["status"], "blocking")
        self.assertEqual(gate["blocking"][0]["rule"], "custom-banned-phrase")

    def test_missing_profile_loads_compatible_implicit_default(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = load_creative_quality_profile(Path(directory))
            self.assertTrue(profile["implicit_default"])
            self.assertTrue(profile["digest"])

    def test_scene_exception_is_scoped_and_requires_a_reason(self):
        profile = default_creative_quality_profile()
        profile["exceptions"] = [
            {
                "rule": "mechanical-contrast-frame",
                "scope": "scene_0042",
                "reason": "人物在法庭上进行明确二分判断",
                "mode": "note",
                "expires_at": "",
            }
        ]
        text = "这不是误会，而是决定。"
        self.assertEqual(style_lint_gate(text, profile=profile)["status"], "blocking")
        self.assertEqual(style_lint_gate(text, profile=profile, scope="scene_0042")["status"], "notes")
        self.assertEqual(style_lint_gate(text, profile=profile, scope="scene_0043")["status"], "blocking")

        invalid = default_creative_quality_profile()
        invalid["exceptions"] = [{"rule": "mechanical-contrast-frame", "scope": "scene_0042", "mode": "note"}]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                save_creative_quality_profile(Path(directory), invalid)


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class CreativeQualityApiTests(unittest.TestCase):
    def test_get_update_and_preview(self):
        with tempfile.TemporaryDirectory() as application_directory, tempfile.TemporaryDirectory() as directory:
            config = default_config()
            application_root = Path(application_directory)
            config["application"]["data_root"] = str(application_root)
            config["application"]["database_path"] = str(application_root / "studio.sqlite3")
            config["application"]["projects_root"] = str(application_root / "projects")
            config["worker"]["runs_root"] = str(application_root / "runs")
            config["agent_runners"]["opencode"]["data_root"] = str(application_root)
            client = TestClient(create_app(config))
            root = Path(directory)
            root.joinpath("project.yaml").write_text("project:\n  title: test\n", encoding="utf-8")
            current = client.get("/project/creative-quality", params={"project_root": str(root)})
            self.assertEqual(current.status_code, 200)
            profile = current.json()["profile"]
            profile["name"] = "我的写作规则"
            saved = client.put(
                "/project/creative-quality",
                json={"project_root": str(root), "profile": profile},
            )
            self.assertEqual(saved.status_code, 200)
            self.assertEqual(saved.json()["profile"]["name"], "我的写作规则")
            preview = client.post(
                "/project/creative-quality/preview",
                json={"project_root": str(root), "text": "这不是误会，而是决定。"},
            )
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.json()["status"], "blocking")

            profile = saved.json()["profile"]
            profile["exceptions"] = [{"rule": "mechanical-contrast-frame", "scope": "scene_0007", "reason": "场景登记例外", "mode": "note", "expires_at": ""}]
            scoped = client.post(
                "/project/creative-quality/preview",
                json={"project_root": str(root), "text": "这不是误会，而是决定。", "profile": profile, "scope": "scene_0007"},
            )
            self.assertEqual(scoped.status_code, 200)
            self.assertEqual(scoped.json()["status"], "notes")
            client.close()


if __name__ == "__main__":
    unittest.main()
