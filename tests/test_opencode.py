import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from literary_engineering_studio.config import default_config
from literary_engineering_studio.opencode_binary import bundle_manifest, locate_opencode
from literary_engineering_studio.opencode_client import OpenCodeClient, OpenCodeEndpoint, split_model
from literary_engineering_studio.opencode_control import disconnect_provider
from literary_engineering_studio.opencode_profiles import advisor_profile, steward_profile, worker_profile, write_profile
from literary_engineering_studio.runtime_events import normalize_opencode_event


class OpenCodeFoundationTests(unittest.TestCase):
    def test_pinned_manifest_has_checksum_and_mit_notice(self):
        manifest = bundle_manifest()
        self.assertEqual(manifest["version"], "1.18.3")
        self.assertEqual(manifest["license"], "MIT")
        target = manifest["targets"]["windows-x64-baseline"]
        self.assertEqual(len(target["sha256"]), 64)

    def test_explicit_binary_path_is_preferred(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "opencode-fixture.exe"
            executable.write_bytes(b"fixture")
            self.assertEqual(locate_opencode({"executable": str(executable)}), executable.resolve())

    def test_worker_and_advisor_profiles_enforce_capabilities(self):
        worker = worker_profile("opencode/big-pickle")
        worker_permissions = worker["agent"]["literary-worker"]["permission"]
        self.assertEqual(worker_permissions["edit"], "allow")
        self.assertEqual(worker_permissions["bash"], "deny")
        self.assertEqual(worker_permissions["task"], "deny")
        advisor = advisor_profile("opencode/big-pickle")
        advisor_permissions = advisor["agent"]["project-advisor"]["permission"]
        self.assertEqual(advisor_permissions["read"], "allow")
        self.assertEqual(advisor_permissions["edit"], "deny")
        steward_permissions = steward_profile("opencode/big-pickle")["agent"]["creative-steward"]["permission"]
        self.assertEqual(steward_permissions["read"], "allow")
        self.assertEqual(steward_permissions["edit"], "deny")
        self.assertEqual(steward_permissions["bash"], "deny")

    def test_profile_is_valid_json_and_model_is_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = write_profile(Path(temporary), role="worker", model="opencode/big-pickle")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["model"], "opencode/big-pickle")
            self.assertFalse(payload["autoupdate"])
            self.assertEqual(payload["share"], "disabled")

    def test_event_normalizer_drops_reasoning_and_keeps_text_delta(self):
        reasoning = normalize_opencode_event(
            {"type": "message.part.updated", "properties": {"part": {"type": "reasoning"}}}
        )
        self.assertEqual(reasoning, ())
        text = normalize_opencode_event(
            {
                "type": "message.part.updated",
                "properties": {
                    "delta": "hello",
                    "part": {"type": "text", "sessionID": "ses_fixture"},
                },
            },
            session_id="ses_fixture",
        )
        self.assertEqual(text[0][0], "agent.message.delta")

    def test_model_identifier_must_include_provider(self):
        self.assertEqual(split_model("opencode/big-pickle"), ("opencode", "big-pickle"))
        with self.assertRaises(ValueError):
            split_model("big-pickle")

    def test_delete_auth_uses_encoded_provider_path(self):
        client = OpenCodeClient(
            OpenCodeEndpoint("http://127.0.0.1:1", "studio", "fixture", Path.cwd())
        )
        with patch.object(client, "_json", return_value=True) as request:
            self.assertTrue(client.delete_auth("deepseek-compatible"))
        request.assert_called_once_with("DELETE", "/auth/deepseek-compatible")

    def test_disconnect_selected_provider_restores_starter_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = default_config()
            config["agent_runners"]["opencode"]["model"] = "deepseek/deepseek-chat"
            config["model_connections"]["connections"][0].update(
                {"provider_family": "deepseek", "selected_model": "deepseek/deepseek-chat"}
            )
            client = MagicMock()
            client.delete_auth.return_value = True
            session = MagicMock()
            session.__enter__.return_value = SimpleNamespace(client=client)
            session.__exit__.return_value = False
            catalog = {"selected_model": "opencode/big-pickle", "providers": []}
            with (
                patch.dict("os.environ", {"LES_CONFIG_PATH": str(Path(temporary) / "config.json")}),
                patch("literary_engineering_studio.opencode_control._control_session", return_value=session),
                patch("literary_engineering_studio.opencode_control.provider_catalog", return_value=catalog),
            ):
                result = disconnect_provider(config, "deepseek")
            self.assertEqual(result, catalog)
            self.assertEqual(config["agent_runners"]["opencode"]["model"], "opencode/big-pickle")
            record = config["model_connections"]["connections"][0]
            self.assertEqual(record["provider_family"], "opencode")
            self.assertEqual(record["selected_model"], "opencode/big-pickle")
            client.delete_auth.assert_called_once_with("deepseek")

    def test_builtin_starter_provider_cannot_be_disconnected(self):
        with self.assertRaisesRegex(ValueError, "built-in OpenCode starter"):
            disconnect_provider(default_config(), "opencode")


if __name__ == "__main__":
    unittest.main()
