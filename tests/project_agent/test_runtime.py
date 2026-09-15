from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import textwrap
import threading
import time
import unittest

from literary_engineering_studio.project_agent import (
    ProjectAgentActionDependencies,
    ProjectAgentDependencies,
    ProjectAgentToolDispatcher,
    ProjectAgentRuntime,
    ProjectAgentToolCall,
    ProjectAgentTurnRequest,
)


SCHEMA = "arcvellum/project-agent-bridge/v1"


class ProjectAgentRuntimeTests(unittest.TestCase):
    def test_read_dispatcher_maps_to_existing_service_dependencies(self):
        seen = []
        dependencies = ProjectAgentDependencies(
            project_overview=lambda root, args: seen.append((root, args)) or {"title": "测试作品"},
            project_search=lambda _root, _args: {},
            creation_observe=lambda _root, _args: {},
        )
        dispatcher = ProjectAgentToolDispatcher(Path("."), dependencies)

        result = dispatcher(ProjectAgentToolCall("request-1", "turn-1", "project_overview", {"focus": "progress"}))

        self.assertEqual(result, {"title": "测试作品"})
        self.assertEqual(seen[0][1], {"focus": "progress"})
        with self.assertRaisesRegex(ValueError, "not enabled"):
            dispatcher(ProjectAgentToolCall("request-2", "turn-1", "project_search", {}))

    def test_mutation_is_session_authorized_and_idempotent(self):
        calls = []
        dispatcher = ProjectAgentToolDispatcher(
            Path("."),
            _dependencies(),
            enabled=("project_record_direction",),
            actions=ProjectAgentActionDependencies(
                record_direction=lambda _root, args: calls.append(dict(args)) or {"ok": True},
                creation_control=lambda _root, _args: {},
            ),
            user_message="请把主角拒绝王位记录为创作方向。",
        )
        allowed = ProjectAgentToolCall(
            "request-3",
            "turn-1",
            "project_record_direction",
            {"message": "主角拒绝王位"},
        )

        self.assertEqual(dispatcher(allowed), {"ok": True})
        self.assertEqual(dispatcher(allowed), {"ok": True})
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            dispatcher(ProjectAgentToolCall(
                "request-4",
                "turn-1",
                "project_record_direction",
                {"message": "修改结局"},
            )),
            {"ok": True},
        )
        self.assertEqual(len(calls), 2)

    def test_dispatcher_resolves_a_registered_cross_work_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            (first / "project.yaml").write_text("title: First\n", encoding="utf-8")
            (second / "project.yaml").write_text("title: Second\n", encoding="utf-8")
            seen = []
            dependencies = ProjectAgentDependencies(
                project_overview=lambda target, _args: seen.append(target) or {"title": target.name},
                project_search=lambda _root, _args: {},
                creation_observe=lambda _root, _args: {},
                resolve_project=lambda _anchor, args: second if args.get("work_id") == "work-second" else first,
            )
            dispatcher = ProjectAgentToolDispatcher(first, dependencies)

            result = dispatcher(ProjectAgentToolCall(
                "request-cross-work",
                "turn-1",
                "project_overview",
                {"work_id": "work-second"},
            ))

            self.assertEqual(result["title"], "second")
            self.assertEqual(seen, [second.resolve()])

    def test_dispatches_one_allowed_tool_and_reaps_the_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = _script(root, """
                import json, sys
                schema = "arcvellum/project-agent-bridge/v1"
                def send(kind, turn, payload):
                    print(json.dumps({"schema": schema, "type": kind, "message_id": "child-" + kind, "turn_id": turn, "payload": payload}), flush=True)
                send("bridge.ready", "bridge", {"version": "test"})
                start = json.loads(sys.stdin.readline())
                turn = start["turn_id"]
                send("tool.call", turn, {"request_id": "request-1", "name": "project_overview", "arguments": {"focus": "progress"}})
                result = json.loads(sys.stdin.readline())
                answer = "stage=" + result["payload"]["result"]["stage"]
                send("turn.complete", turn, {"status": "completed", "answer": answer, "turns": 2, "toolCalls": 1})
            """)
            events: list[tuple[str, dict]] = []
            runtime = ProjectAgentRuntime((sys.executable, "-u", str(script)), cwd=root)
            request = _request()

            result = runtime.run_turn(
                request,
                lambda call: {
                    "stage": "review",
                    "focus": call.arguments.get("focus"),
                    "receipt": {"token": "receipt-1"},
                },
                timeout=3,
                event_sink=lambda event, data: events.append((event, data)),
            )

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.answer, "stage=review")
            self.assertEqual(result.tool_calls, 1)
            self.assertEqual(result.returncode, 0)
            self.assertIn("project_agent.tool.finished", [event for event, _ in events])
            finished = next(data for event, data in events if event == "project_agent.tool.finished")
            self.assertEqual(finished["receipt"], {"token": "receipt-1"})
            self.assertEqual(sorted(path.name for path in root.iterdir()), ["fake_project_agent.py"])

    def test_rejects_an_undeclared_tool(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = _script(root, """
                import json, sys, time
                schema = "arcvellum/project-agent-bridge/v1"
                def send(kind, turn, payload):
                    print(json.dumps({"schema": schema, "type": kind, "message_id": "child-" + kind, "turn_id": turn, "payload": payload}), flush=True)
                send("bridge.ready", "bridge", {})
                start = json.loads(sys.stdin.readline())
                send("tool.call", start["turn_id"], {"request_id": "request-1", "name": "shell_exec", "arguments": {}})
                time.sleep(5)
            """)
            runtime = ProjectAgentRuntime((sys.executable, "-u", str(script)), cwd=root)

            result = runtime.run_turn(_request(), lambda _call: {}, timeout=2)

            self.assertEqual(result.status, "failed")
            self.assertIn("undeclared tool", result.message)

    def test_malformed_output_fails_and_does_not_wait_for_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = _script(root, """
                import json, sys
                print(json.dumps({"schema": "arcvellum/project-agent-bridge/v1", "type": "bridge.ready", "message_id": "ready", "turn_id": "bridge", "payload": {}}), flush=True)
                sys.stdin.readline()
                print("not-json", flush=True)
            """)
            runtime = ProjectAgentRuntime((sys.executable, "-u", str(script)), cwd=root)
            started = time.monotonic()

            result = runtime.run_turn(_request(), lambda _call: {}, timeout=5)

            self.assertEqual(result.status, "failed")
            self.assertIn("valid JSON", result.message)
            self.assertLess(time.monotonic() - started, 2)

    def test_cancellation_terminates_and_reaps_a_waiting_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = _script(root, """
                import json, sys, time
                print(json.dumps({"schema": "arcvellum/project-agent-bridge/v1", "type": "bridge.ready", "message_id": "ready", "turn_id": "bridge", "payload": {}}), flush=True)
                sys.stdin.readline()
                time.sleep(30)
            """)
            runtime = ProjectAgentRuntime((sys.executable, "-u", str(script)), cwd=root)
            cancelled = threading.Event()
            threading.Timer(0.1, cancelled.set).start()
            started = time.monotonic()

            result = runtime.run_turn(_request(), lambda _call: {}, timeout=10, cancel_event=cancelled)

            self.assertEqual(result.status, "cancelled")
            self.assertLess(time.monotonic() - started, 3)


def _request() -> ProjectAgentTurnRequest:
    return ProjectAgentTurnRequest(
        session_id="session-1",
        turn_id="turn-1",
        prompt="项目现在进行到哪里？",
        system_prompt="根据工具事实自然回答。",
    )


def _dependencies() -> ProjectAgentDependencies:
    return ProjectAgentDependencies(
        project_overview=lambda _root, _args: {},
        project_search=lambda _root, _args: {},
        creation_observe=lambda _root, _args: {},
    )


def _script(root: Path, source: str) -> Path:
    path = root / "fake_project_agent.py"
    path.write_text(textwrap.dedent(source).strip() + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
