from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.persistence.job_store import JobStore
from literary_engineering_studio.project_agent import (
    ProjectAgentActionDependencies,
    ProjectAgentDependencies,
    ProjectAgentService,
    ProjectAgentToolCall,
    ProjectAgentTurnResult,
)


class _Runtime:
    def __init__(self, result: ProjectAgentTurnResult):
        self.result = result
        self.requests = []

    def run_turn(self, request, tool_handler, **kwargs):
        self.requests.append(request)
        overview = tool_handler(_tool_call(request.turn_id))
        kwargs["event_sink"]("project_agent.event", {"kind": "text", "text": "正在查看项目。"})
        self.result = ProjectAgentTurnResult(
            self.result.status,
            self.result.answer.replace("{stage}", str(overview["stage"])),
            request.turn_id,
            0,
            1,
            self.result.message,
        )
        return self.result


class _ActionRuntime:
    def __init__(self):
        self.requests = []

    def run_turn(self, request, tool_handler, **_kwargs):
        self.requests.append(request)
        result = tool_handler(ProjectAgentToolCall(
            "request-action",
            request.turn_id,
            "project_record_direction",
            {"message": "主角拒绝王位"},
        ))
        return ProjectAgentTurnResult(
            "completed",
            f"已记录：{result['message']}",
            request.turn_id,
            0,
            1,
        )


class ProjectAgentServiceTests(unittest.TestCase):
    def test_turn_persists_messages_job_and_stream_events(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            runtime = _Runtime(ProjectAgentTurnResult("completed", "当前阶段是 {stage}。", "unused", 0, 1))
            service = ProjectAgentService(
                {},
                sessions=store.sessions,
                jobs=store,
                dependencies=_dependencies(),
                runtime_factory=lambda _config, _root: runtime,
                persona_loader=lambda _root: {"name": "冷面读者", "prompt": "只对真实阅读感受负责。"},
            )
            session = service.create_session(root, title="测试会话")
            streamed = []

            result = service.run_turn(
                session["session_id"],
                "项目到哪了？",
                event_sink=lambda event, data: streamed.append((event, data)),
            )

            restored = service.read_session(session["session_id"])
            self.assertEqual([item["role"] for item in restored["messages"]], ["user", "assistant"])
            self.assertEqual(result["answer"], "当前阶段是 review。")
            self.assertIn("project_agent.event", [event for event, _ in streamed])
            events = store.events_since(result["job_id"])
            self.assertIn("project_agent.result", [item["event"] for item in events])
            self.assertEqual(store.read(result["job_id"])["status"], "complete")
            self.assertEqual(
                runtime.requests[0].allowed_tools,
                ("project_overview", "project_search", "creation_observe"),
            )
            self.assertIn("冷面读者", runtime.requests[0].system_prompt)

    def test_advisor_session_cannot_be_used_as_project_agent(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            session = store.create_advisor_session(temporary, "digest")
            service = ProjectAgentService(
                {},
                sessions=store.sessions,
                jobs=store,
                dependencies=_dependencies(),
                runtime_factory=lambda _config, _root: None,
            )

            with self.assertRaisesRegex(ValueError, "does not belong"):
                service.run_turn(session["session_id"], "继续")

    def test_explicit_user_request_reaches_bounded_action_port(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            runtime = _ActionRuntime()
            writes = []
            service = ProjectAgentService(
                {},
                sessions=store.sessions,
                jobs=store,
                dependencies=_dependencies(),
                actions=ProjectAgentActionDependencies(
                    record_direction=lambda _root, args: writes.append(dict(args)) or {
                        "message": str(args["message"]),
                        "receipt": {"token": "receipt-1"},
                    },
                    creation_control=lambda _root, _args: {},
                ),
                runtime_factory=lambda _config, _root: runtime,
            )
            session = service.create_session(root)

            result = service.run_turn(session["session_id"], "请记录为创作方向：主角拒绝王位。")

            self.assertEqual(result["answer"], "已记录：主角拒绝王位")
            self.assertEqual(len(writes), 1)
            self.assertIn("project_record_direction", runtime.requests[0].allowed_tools)
            self.assertIn("不要请求用户批准", runtime.requests[0].system_prompt)
            self.assertIn("lean-v2", runtime.requests[0].system_prompt)


def _dependencies() -> ProjectAgentDependencies:
    return ProjectAgentDependencies(
        project_overview=lambda _root, _args: {"stage": "review"},
        project_search=lambda _root, _args: {},
        creation_observe=lambda _root, _args: {},
    )


def _tool_call(turn_id):
    from literary_engineering_studio.project_agent import ProjectAgentToolCall

    return ProjectAgentToolCall("request-1", turn_id, "project_overview", {"focus": "progress"})


if __name__ == "__main__":
    unittest.main()
