from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from literary_engineering_studio.runtimes.opencode import OpenCodeRuntime
from literary_engineering_studio.task_preflight import PreflightIssue, PreflightResult


class _Client:
    def __init__(self):
        self.prompts = []
        self.status_reads = 0
        self.aborted = False

    def health(self):
        return {"version": "fixture"}

    def create_session(self, _title):
        return {"id": "session-fixed"}

    def events(self, _stop):
        return iter(())

    def prompt_async(self, session_id, *, text, model, agent):
        self.prompts.append({"session_id": session_id, "text": text, "model": model, "agent": agent})
        self.status_reads = 0

    def session_status(self):
        self.status_reads += 1
        return {"session-fixed": {"type": "busy" if self.status_reads == 1 else "idle"}}

    def messages(self, _session_id):
        return [{"info": {"role": "assistant"}, "parts": [{"type": "text", "text": "修复完成"}]}]

    def diff(self, _session_id):
        return []

    def abort(self, _session_id):
        self.aborted = True


class _Pool:
    def __init__(self, client):
        self.client = client
        self.acquires = 0
        self.releases = 0

    def acquire(self, role, workspace, *, model):
        self.acquires += 1
        return SimpleNamespace(
            role=role,
            client=self.client,
            component_id="opencode-worker",
            generation=3,
            reused=True,
        )

    def release(self, _lease):
        self.releases += 1


class _RepairingValidator:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls == 1:
            return PreflightResult(
                False,
                (PreflightIssue("invalid-json", "output.json", "JSON 无法解析。", "修正 JSON。"),),
            )
        return PreflightResult(True, ())


class OpenCodeRuntimeExecutionTests(unittest.TestCase):
    def test_failed_preflight_is_repaired_in_the_same_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            run_root = root / "run"
            workspace.mkdir()
            run_root.mkdir()
            prompt = root / "prompt.md"
            prompt.write_text("执行正式任务", encoding="utf-8")
            client = _Client()
            pool = _Pool(client)
            validator = _RepairingValidator()
            events = []
            runtime = OpenCodeRuntime({"model": "fixture/model", "models": {"worker": "fixture/model"}})
            runtime.runtime_pool = pool

            with patch(
                "literary_engineering_studio.runtimes.opencode.locate_opencode",
                return_value=Path("opencode.exe"),
            ):
                result = runtime.execute(
                    workspace,
                    prompt,
                    run_root,
                    timeout=10,
                    event_sink=lambda event, data: events.append((event, data)),
                    output_validator=validator,
                    max_repairs=2,
                )

            self.assertEqual(result.status, "completed")
            self.assertEqual(pool.acquires, 1)
            self.assertEqual(pool.releases, 1)
            self.assertEqual(validator.calls, 2)
            self.assertEqual(len(client.prompts), 2)
            self.assertEqual({item["session_id"] for item in client.prompts}, {"session-fixed"})
            self.assertIn("Studio Preflight Repair 1/2", client.prompts[1]["text"])
            self.assertEqual(result.metadata["repairs"], 1)
            self.assertTrue(result.metadata["service_reused"])
            self.assertFalse(client.aborted)
            finished = [data for event, data in events if event == "runner.session.finished"]
            self.assertEqual(finished[-1]["session_id"], "session-fixed")
            self.assertEqual(finished[-1]["status"], "complete")


if __name__ == "__main__":
    unittest.main()
