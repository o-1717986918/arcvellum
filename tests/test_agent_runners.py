import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

from literary_engineering_studio.runtimes.base import AgentRuntime
from literary_engineering_studio.runtimes.claude_code import ClaudeCodeRuntime


class SlowFakeRunner(AgentRuntime):
    runtime_id = "slow-fake"

    def build_command(self, workspace: Path):
        return (sys.executable, "-c", "import time; print('started', flush=True); time.sleep(30)")


class AgentRunnerTests(unittest.TestCase):
    def test_runner_execution_can_be_cancelled(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            prompt = root / "prompt.md"
            prompt.write_text("cancel fixture", encoding="utf-8")
            cancel = threading.Event()

            def request_cancel():
                time.sleep(0.2)
                cancel.set()

            threading.Thread(target=request_cancel, daemon=True).start()
            result = SlowFakeRunner({"executable": sys.executable}).execute(
                workspace,
                prompt,
                root,
                timeout=10,
                cancel_event=cancel,
            )
            self.assertEqual(result.status, "cancelled")

    def test_claude_command_is_safe_streaming_and_model_explicit(self):
        runner = ClaudeCodeRuntime(
            {
                "executable": sys.executable,
                "permission_mode": "acceptEdits",
                "model": "fixture-model",
                "max_budget_usd": 1.5,
            }
        )
        command = runner.build_command(Path.cwd())
        self.assertIn("--verbose", command)
        self.assertIn("--safe-mode", command)
        self.assertIn("--disable-slash-commands", command)
        self.assertIn("--strict-mcp-config", command)
        self.assertEqual(command[command.index("--mcp-config") + 1], '{"mcpServers":{}}')
        self.assertEqual(command[command.index("--model") + 1], "fixture-model")

    def test_claude_stream_parser_omits_thinking_and_normalizes_usage(self):
        runner = ClaudeCodeRuntime({})
        thinking = runner.normalize_output_line(
            json.dumps(
                {
                    "type": "stream_event",
                    "event": {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "hidden"}},
                }
            )
        )
        self.assertEqual(thinking, ())
        text = runner.normalize_output_line(
            json.dumps(
                {
                    "type": "stream_event",
                    "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hello"}},
                }
            )
        )
        self.assertEqual(text[0][0], "agent.message.delta")
        result = runner.normalize_output_line(
            json.dumps({"type": "result", "usage": {"input_tokens": 3}, "total_cost_usd": 0.01})
        )
        self.assertEqual(result[0][0], "usage.updated")
        self.assertEqual(result[-1][0], "agent.message.completed")


if __name__ == "__main__":
    unittest.main()
