import tempfile
from pathlib import Path
import unittest

from literary_engineering_studio.config import CONFIG_SCHEMA, default_config, load_config, save_config


class ConfigTests(unittest.TestCase):
    def test_default_config_has_no_model_provider(self):
        config = default_config()
        self.assertNotIn("model", config)
        self.assertNotIn("profiles", config)
        self.assertNotIn("core", config)
        self.assertEqual(config["engine"]["module"], "literary_engineering_studio_engine")
        self.assertIn("agent_runners", config)
        self.assertIn("model_connections", config)
        self.assertNotIn("runtimes", config)

    def test_migrates_legacy_runtimes_to_agent_runners(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "config.json"
            target.write_text(
                '{"schema":"literary-engineering-studio/config/v0.2","runtimes":{"host-agent":{"enabled":false}}}',
                encoding="utf-8",
            )
            loaded = load_config(target)
            self.assertEqual(loaded["schema"], CONFIG_SCHEMA)
            self.assertFalse(loaded["agent_runners"]["host-agent"]["enabled"])
            self.assertNotIn("runtimes", loaded)

    def test_migrates_unified_opencode_model_to_all_agent_roles(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "config.json"
            target.write_text(
                '{"agent_runners":{"opencode":{"model":"deepseek/deepseek-chat"}}}',
                encoding="utf-8",
            )

            loaded = load_config(target)

            self.assertEqual(
                loaded["agent_runners"]["opencode"]["models"],
                {
                    "worker": "deepseek/deepseek-chat",
                    "advisor": "deepseek/deepseek-chat",
                    "steward": "deepseek/deepseek-chat",
                },
            )

    def test_rejects_api_key_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "config.json"
            with self.assertRaises(ValueError):
                save_config({"api_key": "test-placeholder-key"}, target)


if __name__ == "__main__":
    unittest.main()
