from pathlib import Path
import tempfile
import threading
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


class _DelegatingRuntime:
    def __init__(self):
        self.requests = []

    def run_turn(self, request, _tool_handler, **kwargs):
        self.requests.append(request)
        if len(self.requests) == 1:
            kwargs["event_sink"](
                "project_agent.tool.finished",
                {
                    "name": "project_goal_manage",
                    "request_id": "goal-1",
                    "ok": True,
                    "receipt": {
                        "operation": "goal_start",
                        "run_id": "autopilot-1",
                        "run_status": "running",
                        "work_id": "work-1",
                    },
                },
            )
            return ProjectAgentTurnResult(
                "completed",
                "已经接手，我会继续推进。",
                request.turn_id,
                0,
                1,
            )
        return ProjectAgentTurnResult(
            "completed",
            "全书已经完成并通过交付复核。",
            request.turn_id,
            0,
            2,
        )


class _CheckpointRuntime:
    def __init__(self):
        self.requests = []

    def run_turn(self, request, _tool_handler, **kwargs):
        self.requests.append(request)
        if len(self.requests) in (1, 2):
            kwargs["event_sink"]("project_agent.tool.finished", {
                "name": "project_goal_manage", "ok": True,
                "receipt": {
                    "operation": "goal_start" if len(self.requests) == 1 else "goal_recover",
                    "run_id": "autopilot-1", "run_status": "running", "work_id": "work-1",
                },
            })
        return ProjectAgentTurnResult("completed", "目标完成。", request.turn_id, 0, 1)


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
            self.assertEqual(restored["messages"][0]["payload"]["job_id"], result["job_id"])
            self.assertEqual(restored["messages"][0]["payload"]["turn_id"], result["turn_id"])
            self.assertIsNone(restored["active_turn"])
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
            self.assertIn("故事实际写到哪里", runtime.requests[0].system_prompt)
            self.assertIn("按用户问题与已有正文选择相关事实", runtime.requests[0].system_prompt)
            self.assertIn("人格决定观察角度和语气", runtime.requests[0].system_prompt)
            self.assertIn("continuity_status 为 not_recorded", runtime.requests[0].system_prompt)
            self.assertIn("completed_beats.actual_prose_tail", runtime.requests[0].system_prompt)
            self.assertIn("不凭印象补全", runtime.requests[0].system_prompt)
            self.assertIn("避免连续使用机械", runtime.requests[0].system_prompt)
            self.assertIn("正在进行", runtime.requests[0].system_prompt)
            self.assertIn("无正式正文时直接说尚未落笔", runtime.requests[0].system_prompt)
            self.assertIn("仅要求检查或修复时先核验并汇报，不擅自启动无限创作", runtime.requests[0].system_prompt)
            self.assertIn("stop_after_formal_units", runtime.requests[0].system_prompt)

    def test_read_session_exposes_only_its_latest_active_turn(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            service = ProjectAgentService(
                {},
                sessions=store.sessions,
                jobs=store,
                dependencies=_dependencies(),
                runtime_factory=lambda _config, _root: None,
            )
            session = service.create_session(root)
            job = store.create({
                "kind": "project-agent-turn",
                "project_root": str(root),
                "session_id": session["session_id"],
                "turn_id": "turn-recover",
            })
            self.assertTrue(store.claim(job["job_id"], "project-agent-test"))
            store.append_session_message(
                session["session_id"],
                "user",
                {"text": "继续", "turn_id": "turn-recover", "job_id": job["job_id"]},
            )

            active = service.read_session(session["session_id"])["active_turn"]

            self.assertEqual(active["job_id"], job["job_id"])
            self.assertEqual(active["turn_id"], "turn-recover")
            self.assertEqual(active["status"], "running")

            store.update(job["job_id"], status="interrupted")
            self.assertIsNone(service.read_session(session["session_id"])["active_turn"])

    def test_workspace_session_can_start_without_a_selected_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = JobStore(root / "studio.sqlite3")
            dependencies = _dependencies()
            dependencies = ProjectAgentDependencies(
                dependencies.project_overview,
                dependencies.project_search,
                dependencies.creation_observe,
                workspace_catalog=lambda _root, _args: {"works": [], "count": 0},
            )
            service = ProjectAgentService(
                {"application": {"projects_root": str(root / "Works")}},
                sessions=store.sessions,
                jobs=store,
                dependencies=dependencies,
                runtime_factory=lambda _config, _root: None,
            )

            session = service.create_session(None, title="作品库总控")

            self.assertEqual(session["project_root"], str((root / "Works").resolve()))
            self.assertEqual(service.list_sessions(None)[0]["session_id"], session["session_id"])

    def test_cancelled_queued_turn_never_becomes_a_runtime_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            service = ProjectAgentService(
                {},
                sessions=store.sessions,
                jobs=store,
                dependencies=_dependencies(),
                runtime_factory=lambda _config, _root: None,
            )
            session = service.create_session(root)
            prepared = service._prepare_turn(session["session_id"], "停止这个回答")
            cancellation = threading.Event()
            cancellation.set()

            stopped = service.cancel_turn(prepared["job_id"])
            result = service._execute_prepared(
                prepared,
                timeout=30,
                event_sink=None,
                cancel_event=cancellation,
            )

            self.assertEqual(stopped["status"], "cancelled")
            self.assertEqual(result["status"], "cancelled")
            self.assertEqual(store.read(prepared["job_id"])["status"], "cancelled")

    def test_delegated_goal_keeps_the_same_turn_open_and_reports_its_terminal_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            runtime = _DelegatingRuntime()
            snapshots = iter([
                {
                    "run_id": "autopilot-1",
                    "status": "running",
                    "current_route": "scene-development",
                    "current_task_id": "scene-0001",
                    "tasks_completed": 3,
                },
                {
                    "run_id": "autopilot-1",
                    "status": "complete",
                    "current_route": "release",
                    "current_task_id": "",
                    "tasks_completed": 12,
                },
            ])
            service = ProjectAgentService(
                {},
                sessions=store.sessions,
                jobs=store,
                dependencies=_dependencies(),
                actions=ProjectAgentActionDependencies(
                    record_direction=lambda _root, _args: {},
                    creation_control=lambda _root, _args: {},
                    manage_goal=lambda _root, _args: {},
                ),
                runtime_factory=lambda _config, _root: runtime,
                goal_run_reader=lambda _run_id: next(snapshots),
                goal_poll_interval=0.001,
            )
            session = service.create_session(root)

            result = service.run_turn(session["session_id"], "完成这部作品并交付")

            self.assertEqual(result["answer"], "全书已经完成并通过交付复核。")
            self.assertEqual(len(runtime.requests), 2)
            self.assertIn("同一条用户消息", runtime.requests[1].prompt)
            self.assertIn("主要人物处境", runtime.requests[1].prompt)
            restored = service.read_session(session["session_id"])
            self.assertEqual([item["role"] for item in restored["messages"]], ["user", "assistant"])
            events = [item["event"] for item in store.events_since(result["job_id"])]
            self.assertIn("project_agent.goal.waiting", events)
            self.assertIn("project_agent.goal.progress", events)
            self.assertIn("project_agent.goal.terminal", events)
            self.assertIn("project_agent.goal.followup.started", events)
            self.assertEqual(store.read(result["job_id"])["status"], "complete")

    def test_scene_checkpoint_reenters_agent_then_resumes_same_goal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            store = JobStore(Path(temporary) / "studio.sqlite3")
            runtime = _CheckpointRuntime()
            snapshots = iter([
                {"run_id": "autopilot-1", "status": "paused", "stop_reason": "scene-editorial-checkpoint",
                 "current_task_id": "lean-scene:scene_0001:committed"},
                {"run_id": "autopilot-1", "status": "complete", "stop_reason": ""},
            ])
            service = ProjectAgentService(
                {}, sessions=store.sessions, jobs=store,
                dependencies=_dependencies(),
                actions=ProjectAgentActionDependencies(
                    record_direction=lambda _root, _args: {}, creation_control=lambda _root, _args: {},
                    manage_goal=lambda _root, _args: {},
                ),
                runtime_factory=lambda _config, _root: runtime,
                goal_run_reader=lambda _run_id: next(snapshots), goal_poll_interval=0.001,
            )
            session = service.create_session(root)
            result = service.run_turn(session["session_id"], "继续写完")
            self.assertEqual(result["answer"], "目标完成。")
            self.assertEqual(len(runtime.requests), 3)
            self.assertIn("场间编辑检查点", runtime.requests[1].prompt)
            self.assertIn("macro_plan", runtime.requests[1].prompt)


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
