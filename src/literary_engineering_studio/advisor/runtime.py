"""Runtime-neutral lifecycle for read-only advisor conversations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Any, Callable

from ..integrations.opencode.opencode_binary import locate_opencode
from ..integrations.opencode.opencode_server import OpenCodeServer
from ..observability.runtime_events import normalize_opencode_event
from ..process_manager import ProcessManager
from ..runtime.role_conversation import RoleConversationGateway
from ..runtime.runtime_selection import runtime_for_role
from .answer_parser import parse_answer
from .streaming import PublicAnswerStream


@dataclass
class AdvisorRuntimeResources:
    manager: ProcessManager | None
    server: OpenCodeServer | None
    handle: Any
    lease: Any
    client: Any

    def close(self, runtime_pool: Any) -> None:
        if self.lease is not None:
            runtime_pool.release(self.lease)
        elif self.handle is not None and self.server is not None:
            self.server.stop(self.handle)
        if self.manager is not None:
            self.manager.shutdown()


class AdvisorRuntimeExecutor:
    def __init__(
        self,
        config: dict[str, Any],
        *,
        runtime_pool: Any,
        data_root: Path,
        remote_sessions: dict[str, tuple[str, str, int]],
        remote_lock: threading.RLock,
        session_event_tracker: Callable[..., object],
    ) -> None:
        self.config = config
        self.runtime_pool = runtime_pool
        self.data_root = data_root
        self.remote_sessions = remote_sessions
        self.remote_lock = remote_lock
        self.session_event_tracker = session_event_tracker

    def run(
        self,
        workspace: Path,
        *,
        project_root: Path,
        studio_session_id: str,
        snapshot_digest: str,
        prompt_factory: Callable[[bool], str],
        timeout: int,
        event_sink: Callable[[str, dict[str, Any]], None] | None,
    ) -> dict[str, Any]:
        if runtime_for_role(self.config, "advisor") == "pi-worker":
            return self._run_pi(
                workspace,
                project_root=project_root,
                studio_session_id=studio_session_id,
                prompt_factory=prompt_factory,
                timeout=timeout,
                event_sink=event_sink,
            )
        executable, model = self._runner_config()
        run_root = self.data_root / "advisor" / "runs" / f"run-{int(time.time() * 1000)}"
        run_root.mkdir(parents=True, exist_ok=False)
        resources = self._open_resources(executable, model, workspace, run_root)
        stop = threading.Event()
        event_thread: threading.Thread | None = None
        remote_id = ""
        session_idle = False
        observe = self._observer(project_root, studio_session_id)
        try:
            remote_id, can_resume = self._remote_session(resources, studio_session_id, snapshot_digest, model, observe)
            observe("advisor.session.started", {
                "session_id": remote_id,
                "model": model,
                "public_message": "项目顾问正在阅读当前只读快照并组织答复。",
            })
            stream = PublicAnswerStream(event_sink)
            event_thread = self._start_events(resources.client, remote_id, stop, stream, event_sink)
            resources.client.prompt_async(
                remote_id,
                text=prompt_factory(can_resume),
                model=model,
                agent="project-advisor",
            )
            self._wait_until_idle(resources.client, remote_id, timeout)
            result = parse_answer(_last_assistant_text(resources.client.messages(remote_id)))
            stream.finish(result["message"])
            observe("advisor.session.idle", {"session_id": remote_id, "model": model})
            session_idle = True
            return result
        except Exception:
            if remote_id and not session_idle:
                observe("advisor.session.finished", {
                    "session_id": remote_id,
                    "model": model,
                    "status": "failed",
                    "reason": "advisor_error",
                })
            raise
        finally:
            stop.set()
            if event_thread is not None:
                event_thread.join(timeout=3)
            resources.close(self.runtime_pool)

    def _run_pi(
        self,
        workspace: Path,
        *,
        project_root: Path,
        studio_session_id: str,
        prompt_factory: Callable[[bool], str],
        timeout: int,
        event_sink: Callable[[str, dict[str, Any]], None] | None,
    ) -> dict[str, Any]:
        stream = PublicAnswerStream(event_sink)
        gateway = RoleConversationGateway(self.config, data_root=self.data_root)

        def observe(event: str, data: dict[str, Any]) -> None:
            if event == "agent.message.delta":
                stream.feed(str(data.get("text") or ""))
            elif event == "usage.updated" and event_sink is not None:
                event_sink("advisor.usage", data)
            elif event == "runner.warning" and event_sink is not None:
                event_sink("advisor.notice", {"message": "顾问连接正在恢复，请稍候。"})

        self.session_event_tracker(
            project_root=str(project_root),
            role="advisor",
            runtime="pi-worker",
            controller_id=studio_session_id,
            event="advisor.session.started",
            data={"public_message": "项目顾问正在阅读当前只读快照并组织答复。"},
        )
        try:
            conversation = gateway.run(
                workspace,
                prompt_factory(False),
                role="advisor",
                timeout=timeout,
                event_sink=observe,
            )
            result = parse_answer(conversation.answer)
            stream.finish(result["message"])
            self.session_event_tracker(
                project_root=str(project_root),
                role="advisor",
                runtime="pi-worker",
                controller_id=studio_session_id,
                event="advisor.session.finished",
                data={
                    "session_id": conversation.run_id,
                    "model": conversation.model,
                    "status": "complete",
                },
            )
            return result
        except Exception:
            self.session_event_tracker(
                project_root=str(project_root),
                role="advisor",
                runtime="pi-worker",
                controller_id=studio_session_id,
                event="advisor.session.finished",
                data={"status": "failed", "reason": "advisor_error"},
            )
            raise

    def _runner_config(self) -> tuple[Path, str]:
        raw_settings = self.config.get("agent_runners", {}).get("opencode", {})
        settings = raw_settings if isinstance(raw_settings, dict) else {}
        executable = locate_opencode(settings)
        if executable is None:
            raise RuntimeError("bundled OpenCode Runner is not installed")
        models = settings.get("models") if isinstance(settings.get("models"), dict) else {}
        model = str(models.get("advisor") or settings.get("advisor_model") or settings.get("model") or "").strip()
        if "/" not in model:
            raise RuntimeError("select an OpenCode provider/model before using the advisor")
        return executable, model

    def _open_resources(self, executable: Path, model: str, workspace: Path, run_root: Path) -> AdvisorRuntimeResources:
        if self.runtime_pool is not None:
            lease = self.runtime_pool.acquire("advisor", workspace, model=model)
            return AdvisorRuntimeResources(None, None, None, lease, lease.client)
        manager = ProcessManager(run_root / "logs")
        server = OpenCodeServer(manager, executable=executable, shared_data_root=self.data_root)
        try:
            handle = server.start(
                component_id=f"advisor-{run_root.name}",
                workspace=workspace,
                run_root=run_root,
                role="advisor",
                model=model,
            )
        except Exception:
            manager.shutdown()
            raise
        return AdvisorRuntimeResources(manager, server, handle, None, handle.client)

    def _observer(self, project_root: Path, studio_session_id: str) -> Callable[[str, dict[str, Any]], None]:
        def observe(event: str, data: dict[str, Any]) -> None:
            self.session_event_tracker(
                project_root=str(project_root),
                role="advisor",
                runtime="opencode",
                controller_id=studio_session_id,
                event=event,
                data=data,
            )
        return observe

    def _remote_session(
        self,
        resources: AdvisorRuntimeResources,
        studio_session_id: str,
        snapshot_digest: str,
        model: str,
        observe: Callable[[str, dict[str, Any]], None],
    ) -> tuple[str, bool]:
        with self.remote_lock:
            previous = self.remote_sessions.get(studio_session_id)
        can_resume = bool(
            resources.lease is not None
            and previous
            and previous[0] == snapshot_digest
            and previous[2] == resources.lease.generation
        )
        remote_id = previous[1] if can_resume and previous else ""
        if not remote_id:
            self._archive_previous(previous, model, observe)
            remote_id = str(resources.client.create_session("Studio 项目顾问").get("id") or "")
            if resources.lease is not None and remote_id:
                with self.remote_lock:
                    self.remote_sessions[studio_session_id] = (
                        snapshot_digest,
                        remote_id,
                        resources.lease.generation,
                    )
        if not remote_id:
            raise RuntimeError("OpenCode did not create an advisor session")
        if not can_resume:
            observe("advisor.session.created", {"session_id": remote_id, "model": model})
        return remote_id, can_resume

    @staticmethod
    def _archive_previous(
        previous: tuple[str, str, int] | None,
        model: str,
        observe: Callable[[str, dict[str, Any]], None],
    ) -> None:
        if previous and previous[1]:
            observe("advisor.session.finished", {
                "session_id": previous[1],
                "model": model,
                "status": "complete",
                "public_message": "项目快照已变化，旧顾问会话已归档。",
            })

    @staticmethod
    def _start_events(
        client: Any,
        remote_id: str,
        stop: threading.Event,
        stream: PublicAnswerStream,
        event_sink: Callable[[str, dict[str, Any]], None] | None,
    ) -> threading.Thread | None:
        if event_sink is None:
            return None

        def consume() -> None:
            try:
                for raw in client.events(stop):
                    for name, data in normalize_opencode_event(raw, session_id=remote_id):
                        if name == "agent.message.delta":
                            stream.feed(str(data.get("text") or ""))
                        elif name == "usage.updated":
                            event_sink("advisor.usage", data)
                        elif name == "runner.warning":
                            event_sink("advisor.notice", {"message": "顾问连接正在恢复，请稍候。"})
            except Exception as exc:
                if not stop.is_set():
                    event_sink("advisor.notice", {"message": f"实时输出暂时中断：{exc}"})

        thread = threading.Thread(target=consume, name=f"arcvellum-advisor-events-{remote_id}", daemon=True)
        thread.start()
        return thread

    @staticmethod
    def _wait_until_idle(client: Any, remote_id: str, timeout: int) -> None:
        deadline = time.monotonic() + max(10, min(600, int(timeout)))
        seen_busy = False
        while time.monotonic() < deadline:
            state = client.session_status().get(remote_id, {})
            kind = str(state.get("type") or "") if isinstance(state, dict) else ""
            if kind in {"busy", "retry"}:
                seen_busy = True
            if seen_busy and kind in {"idle", ""}:
                return
            time.sleep(0.2)
        client.abort(remote_id)
        raise RuntimeError("advisor answer timed out")


def _last_assistant_text(messages: list[dict[str, Any]]) -> str:
    result = ""
    for message in messages:
        info = message.get("info") if isinstance(message.get("info"), dict) else {}
        if info.get("role") != "assistant":
            continue
        text = "".join(
            str(part.get("text") or "")
            for part in message.get("parts") or []
            if isinstance(part, dict) and part.get("type") == "text"
        )
        if text:
            result = text
    if not result:
        raise RuntimeError("advisor returned no answer")
    return result


__all__ = ["AdvisorRuntimeExecutor"]
