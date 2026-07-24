import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from literary_engineering_studio.cli import main


class CliCommandTests(unittest.TestCase):
    def test_doctor_serializes_a_command_result(self):
        bridge_result = type("Result", (), {"returncode": 0, "stderr": ""})()
        with (
            patch("literary_engineering_studio.cli.CoreBridge.doctor", return_value=bridge_result),
            patch("literary_engineering_studio.cli.agent_runner_status", return_value=[]),
            patch("literary_engineering_studio.cli.model_connection_status", return_value={}),
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["doctor"]), 0)
        self.assertTrue(json.loads(output.getvalue())["engine"]["available"])

    def test_prompt_eval_serializes_a_command_result(self):
        with patch(
            "literary_engineering_studio.cli.evaluate_prompt_assets",
            return_value={"status": "pass", "cases": []},
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["prompt-eval"]), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "pass")


if __name__ == "__main__":
    unittest.main()
