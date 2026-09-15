"""Project Agent application service with durable turn evidence."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
import json
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4

from .contracts import (
    ProjectAgentActionDependencies,
    ProjectAgentDependencies,
    ProjectAgentTurnRequest,
    ProjectAgentTurnResult,
)
from .factory import build_project_agent_runtime
from .delegated_goal import DelegatedGoal, DelegatedGoalObserver, goal_snapshot
from .prompt_policy import delegated_goal_followup_prompt, system_prompt, turn_prompt
from .runtime import ProjectAgentRuntime
from .session_state import active_turn_payload, turn_reference
from .tools import ProjectAgentToolDispatcher, available_action_tools, available_read_tools


RuntimeFactory = Callable[[dict[str, Any], Path], ProjectAgentRuntime]
EventSink = Callable[[str, dict[str, Any]], None]
PersonaLoader = Callable[[Path], dict[str, str]]
GoalRunReader = Callable[[str], dict[str, Any]]


class ProjectAgentService:
    """Coordinate one bounded Agent turn through existing Studio ports."""

    def __init__(
        self,
        config: dict[str, Any],
        *,
        sessions: Any,
        jobs: Any,
        dependencies: ProjectAgentDependencies,
        actions: ProjectAgentActionDependencies | None = None,
        runtime_factory: RuntimeFactory = build_project_agent_runtime,
        persona_loader: PersonaLoader | None = None,
        goal_run_reader: GoalRunReader | None = None,
        goal_poll_interval: float = 0.5,
    ) -> None:
        self.config = config
        self.sessions = sessions
        self.jobs = jobs
        self.dependencies = dependencies
        self.actions = actions
        self.runtime_factory = runtime_factory
        self.persona_loader = persona_loader
        resolved_goal_reader = goal_run_reader or getattr(jobs, "read_autopilot_run", None)
        self.goal_observer = (
            DelegatedGoalObserver(resolved_goal_reader, poll_interval=goal_poll_interval)
            if callable(resolved_goal_reader)
            else None
        )
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._turn_cancellations: dict[str, threading.Event] = {}
        self._turn_cancellations_guard = threading.Lock()
        application = config.get("application") if isinstance(config.get("application"), dict) else {}
        self.workspace_root = Path(
            str(application.get("projects_root") or application.get("data_root") or Path.cwd())
        ).expanduser().resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def create_session(self, project_root: Path | None = None, *, title: str = "项目 Agent") -> dict[str, Any]:
        root = self._session_root(project_root)
        overview = self._session_overview(root)
        digest = sha256(
            json.dumps(overview, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        return self.sessions.create_conversation_session(
            str(root),
            digest,
            title=title,
            session_kind="project-agent",
        )

    def list_sessions(self, project_root: Path | None = None, *, limit: int = 30) -> list[dict[str, Any]]:
        return self.sessions.list_conversation_sessions(
            str(self._session_root(project_root)),
            session_kind="project-agent",
            limit=limit,
        )

    def read_session(self, session_id: str) -> dict[str, Any]:
        session = self.sessions.read_conversation_session(session_id)
        self._require_project_agent(session)
        return {**session, "active_turn": self._active_turn(session)}

    def run_turn(
        self,
        session_id: str,
        message: str,
        *,
        timeout: float = 120.0,
        event_sink: EventSink | None = None,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        prepared = self._prepare_turn(session_id, message)
        return self._execute_prepared(
            prepared,
            timeout=timeout,
            event_sink=event_sink,
            cancel_event=cancel_event,
        )

    def start_turn(
        self,
        session_id: str,
        message: str,
        *,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        prepared = self._prepare_turn(session_id, message)
        cancellation = threading.Event()
        with self._turn_cancellations_guard:
            self._turn_cancellations[str(prepared["job_id"])] = cancellation

        def run() -> None:
            try:
                self._execute_prepared(
                    prepared,
                    timeout=timeout,
                    event_sink=None,
                    cancel_event=cancellation,
                )
            except Exception:
                # Failure evidence is already durable; the API reads it from the job.
                return
            finally:
                with self._turn_cancellations_guard:
                    self._turn_cancellations.pop(str(prepared["job_id"]), None)

        threading.Thread(
            target=run,
            name=f"arcvellum-project-agent-{prepared['turn_id']}",
            daemon=True,
        ).start()
        return {
            "session_id": session_id,
            "turn_id": prepared["turn_id"],
            "job_id": prepared["job_id"],
            "status": "queued",
        }

    def cancel_turn(self, job_id: str) -> dict[str, Any]:
        job = self.jobs.read(job_id)
        request = job.get("request") if isinstance(job.get("request"), dict) else {}
        if request.get("kind") != "project-agent-turn":
            raise ValueError("job does not belong to the Project Agent")
        status = str(job.get("status") or "")
        if status not in {"queued", "running", "stopping"}:
            return {"job_id": job_id, "status": status, "stopped": False}
        with self._turn_cancellations_guard:
            cancellation = self._turn_cancellations.get(job_id)
            if cancellation is not None:
                cancellation.set()
        next_status = "cancelled" if status == "queued" else "stopping"
        updates: dict[str, Any] = {"status": next_status}
        if next_status == "cancelled":
            updates.update(
                result={
                    "status": "cancelled",
                    "answer": "",
                    "turn_id": str(request.get("turn_id") or ""),
                    "job_id": job_id,
                    "tool_calls": 0,
                    "message": "Project Agent turn cancelled before execution",
                },
                error="Project Agent turn cancelled before execution",
            )
        self.jobs.update(job_id, **updates)
        self.jobs.append_event(job_id, "project_agent.turn.cancelling", {"job_id": job_id})
        return {"job_id": job_id, "status": next_status, "stopped": cancellation is not None}

    def _prepare_turn(self, session_id: str, message: str) -> dict[str, Any]:
        prompt = str(message or "").strip()
        if not prompt:
            raise ValueError("Project Agent message is required")
        if len(prompt) > 20_000:
            raise ValueError("Project Agent message is too long")
        session = self.read_session(session_id)
        root = Path(str(session["project_root"])).expanduser().resolve()
        turn_id = f"turn-{uuid4()}"
        job = self.jobs.create(
            {
                "kind": "project-agent-turn",
                "project_root": str(root),
                "session_id": session_id,
                "turn_id": turn_id,
            }
        )
        job_id = str(job["job_id"])
        return {
            "session": session,
            "session_id": session_id,
            "root": root,
            "turn_id": turn_id,
            "job_id": job_id,
            "message": prompt,
        }

    def _execute_prepared(
        self,
        prepared: dict[str, Any],
        *,
        timeout: float,
        event_sink: EventSink | None,
        cancel_event: threading.Event | None,
    ) -> dict[str, Any]:
        session = prepared["session"]
        session_id = str(prepared["session_id"])
        root = prepared["root"]
        turn_id = str(prepared["turn_id"])
        job_id = str(prepared["job_id"])
        message = str(prepared["message"])
        delegated_goal: list[DelegatedGoal | None] = [None]

        def emit(event: str, data: dict[str, Any]) -> None:
            payload = {"session_id": session_id, "turn_id": turn_id, **data}
            self.jobs.append_event(job_id, event, payload)
            binding = DelegatedGoal.from_tool_event(event, data)
            if binding is not None:
                delegated_goal[0] = binding
            if event_sink is not None:
                event_sink(event, payload)

        with self._session_lock(session_id):
            try:
                result = self._run_claimed_turn(
                    session_id=session_id,
                    root=root,
                    turn_id=turn_id,
                    job_id=job_id,
                    message=message,
                    timeout=timeout,
                    cancel_event=cancel_event,
                    emit=emit,
                    delegated_goal=delegated_goal,
                )
                return self._finish(job_id, session_id, result, emit)
            except Exception as exc:
                emit("project_agent.error", {"message": str(exc)[:2000]})
                self.jobs.update(job_id, status="runtime_failed", error=str(exc)[:2000])
                raise

    def _run_claimed_turn(
        self,
        *,
        session_id: str,
        root: Path,
        turn_id: str,
        job_id: str,
        message: str,
        timeout: float,
        cancel_event: threading.Event | None,
        emit: EventSink,
        delegated_goal: list[DelegatedGoal | None],
    ) -> ProjectAgentTurnResult:
        if cancel_event is not None and cancel_event.is_set():
            receipt = self._cancel_before_start(job_id, turn_id)
            return ProjectAgentTurnResult("cancelled", "", turn_id, None, 0, receipt["message"])
        worker_id = f"project-agent-{uuid4()}"
        if not self.jobs.claim(job_id, worker_id, lease_seconds=max(30, int(timeout) + 10)):
            if str(self.jobs.read(job_id).get("status") or "") == "cancelled":
                receipt = self._cancel_before_start(job_id, turn_id)
                return ProjectAgentTurnResult("cancelled", "", turn_id, None, 0, receipt["message"])
            raise RuntimeError("Project Agent turn could not claim its durable job")
        session = self.read_session(session_id)
        self.sessions.append_session_message(
            session_id,
            "user",
            {"text": message, "turn_id": turn_id, "job_id": job_id},
        )
        emit("project_agent.turn.started", {"job_id": job_id})
        request = self._turn_request(session_id, turn_id, root, message, session)
        result = self._run_runtime(root, message, request, timeout, cancel_event, emit)
        return self._continue_delegated_goals(
            result=result,
            delegated_goal=delegated_goal,
            request=request,
            root=root,
            message=message,
            job_id=job_id,
            worker_id=worker_id,
            timeout=timeout,
            cancel_event=cancel_event,
            emit=emit,
        )

    def _turn_request(
        self,
        session_id: str,
        turn_id: str,
        root: Path,
        message: str,
        session: dict[str, Any],
    ) -> ProjectAgentTurnRequest:
        allowed_tools = (*available_read_tools(self.dependencies), *available_action_tools(self.actions))
        persona = (
            self.persona_loader(root)
            if self.persona_loader is not None
            and (root != self.workspace_root or (root / "project.yaml").is_file())
            else {}
        )
        return ProjectAgentTurnRequest(
            session_id=session_id,
            turn_id=turn_id,
            prompt=turn_prompt(message, session),
            system_prompt=system_prompt(persona, write_enabled=self.actions is not None),
            allowed_tools=allowed_tools,
            max_turns=6,
            max_tool_calls=8,
        )

    def _run_runtime(
        self,
        root: Path,
        message: str,
        request: ProjectAgentTurnRequest,
        timeout: float,
        cancel_event: threading.Event | None,
        emit: EventSink,
    ) -> ProjectAgentTurnResult:
        runtime = self.runtime_factory(self.config, root)
        dispatcher = ProjectAgentToolDispatcher(
            root,
            self.dependencies,
            enabled=request.allowed_tools,
            actions=self.actions,
            user_message=message,
        )
        return runtime.run_turn(
            request,
            dispatcher,
            timeout=timeout,
            cancel_event=cancel_event,
            event_sink=emit,
        )

    def _continue_delegated_goals(
        self,
        *,
        result: ProjectAgentTurnResult,
        delegated_goal: list[DelegatedGoal | None],
        request: ProjectAgentTurnRequest,
        root: Path,
        message: str,
        job_id: str,
        worker_id: str,
        timeout: float,
        cancel_event: threading.Event | None,
        emit: EventSink,
    ) -> ProjectAgentTurnResult:
        while delegated_goal[0] is not None and delegated_goal[0].needs_observation:
            if self.goal_observer is None:
                raise RuntimeError("Project Agent goal observer is unavailable")
            current_goal = delegated_goal[0]
            delegated_goal[0] = None
            assert current_goal is not None
            emit("project_agent.goal.waiting", {
                "run_id": current_goal.run_id,
                "work_id": current_goal.work_id,
                "operation": current_goal.operation,
            })
            self.jobs.update(job_id, result={
                "status": "delegated_wait",
                "turn_id": request.turn_id,
                "job_id": job_id,
                "run_id": current_goal.run_id,
                "work_id": current_goal.work_id,
            })
            terminal_run = self.goal_observer.wait(
                current_goal,
                cancel_event=cancel_event,
                event_sink=emit,
                heartbeat=lambda: self.jobs.heartbeat(job_id, worker_id, lease_seconds=120),
            )
            if terminal_run is None:
                return ProjectAgentTurnResult(
                    "cancelled", "", request.turn_id, None, result.tool_calls,
                    "Project Agent stopped waiting; the background goal was left intact",
                )
            emit("project_agent.goal.terminal", goal_snapshot(terminal_run))
            emit("project_agent.goal.followup.started", {"run_id": current_goal.run_id})
            followup = ProjectAgentTurnRequest(
                session_id=request.session_id,
                turn_id=request.turn_id,
                prompt=delegated_goal_followup_prompt(message, result.answer, terminal_run),
                system_prompt=request.system_prompt,
                allowed_tools=request.allowed_tools,
                max_turns=request.max_turns,
                max_tool_calls=request.max_tool_calls,
            )
            result = self._run_runtime(root, message, followup, timeout, cancel_event, emit)
        return result

    def _cancel_before_start(self, job_id: str, turn_id: str) -> dict[str, Any]:
        receipt = {
            "status": "cancelled",
            "answer": "",
            "turn_id": turn_id,
            "job_id": job_id,
            "tool_calls": 0,
            "message": "Project Agent turn cancelled before execution",
        }
        self.jobs.update(job_id, status="cancelled", result=receipt, error=receipt["message"])
        return receipt

    def _session_root(self, project_root: Path | None) -> Path:
        if project_root is None:
            return self.workspace_root
        return project_root.expanduser().resolve()

    def _session_overview(self, root: Path) -> dict[str, Any]:
        if (root / "project.yaml").is_file():
            return dict(self.dependencies.project_overview(root, {"focus": "session-start"}))
        if self.dependencies.workspace_catalog is None:
            return {"scope": "workspace"}
        return dict(self.dependencies.workspace_catalog(root, {"focus": "session-start"}))

    def _finish(
        self,
        job_id: str,
        session_id: str,
        result: ProjectAgentTurnResult,
        emit: EventSink,
    ) -> dict[str, Any]:
        if result.answer:
            self.sessions.append_session_message(
                session_id,
                "assistant",
                {"text": result.answer, "turn_id": result.turn_id, "job_id": job_id},
            )
        job_status = "complete" if result.status == "completed" else (
            "cancelled" if result.status == "cancelled" else "runtime_failed"
        )
        receipt = {
            "status": result.status,
            "answer": result.answer,
            "turn_id": result.turn_id,
            "job_id": job_id,
            "tool_calls": result.tool_calls,
            "message": result.message,
        }
        emit("project_agent.result", receipt)
        self.jobs.update(
            job_id,
            status=job_status,
            result=receipt,
            error="" if job_status == "complete" else result.message,
        )
        return receipt

    def _session_lock(self, session_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(session_id, threading.Lock())

    def _active_turn(self, session: dict[str, Any]) -> dict[str, Any] | None:
        """Resolve the latest durable turn without adding a second session state store."""

        for message in reversed(list(session.get("messages") or [])):
            reference = turn_reference(message)
            if reference is None:
                continue
            job_id, turn_id = reference
            try:
                job = self.jobs.read(job_id)
            except (FileNotFoundError, ValueError):
                return None
            return active_turn_payload(job, job_id, turn_id, str(session.get("session_id") or ""))
        return None

    @staticmethod
    def _require_project_agent(session: dict[str, Any]) -> None:
        if session.get("session_kind") != "project-agent":
            raise ValueError("session does not belong to the Project Agent")


__all__ = ["ProjectAgentService"]
