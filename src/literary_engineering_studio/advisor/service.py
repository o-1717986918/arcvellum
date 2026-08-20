"""Read-only project advisor application service."""

from __future__ import annotations

from pathlib import Path
import threading
from typing import Any, Callable

from ..application.persistence_ports import SessionRepositoryPort
from ..observability.agent_session_tracking import track_agent_session_event
from .advisor_personas import active_persona
from .advisor_snapshot import create_advisor_snapshot, project_hashes
from .answer_parser import normalized_answer as _normalized_answer
from .answer_parser import parse_answer as _parse_answer
from .contracts import ALLOWED_ACTIONS, ANSWER_SCHEMA, METADATA_END, METADATA_MARKER
from .prompt import advisor_prompt as _advisor_prompt
from .prompt import conversation_history as _conversation_history
from .prompt import public_context as _public_context
from .runtime import AdvisorRuntimeExecutor
from .runtime import _last_assistant_text
from .streaming import PublicAnswerStream as _PublicAnswerStream
from .streaming import marker_prefix_length as _marker_prefix_length


class ProjectAdvisor:
    def __init__(
        self,
        config: dict[str, Any],
        sessions: SessionRepositoryPort,
        *,
        runtime_pool=None,
        data_root: Path | None = None,
        session_event_tracker: Callable[..., object] | None = None,
    ):
        self.config = config
        self.sessions = sessions
        self.runtime_pool = runtime_pool
        self._configured_data_root = data_root.expanduser().resolve() if data_root is not None else None
        self._session_event_tracker = session_event_tracker or (
            lambda **fields: track_agent_session_event(sessions, **fields)
        )
        self._remote_sessions: dict[str, tuple[str, str, int]] = {}
        self._remote_lock = threading.RLock()

    def create_session(self, project_root: Path, *, title: str = "项目问答") -> dict[str, Any]:
        snapshot = self._snapshot(project_root)
        return self.sessions.create_advisor_session(str(snapshot.project_root), snapshot.digest, title=title)

    def list_sessions(self, project_root: Path) -> list[dict[str, Any]]:
        return self.sessions.list_advisor_sessions(str(project_root.expanduser().resolve()))

    def ask(
        self,
        session_id: str,
        question: str,
        *,
        timeout: int = 180,
        context: dict[str, Any] | None = None,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        normalized = str(question or "").strip()
        if not normalized:
            raise ValueError("advisor question must not be empty")
        session = self.sessions.read_advisor_session(session_id)
        project = Path(session["project_root"]).resolve()
        before = project_hashes(project)
        snapshot = self._snapshot(project)
        persona = active_persona(self._data_root(), project)
        stale = snapshot.digest != session["snapshot_digest"]
        self.sessions.append_advisor_message(session_id, "user", {"question": normalized})
        answer = self._run(
            snapshot.workspace,
            normalized,
            session["messages"],
            project_root=project,
            studio_session_id=session_id,
            snapshot_digest=snapshot.digest,
            context=context or {},
            session_summary=str(session.get("session_summary") or ""),
            pinned_preferences=list(session.get("pinned_user_preferences") or []),
            persona=persona,
            timeout=timeout,
            event_sink=event_sink,
        )
        if before != project_hashes(project):
            raise RuntimeError("read-only advisor project integrity check failed")
        answer.update(
            schema=ANSWER_SCHEMA,
            snapshot_digest=snapshot.digest,
            snapshot_stale_at_start=stale,
            project_unchanged=True,
            persona={key: persona[key] for key in ("persona_id", "name", "version", "accent")},
        )
        self._save_answer(session_id, session, answer)
        return answer

    def _save_answer(self, session_id: str, session: dict[str, Any], answer: dict[str, Any]) -> None:
        memory = answer.pop("memory", {}) if isinstance(answer.get("memory"), dict) else {}
        self.sessions.save_advisor_memory(
            session_id,
            summary=str(memory.get("session_summary") or session.get("session_summary") or ""),
            preferences=list(memory.get("pinned_preferences") or session.get("pinned_user_preferences") or []),
        )
        self.sessions.append_advisor_message(session_id, "advisor", answer)

    def _snapshot(self, project_root: Path):
        return create_advisor_snapshot(project_root, self._data_root() / "advisor" / "snapshots")

    def _data_root(self) -> Path:
        application = self.config.get("application") if isinstance(self.config.get("application"), dict) else {}
        configured = application.get("data_root") or self._configured_data_root
        if configured:
            return Path(str(configured)).expanduser().resolve()
        path = getattr(self.sessions, "path", None)
        return Path(path).parent.resolve() if path else Path(".").resolve()

    def _run(
        self,
        workspace: Path,
        question: str,
        history: list[dict[str, Any]],
        *,
        project_root: Path,
        studio_session_id: str,
        snapshot_digest: str,
        context: dict[str, Any],
        session_summary: str,
        pinned_preferences: list[str],
        persona: dict[str, str],
        timeout: int,
        event_sink: Callable[[str, dict[str, Any]], None] | None,
    ) -> dict[str, Any]:
        executor = AdvisorRuntimeExecutor(
            self.config,
            runtime_pool=self.runtime_pool,
            data_root=self._data_root(),
            remote_sessions=self._remote_sessions,
            remote_lock=self._remote_lock,
            session_event_tracker=self._session_event_tracker,
        )
        return executor.run(
            workspace,
            project_root=project_root,
            studio_session_id=studio_session_id,
            snapshot_digest=snapshot_digest,
            prompt_factory=lambda can_resume: _advisor_prompt(
                question,
                [] if can_resume else history,
                context,
                session_summary=session_summary,
                pinned_preferences=pinned_preferences,
                persona=persona,
            ),
            timeout=timeout,
            event_sink=event_sink,
        )


__all__ = ["ProjectAdvisor"]
