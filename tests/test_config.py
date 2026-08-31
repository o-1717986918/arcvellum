import json
import tempfile
from pathlib import Path
import sys
import unittest

from literary_engineering_studio.config import CONFIG_SCHEMA, default_config, load_config, repository_root, save_config


class ConfigTests(unittest.TestCase):
    def test_migrates_untouched_v06_pi_prompt_canary_to_all_pi_tasks_v3(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-studio/config/v0.6",
                        "worker": {
                            "prompt_program": {
                                "mode": "shadow",
                                "enforcement": {
                                    "enabled": False,
                                    "runtimes": ["pi-worker"],
                                    "routes": ["character-and-world-assets", "scene-development"],
                                    "states": ["asset-creation-agent-task", "candidate-review"],
                                    "task_kinds": ["creative", "review"],
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(path)
            prompt = config["worker"]["prompt_program"]

            self.assertEqual(prompt["mode"], "enforced")
            self.assertTrue(prompt["enforcement"]["enabled"])
            self.assertEqual(prompt["enforcement"]["runtimes"], ["pi-worker"])
            self.assertNotIn("routes", prompt["enforcement"])
            self.assertNotIn("states", prompt["enforcement"])
            self.assertNotIn("task_kinds", prompt["enforcement"])

    def test_migrates_v07_prose_only_rollout_to_all_pi_tasks_v3(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-studio/config/v0.7",
                        "worker": {
                            "prompt_program": {
                                "mode": "enforced",
                                "enforcement": {
                                    "enabled": True,
                                    "runtimes": ["pi-worker"],
                                    "routes": ["scene-development"],
                                    "states": ["candidate-generation-provenance"],
                                    "task_kinds": ["prose"],
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            prompt = load_config(path)["worker"]["prompt_program"]

            self.assertEqual(
                prompt["enforcement"],
                {"enabled": True, "runtimes": ["pi-worker"]},
            )

    def test_repository_root_is_the_checkout_root_not_src_directory(self):
        root = repository_root()
        self.assertTrue((root / "pyproject.toml").is_file())
        self.assertTrue((root / "src" / "literary_engineering_studio_engine").is_dir())

    def test_default_config_has_no_model_provider(self):
        config = default_config()
        self.assertNotIn("model", config)
        self.assertNotIn("profiles", config)
        self.assertNotIn("core", config)
        self.assertEqual(config["engine"]["module"], "literary_engineering_studio_engine")
        self.assertIn("agent_runners", config)
        self.assertFalse(config["agent_runners"]["pi-rpc"]["enabled"])
        self.assertTrue(config["agent_runners"]["pi-rpc"]["experiment_only"])
        self.assertTrue(config["agent_runners"]["pi-worker"]["enabled"])
        self.assertFalse(config["agent_runners"]["pi-worker"]["experiment_only"])
        self.assertFalse(config["agent_runners"]["opencode"]["enabled"])
        self.assertEqual(config["agent_runtime_roles"]["worker"], "pi-worker")
        self.assertEqual(config["agent_runtime_roles"]["advisor"], "pi-worker")
        self.assertIn("model_connections", config)
        self.assertNotIn("runtimes", config)
        self.assertEqual(
            config["worker"]["prompt_program"]["enforcement"],
            {"enabled": True, "runtimes": ["pi-worker"]},
        )
        self.assertEqual(config["worker"]["execution_profile"]["mode"], "enforced")
        self.assertEqual(
            config["worker"]["execution_profile"]["enforcement"],
            {
                "enabled": True,
                "runtimes": ["pi-worker"],
                "routes": ["scene-development"],
                "states": ["candidate-generation-provenance"],
                "task_kinds": ["prose"],
            },
        )

    def test_migrates_untouched_legacy_pi_profile_to_prose_enforcement(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "config.json"
            target.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-studio/config/v0.8",
                        "worker": {
                            "execution_profile": {
                                "mode": "shadow",
                                "enforcement": {
                                    "enabled": False,
                                    "runtimes": ["pi-worker"],
                                    "routes": ["character-and-world-assets", "scene-development"],
                                    "states": ["asset-creation-agent-task", "candidate-review"],
                                    "task_kinds": ["creative", "review"],
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            profile = load_config(target)["worker"]["execution_profile"]

            self.assertEqual(profile["mode"], "enforced")
            self.assertEqual(profile["enforcement"]["states"], ["candidate-generation-provenance"])
            self.assertEqual(profile["enforcement"]["task_kinds"], ["prose"])

    def test_preserves_custom_legacy_execution_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "config.json"
            target.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-studio/config/v0.8",
                        "worker": {
                            "execution_profile": {
                                "mode": "shadow",
                                "enforcement": {
                                    "enabled": False,
                                    "runtimes": ["pi-worker"],
                                    "routes": ["style-learning"],
                                    "states": ["style-agent-task"],
                                    "task_kinds": ["style"],
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            profile = load_config(target)["worker"]["execution_profile"]

            self.assertEqual(profile["mode"], "shadow")
            self.assertEqual(profile["enforcement"]["routes"], ["style-learning"])

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

    def test_migrates_experimental_pi_worker_to_embedded_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "config.json"
            target.write_text(
                json.dumps(
                    {
                        "schema": "literary-engineering-studio/config/v0.5",
                        "agent_runners": {
                            "pi-worker": {
                                "enabled": False,
                                "executable": "D:/prototype/node.exe",
                                "entrypoint": "D:/prototype/main.js",
                                "model": "deepseek/deepseek-v4-flash",
                                "auth_path": "D:/private/auth.json",
                                "experiment_only": True,
                                "experiment_authorized": True,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_config(target)
            pi_worker = loaded["agent_runners"]["pi-worker"]

            self.assertTrue(pi_worker["enabled"])
            self.assertFalse(pi_worker["experiment_only"])
            self.assertEqual(pi_worker["executable"], "")
            self.assertEqual(pi_worker["entrypoint"], "")
            self.assertEqual(pi_worker["model"], "deepseek/deepseek-v4-flash")
            self.assertEqual(pi_worker["auth_path"], "D:/private/auth.json")
            self.assertNotIn("experiment_authorized", pi_worker)

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

    def test_load_ignores_machine_local_engine_path_from_an_old_install(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "config.json"
            target.write_text(
                '{"engine":{"python":"D:/removed/ArcVellum/literary-engineering-studio-sidecar.exe",'
                '"module":"literary_engineering_studio_engine"}}',
                encoding="utf-8",
            )

            loaded = load_config(target)

            self.assertEqual(loaded["engine"]["python"], sys.executable)
            self.assertEqual(loaded["engine"]["module"], "literary_engineering_studio_engine")

    def test_save_does_not_persist_machine_local_engine_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "config.json"
            config = default_config()
            config["engine"]["python"] = "D:/ArcVellum/literary-engineering-studio-sidecar.exe"

            save_config(config, target)
            persisted = json.loads(target.read_text(encoding="utf-8"))

            self.assertNotIn("python", persisted["engine"])
            self.assertEqual(load_config(target)["engine"]["python"], sys.executable)

    def test_rejects_api_key_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "config.json"
            with self.assertRaises(ValueError):
                save_config({"api_key": "test-placeholder-key"}, target)


if __name__ == "__main__":
    unittest.main()
