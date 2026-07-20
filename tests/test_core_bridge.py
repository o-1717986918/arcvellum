from contextlib import redirect_stderr
from io import StringIO
import unittest

from literary_engineering_studio.core_bridge import _assert_studio_engine_args, parse_cli_fields
from literary_engineering_studio_engine.cli import main as engine_main


class CoreBridgeTests(unittest.TestCase):
    def test_parses_formal_cli_fields(self):
        fields = parse_cli_fields("status: issued\ntask_id: scene-demo\nmessage: task issued\n")
        self.assertEqual(fields["status"], "issued")
        self.assertEqual(fields["task_id"], "scene-demo")

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
