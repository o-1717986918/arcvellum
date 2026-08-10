from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import textwrap
import threading
import unittest

from literary_engineering_studio.integrations.pi_rpc import (
    JsonlFramer,
    PiRpcProcess,
    PiRpcProtocolError,
    encode_jsonl,
)
from literary_engineering_studio.runtimes.pi_rpc import PiRpcRuntime


FIXTURE_SERVER = r'''\
import json
from pathlib import Path
import sys
import time

if "--version" in sys.argv:
    print("fixture-pi 0.84.1")
    raise SystemExit(0)

for line in sys.stdin.buffer:
    command = json.loads(line.decode("utf-8"))
    command_id = command.get("id")
    command_type = command.get("type")
    if command_type == "get_state":
        print(json.dumps({"id":"unmatched","type":"response","command":"get_state","success":True,"data":{}}), flush=True)
        print(json.dumps({"type":"agent_start"}), flush=True)
        print(json.dumps({"id":command_id,"type":"response","command":"get_state","success":True,"data":{"sessionId":"fixture-session","model":{"provider":"fixture","id":"fixture-model"}}}), flush=True)
    elif command_type == "prompt":
        Path("result.md").write_text("fixture output", encoding="utf-8")
        print(json.dumps({"id":command_id,"type":"response","command":"prompt","success":True}), flush=True)
        print(json.dumps({"type":"message_update","assistantMessageEvent":{"type":"thinking_delta","delta":"private fixture reasoning"}}), flush=True)
        print(json.dumps({"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"done"}}), flush=True)
        print(json.dumps({"type":"agent_settled"}), flush=True)
    elif command_type == "get_session_stats":
        print(json.dumps({"id":command_id,"type":"response","command":"get_session_stats","success":True,"data":{"sessionId":"fixture-session","tokens":{"input":10,"output":2},"cost":0.01}}), flush=True)
    elif command_type == "abort":
        print(json.dumps({"id":command_id,"type":"response","command":"abort","success":True}), flush=True)
'''


class PiRpcFramingTests(unittest.TestCase):
    def test_fragmented_and_coalesced_records_preserve_unicode_separators(self):
        framer = JsonlFramer()
        first = encode_jsonl({"id": "one", "text": "a\u2028b"})
        second = encode_jsonl({"id": "two"})
        self.assertEqual(framer.feed(first[:5]), ())
        records = framer.feed(first[5:] + second)
        self.assertEqual([record["id"] for record in records], ["one", "two"])
        self.assertEqual(records[0]["text"], "a\u2028b")
        self.assertEqual(framer.finish(), ())

    def test_bom_is_rejected(self):
        with self.assertRaisesRegex(PiRpcProtocolError, "must not contain"):
            JsonlFramer().feed(b"\xef\xbb\xbf{}\n")


class PiRpcProcessTests(unittest.TestCase):
    def _server(self, root: Path) -> Path:
        script = root / "fixture_pi.py"
        script.write_text(textwrap.dedent(FIXTURE_SERVER), encoding="utf-8")
        return script

    def test_request_correlation_events_abort_and_clean_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            server = self._server(root)
            events: list[dict[str, object]] = []
            process = PiRpcProcess(
                (sys.executable, "-u", str(server), "--mode", "rpc"),
                cwd=root,
                event_sink=events.append,
            )
            process.start()
            pid = process.pid
            response = process.request("get_state")
            self.assertEqual(response["data"]["sessionId"], "fixture-session")
            self.assertTrue(any(event.get("type") == "agent_start" for event in events))
            process.abort()
            process.close()
            self.assertIsNotNone(pid)
            self.assertIsNotNone(process.returncode)

    def test_timeout_can_be_terminated_without_residual_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / "silent.py"
            script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
            process = PiRpcProcess((sys.executable, "-u", str(script)), cwd=root)
            process.start()
            with self.assertRaises(TimeoutError):
                process.request("get_state", timeout=0.1)
            process.terminate()
            self.assertIsNotNone(process.returncode)


class PiRpcRuntimeTests(unittest.TestCase):
    def test_short_lived_runtime_normalizes_events_and_collects_usage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            server = PiRpcProcessTests()._server(root)
            workspace = root / "workspace"
            run_root = root / "run"
            workspace.mkdir()
            run_root.mkdir()
            prompt = root / "prompt.md"
            prompt.write_text("perform fixture", encoding="utf-8")
            observed: list[tuple[str, dict[str, object]]] = []
            runtime = PiRpcRuntime(
                {
                    "executable": sys.executable,
                    "entrypoint": str(server),
                    "model": "fixture/fixture-model",
                }
            )
            result = runtime.execute(
                workspace,
                prompt,
                run_root,
                timeout=10,
                event_sink=lambda event, data: observed.append((event, data)),
            )
            self.assertEqual(result.status, "completed")
            self.assertEqual((workspace / "result.md").read_text(encoding="utf-8"), "fixture output")
            self.assertEqual(result.metadata["usage"]["input"], 10)
            self.assertTrue(any(event == "agent.message.delta" for event, _ in observed))
            self.assertTrue(any(event == "reasoning.activity" for event, _ in observed))
            self.assertTrue(any(event == "runner.process.completed" for event, _ in observed))
            event_log = (run_root / "runtime.events.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("private fixture reasoning", event_log)

    def test_runtime_cancellation_reclaims_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / "waiting_pi.py"
            script.write_text(
                textwrap.dedent(
                    '''\
                    import json, sys, time
                    for line in sys.stdin:
                        command = json.loads(line)
                        if command["type"] == "get_state":
                            print(json.dumps({"id":command["id"],"type":"response","command":"get_state","success":True,"data":{"sessionId":"waiting"}}), flush=True)
                        elif command["type"] == "prompt":
                            print(json.dumps({"id":command["id"],"type":"response","command":"prompt","success":True}), flush=True)
                        elif command["type"] == "abort":
                            print(json.dumps({"id":command["id"],"type":"response","command":"abort","success":True}), flush=True)
                            print(json.dumps({"type":"agent_settled"}), flush=True)
                    '''
                ),
                encoding="utf-8",
            )
            workspace = root / "workspace"
            run_root = root / "run"
            workspace.mkdir()
            run_root.mkdir()
            prompt = root / "prompt.md"
            prompt.write_text("wait", encoding="utf-8")
            cancellation = threading.Event()
            cancellation.set()
            runtime = PiRpcRuntime(
                {"executable": sys.executable, "entrypoint": str(script), "model": "fixture/model"}
            )
            result = runtime.execute(workspace, prompt, run_root, timeout=5, cancel_event=cancellation)
            self.assertEqual(result.status, "cancelled")
            self.assertIsNotNone(result.returncode)


if __name__ == "__main__":
    unittest.main()
