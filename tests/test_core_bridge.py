from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.config import default_config
from literary_engineering_studio.core_bridge import CoreBridge, CoreCommandResult, _assert_studio_engine_args, parse_cli_fields, task_command_parameters
from literary_engineering_studio_engine.cli import main as engine_main


class CoreBridgeTests(unittest.TestCase):
    def test_task_command_parameters_distinguishes_project_placeholder_from_required_choices(self):
        self.assertEqual(task_command_parameters("python -m literary_engineering_studio_engine word-budget <project>"), ())
        self.assertEqual(
            task_command_parameters("python -m literary_engineering_studio_engine asset-create <project> --type <type> [--source <path>]"),
            ("type", "--source <path>"),
        )

    def test_source_checkout_does_not_use_stale_installed_sidecar(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
            (root / "src" / "literary_engineering_studio_engine").mkdir(parents=True)
            config = default_config()
            config["engine"]["python"] = "D:/ArcVellum/literary-engineering-studio-sidecar.exe"
            with patch("literary_engineering_studio.core_bridge.repository_root", return_value=root):
                bridge = CoreBridge(config)
            self.assertEqual(bridge.python, sys.executable)

    def test_project_placeholder_is_not_treated_as_shell_redirection(self):
        config = default_config()
        bridge = CoreBridge(config)
        with patch.object(bridge, "run") as run:
            run.return_value = CoreCommandResult(("python",), 0, "", "", {})
            bridge.execute_task_command(
                "python -m literary_engineering_studio_engine word-budget <project> --target-words 30000",
                Path("C:/work-project"),
            )
        args = run.call_args.args[0]
        self.assertIn(str(Path("C:/work-project").resolve()), args)

    def test_unresolved_template_is_reported_as_required_input_not_shell_syntax(self):
        bridge = CoreBridge(default_config())
        command = "python -m literary_engineering_studio_engine word-budget <project> --target-words <target>"
        with self.assertRaisesRegex(ValueError, "requires: target") as raised:
            bridge.execute_task_command(command, Path("C:/work-project"))
        self.assertNotIn("unsupported shell syntax", str(raised.exception))

    def test_asset_template_is_reported_as_required_input_not_shell_syntax(self):
        bridge = CoreBridge(default_config())
        command = (
            "python -m literary_engineering_studio_engine asset-create <project> "
            "--type <type> --brief <user brief> [--source <path>]"
        )
        with self.assertRaisesRegex(ValueError, "requires: type, user brief, --source <path>") as raised:
            bridge.execute_task_command(command, Path("C:/work-project"))
        self.assertNotIn("unsupported shell syntax", str(raised.exception))

    def test_parses_formal_cli_fields(self):
        fields = parse_cli_fields("status: issued\ntask_id: scene-demo\nmessage: task issued\n")
        self.assertEqual(fields["status"], "issued")
        self.assertEqual(fields["task_id"], "scene-demo")

    def test_engine_subprocess_forces_utf8_transport_on_windows_code_pages(self):
        bridge = CoreBridge(default_config())
        with patch("literary_engineering_studio.core_bridge.run_hidden") as run:
            run.return_value = type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            bridge.run(["--help"])
        env = run.call_args.kwargs["env"]
        self.assertEqual(env["PYTHONUTF8"], "1")
        self.assertEqual(env["PYTHONIOENCODING"], "utf-8")

    def test_rejects_embedded_model_provider_commands(self):
        for args in (
            ["agent-run", "C:/project", "--provider", "auto"],
            ["director-chat", "C:/project", "--message", "continue"],
            ["config-set-profile", "--name", "remote"],
            ["serve-api"],
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                _assert_studio_engine_args(args)

    def test_allows_platform_agent_task_generation(self):
        _assert_studio_engine_args(
            ["style-prompt", "C:/project/style/demo", "--provider", "platform-agent"]
        )

    def test_embedded_engine_direct_entry_rejects_provider_routes(self):
        for args in (["config-show"], ["agent-run", "C:/project", "--agent-id", "x", "--task", "x"]):
            with self.subTest(args=args), redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                engine_main(args)


if __name__ == "__main__":
    unittest.main()
