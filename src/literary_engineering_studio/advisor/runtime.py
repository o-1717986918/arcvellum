"""Pi Worker lifecycle for read-only advisor conversations."""

from __future__ import annotations

from pathlib import Path
import threading
from typing import Any, Callable

from ..runtime.role_conversation import RoleConversationGateway
from .answer_parser import parse_answer
from .streaming import PublicAnswerStream


class AdvisorRuntimeExecutor:
    """Run advisor turns through the embedded, role-scoped Pi Worker."""

    def __init__(
        self,
        config: dict[str, Any],
        *,
        runtime_pool: Any = None,
        data_root: Path,
        remote_sessions: dict[str, tuple[str, str, int]],
        remote_lock: threading.RLock,
        session_event_tracker: Callable[..., object],
    ) -> None:
        self.config = config
        self.data_root = data_root
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


__all__ = ["AdvisorRuntimeExecutor"]
