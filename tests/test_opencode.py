import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from literary_engineering_studio.config import default_config, load_config
from literary_engineering_studio.opencode_binary import (
    _write_installation_receipt,
    bundle_manifest,
    ensure_opencode_integrity,
    install_pinned_opencode,
    locate_opencode,
    verify_opencode,
)
from literary_engineering_studio.opencode_client import OpenCodeClient, OpenCodeEndpoint, split_model
from literary_engineering_studio.opencode_control import disconnect_provider, select_model
from literary_engineering_studio.opencode_profiles import (
    OpenCodeRole,
    advisor_profile,
    planner_profile,
    reviewer_profile,
    steward_profile,
    worker_profile,
    write_profile,
)
from literary_engineering_studio.integrations.opencode.provider_definitions import (
    opencode_provider_overrides,
    register_custom_provider,
)
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

    def test_installation_receipt_detects_tampered_binary(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "opencode.exe"
            executable.write_bytes(b"fixture")
            manifest = bundle_manifest()
            with patch("literary_engineering_studio.opencode_binary.current_target", return_value="windows-x64-baseline"):
                _write_installation_receipt(executable, manifest, "windows-x64-baseline")
                verified = verify_opencode(executable)
                self.assertTrue(verified["verified"])
                executable.write_bytes(b"tampered")
                self.assertEqual(verify_opencode(executable)["verification_state"], "receipt-mismatch")
                with self.assertRaisesRegex(RuntimeError, "integrity verification failed"):
                    ensure_opencode_integrity(executable)

    def test_build_time_receipt_is_not_treated_as_a_tamper_event(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "opencode.exe"
            executable.write_bytes(b"fixture")
            (Path(temporary) / "opencode-installation.json").write_text(
                json.dumps(
                    {
                        "status": "build-time-receipt-required",
                        "version": "1.18.3",
                        "target": "windows-x64-baseline",
                        "executable": "opencode.exe",
                        "binary_sha256": "BUILD_TIME_RECEIPT_REQUIRED",
                    }
                ),
                encoding="utf-8",
            )
            with patch("literary_engineering_studio.opencode_binary.current_target", return_value="windows-x64-baseline"):
                verification = ensure_opencode_integrity(executable)
            self.assertEqual(verification["verification_state"], "build-time-receipt-required")

    def test_install_replaces_unrecorded_build_cache_with_verified_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "fixture.zip"
            with __import__("zipfile").ZipFile(archive_path, "w") as archive:
                archive.writestr("opencode.exe", b"verified fixture")
            manifest = {
                "version": "fixture",
                "targets": {
                    "windows-x64-baseline": {
                        "archive": "fixture.zip",
                        "url": "https://example.invalid/fixture.zip",
                        "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                        "executable": "opencode.exe",
                    }
                },
            }
            destination = root / "expanded"
            destination.mkdir()
            (destination / "opencode.exe").write_bytes(b"unrecorded cache")
            with (
                patch("literary_engineering_studio.opencode_binary.bundle_manifest", return_value=manifest),
                patch("literary_engineering_studio.opencode_binary.current_target", return_value="windows-x64-baseline"),
                patch("literary_engineering_studio.opencode_binary.urlopen") as download,
            ):
                result = install_pinned_opencode(destination)
                verification = verify_opencode(destination / "opencode.exe")
            self.assertEqual(result["status"], "installed")
            self.assertTrue(verification["verified"])
            self.assertEqual((destination / "opencode.exe").read_bytes(), b"verified fixture")
            download.assert_not_called()

    def test_worker_and_advisor_profiles_enforce_capabilities(self):
        worker = worker_profile("opencode/big-pickle")
        worker_permissions = worker["agent"]["literary-worker"]["permission"]
        self.assertEqual(worker_permissions["edit"], "allow")
        self.assertEqual(worker_permissions["read"]["*"], "allow")
        self.assertEqual(
            worker_permissions["read"]["*.agent_tasks.md"],
            "deny",
        )
        self.assertEqual(worker_permissions["glob"], "deny")
        self.assertEqual(worker_permissions["grep"], "deny")
        self.assertEqual(worker_permissions["bash"], "deny")
        self.assertEqual(worker_permissions["task"], "deny")
        advisor = advisor_profile("opencode/big-pickle")
        advisor_permissions = advisor["agent"]["project-advisor"]["permission"]
        self.assertEqual(advisor_permissions["read"], "allow")
        self.assertEqual(advisor_permissions["edit"], "deny")
        steward_permissions = steward_profile("opencode/big-pickle")["agent"]["creative-steward"]["permission"]
        self.assertEqual(steward_permissions["read"], "deny")
        self.assertEqual(steward_permissions["glob"], "deny")
        self.assertEqual(steward_permissions["edit"], "deny")
        self.assertEqual(steward_permissions["bash"], "deny")

    def test_orchestration_profiles_are_read_only_and_role_names_are_strict(self):
        planner = planner_profile("fixture/model")
        reviewer = reviewer_profile("fixture/model")
        planner_permissions = planner["agent"]["orchestration-planner"]["permission"]
        reviewer_permissions = reviewer["agent"]["orchestration-reviewer"]["permission"]
        self.assertEqual(planner_permissions["read"], "allow")
        self.assertEqual(planner_permissions["edit"], "deny")
        self.assertEqual(planner_permissions["write"], "deny")
        self.assertEqual(reviewer_permissions["read"], "allow")
        self.assertEqual(reviewer_permissions["edit"], "deny")
        self.assertNotEqual(planner["default_agent"], reviewer["default_agent"])
        with tempfile.TemporaryDirectory() as temporary:
            path = write_profile(
                Path(temporary),
                role=OpenCodeRole.PLANNER,
                model="fixture/model",
            )
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["default_agent"], "orchestration-planner")
            with self.assertRaises(ValueError):
                write_profile(Path(temporary), role="unknown", model="fixture/model")

    def test_profile_is_valid_json_and_model_is_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = write_profile(Path(temporary), role="worker", model="opencode/big-pickle")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["model"], "opencode/big-pickle")
            self.assertFalse(payload["autoupdate"])
            self.assertEqual(payload["share"], "disabled")

    def test_custom_compatible_provider_is_written_into_isolated_profile_without_credentials(self):
        config = default_config()
        register_custom_provider(
            config,
            {
                "provider_id": "team-gateway",
                "display_name": "Team Gateway",
                "base_url": "https://models.example.test/v1",
                "models": [{"id": "writer-1", "name": "Writer One", "context": 128000, "output": 8192}],
            },
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = write_profile(
                Path(temporary),
                role="worker",
                model="team-gateway/writer-1",
                provider_overrides=opencode_provider_overrides(config),
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
        provider = payload["provider"]["team-gateway"]
        self.assertEqual(provider["options"]["baseURL"], "https://models.example.test/v1")
        self.assertIn("writer-1", provider["models"])
        self.assertNotIn("credential", json.dumps(payload).lower())
        self.assertNotIn("api_key", json.dumps(payload).lower())

    def test_role_model_selection_persists_across_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_path = Path(temporary) / "config.json"
            with patch.dict("os.environ", {"LES_CONFIG_PATH": str(config_path)}):
                config = default_config()
                worker = select_model(config, "zhipuai/glm-5", role="worker")
                advisor = select_model(config, "alibaba-cn/qwen-plus", role="advisor")
                reloaded = load_config()
        settings = reloaded["agent_runners"]["opencode"]
        self.assertEqual(worker["selected_models"]["worker"], "zhipuai/glm-5")
        self.assertEqual(advisor["selected_models"]["advisor"], "alibaba-cn/qwen-plus")
        self.assertEqual(settings["model"], "zhipuai/glm-5")
        self.assertEqual(settings["models"]["worker"], "zhipuai/glm-5")
        self.assertEqual(settings["models"]["advisor"], "alibaba-cn/qwen-plus")
        self.assertNotEqual(settings["models"]["worker"], "opencode/deepseek-v4-flash-free")

    def test_event_normalizer_reduces_reasoning_to_content_free_activity(self):
        reasoning = normalize_opencode_event(
            {
                "type": "message.part.updated",
                "properties": {
                    "delta": "private chain text",
                    "part": {"type": "reasoning", "sessionID": "ses_fixture"},
                },
            }
        )
        self.assertEqual(reasoning[0][0], "runner.reasoning.activity")
        self.assertNotIn("private chain text", json.dumps(reasoning))
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
            config["model_connections"]["connections"] = [
                {
                    "connection_id": "opencode-starter",
                    "provider_family": "opencode",
                    "connection_method": "external-agent-runtime",
                    "agent_runner": "opencode",
                    "selected_model": "opencode/big-pickle",
                }
            ]
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
