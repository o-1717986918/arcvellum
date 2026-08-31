from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.integrations.pi_worker import control
from literary_engineering_studio.integrations.pi_worker.installation import PiWorkerInstallation


CATALOG = {
    "schema": "arcvellum/pi-worker-catalog/v1",
    "worker_version": "0.99.0",
    "providers": [
        {
            "id": "deepseek",
            "name": "DeepSeek",
            "connected": True,
            "models": [
                {
                    "id": "deepseek-v4-flash",
                    "qualified_id": "deepseek/deepseek-v4-flash",
                    "name": "DeepSeek V4 Flash",
                    "context": 128000,
                }
            ],
        }
    ],
    "connected_provider_count": 1,
    "available_model_count": 1,
}


class PiWorkerControlTests(unittest.TestCase):
    def test_catalog_uses_embedded_worker_without_exposing_secret_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "node.exe"
            entrypoint = root / "main.js"
            executable.write_bytes(b"fixture")
            entrypoint.write_text("", encoding="utf-8")
            config = {
                "agent_runners": {
                    "pi-worker": {
                        "auth_path": str(root / "secret" / "auth.json"),
                        "model": "deepseek/deepseek-v4-flash",
                    }
                }
            }
            with (
                patch.object(
                    control,
                    "locate_pi_worker",
                    return_value=PiWorkerInstallation(str(executable), entrypoint, "embedded"),
                ),
                patch.object(
                    control,
                    "run_hidden",
                    return_value=SimpleNamespace(returncode=0, stdout=json.dumps(CATALOG), stderr=""),
                ),
            ):
                result = control.pi_worker_catalog(config)

        self.assertEqual(result["selected_model"], "deepseek/deepseek-v4-flash")
        self.assertEqual(result["selected_models"]["advisor"], "deepseek/deepseek-v4-flash")
        self.assertEqual(result["auth_path"], "自定义本机凭证库")
        self.assertNotIn(str(root), json.dumps(result, ensure_ascii=False))

    def test_credential_write_is_atomic_and_selection_requires_connected_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            auth = Path(temporary) / "auth.json"
            config = {"agent_runners": {"pi-worker": {"auth_path": str(auth), "model": ""}}}
            connected = {**CATALOG, "selected_model": ""}
            with patch.object(control, "pi_worker_catalog", return_value=connected):
                control.set_pi_api_credential(config, "deepseek", "test-placeholder-key")
                selected = control.select_pi_model(config, "deepseek/deepseek-v4-flash")

            stored = json.loads(auth.read_text(encoding="utf-8"))

        self.assertEqual(stored["deepseek"]["type"], "api_key")
        self.assertEqual(stored["deepseek"]["key"], "test-placeholder-key")
        self.assertEqual(selected["selected_model"], "deepseek/deepseek-v4-flash")
        self.assertEqual(config["agent_runners"]["pi-worker"]["model"], "deepseek/deepseek-v4-flash")

    def test_disconnecting_selected_provider_clears_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            auth = Path(temporary) / "auth.json"
            auth.write_text(
                json.dumps({"deepseek": {"type": "api_key", "key": "test-placeholder-key"}}),
                encoding="utf-8",
            )
            config = {
                "agent_runners": {
                    "pi-worker": {
                        "auth_path": str(auth),
                        "model": "deepseek/deepseek-v4-flash",
                        "models": {"worker": "deepseek/deepseek-v4-flash", "advisor": "deepseek/deepseek-v4-flash"},
                    }
                }
            }
            disconnected = {
                **CATALOG,
                "providers": [{**CATALOG["providers"][0], "connected": False}],
            }
            with patch.object(control, "pi_worker_catalog", return_value=disconnected):
                control.disconnect_pi_provider(config, "deepseek")

            stored = json.loads(auth.read_text(encoding="utf-8"))

        self.assertNotIn("deepseek", stored)
        self.assertEqual(config["agent_runners"]["pi-worker"]["model"], "")
        self.assertEqual(config["agent_runners"]["pi-worker"]["models"]["advisor"], "")

    def test_role_model_selection_does_not_replace_other_roles(self):
        config = {
            "agent_runners": {
                "pi-worker": {
                    "model": "deepseek/deepseek-v4-flash",
                    "models": {
                        "worker": "deepseek/deepseek-v4-flash",
                        "advisor": "deepseek/deepseek-v4-flash",
                    },
                }
            }
        }
        connected = {**CATALOG, "selected_model": "deepseek/deepseek-v4-flash"}
        with patch.object(control, "pi_worker_catalog", return_value=connected):
            control.select_pi_model(
                config,
                "deepseek/deepseek-v4-flash",
                role="advisor",
            )

        models = config["agent_runners"]["pi-worker"]["models"]
        self.assertEqual(models["worker"], "deepseek/deepseek-v4-flash")
        self.assertEqual(models["advisor"], "deepseek/deepseek-v4-flash")


if __name__ == "__main__":
    unittest.main()
