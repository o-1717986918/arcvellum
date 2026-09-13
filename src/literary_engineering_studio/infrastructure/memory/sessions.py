"""In-memory Advisor, Agent-session, and delegation-policy repository."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .primitives import iso_now
from .state import MemoryPersistenceState


_CONVERSATION_KINDS = {"advisor", "project-agent"}


class InMemorySessionRepository:
    path = Path(":memory:")

    def __init__(self, state: MemoryPersistenceState, clock, ids):
        self._state = state
        self._clock = clock
        self._ids = ids

    def create_conversation_session(
        self,
        project_root: str,
        snapshot_digest: str,
        *,
        title: str,
        session_kind: str,
    ) -> dict[str, Any]:
        kind = _conversation_kind(session_kind)
        with self._state.lock:
            session_id = self._ids.new_id(kind)
            now = iso_now(self._clock)
            self._state.advisor_sessions[session_id] = {
                "session_id": session_id,
                "project_root": project_root,
                "snapshot_digest": snapshot_digest,
                "title": title.strip() or _default_conversation_title(kind),
                "session_kind": kind,
                "created_at": now,
                "updated_at": now,
                "session_summary": "",
                "summary_updated_at": "",
                "pinned_user_preferences": [],
                "messages": [],
            }
            return self.read_conversation_session(session_id)

    def create_advisor_session(
        self,
        project_root: str,
        snapshot_digest: str,
        *,
        title: str = "项目问答",
    ) -> dict[str, Any]:
        return self.create_conversation_session(
            project_root,
            snapshot_digest,
            title=title,
            session_kind="advisor",
        )

    def read_advisor_session(self, session_id: str) -> dict[str, Any]:
        session = self.read_conversation_session(session_id)
        if session.get("session_kind") != "advisor":
            raise FileNotFoundError(f"Advisor session not found: {session_id}")
        return session

    def read_conversation_session(self, session_id: str) -> dict[str, Any]:
        with self._state.lock:
            try:
                return deepcopy(self._state.advisor_sessions[session_id])
            except KeyError as exc:
                raise FileNotFoundError(f"Conversation session not found: {session_id}") from exc

    def list_advisor_sessions(self, project_root: str, *, limit: int = 30) -> list[dict[str, Any]]:
        return self.list_conversation_sessions(
            project_root,
            session_kind="advisor",
            limit=limit,
        )

    def list_conversation_sessions(
        self,
        project_root: str,
        *,
        session_kind: str,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        kind = _conversation_kind(session_kind)
        with self._state.lock:
            sessions = [
                {key: value for key, value in item.items() if key not in {
                    "messages", "session_summary", "summary_updated_at", "pinned_user_preferences",
                }}
                for item in self._state.advisor_sessions.values()
                if item["project_root"] == project_root and item.get("session_kind", "advisor") == kind
            ]
            sessions.sort(key=lambda item: (item["updated_at"], item["session_id"]), reverse=True)
            return deepcopy(sessions[:max(1, min(200, int(limit)))])

    def append_advisor_message(self, session_id: str, role: str, payload: dict[str, Any]) -> dict[str, Any]:
        if role not in {"user", "advisor"}:
            raise ValueError("advisor message role must be user or advisor")
        session = self.read_conversation_session(session_id)
        if session.get("session_kind") != "advisor":
            raise FileNotFoundError(f"Advisor session not found: {session_id}")
        return self.append_session_message(session_id, role, payload)

    def append_session_message(self, session_id: str, role: str, payload: dict[str, Any]) -> dict[str, Any]:
        normalized_role = str(role or "").strip().lower()
        if normalized_role not in {"user", "assistant", "tool", "advisor"}:
            raise ValueError("conversation message role must be user, assistant, tool, or advisor")
        with self._state.lock:
            session = self._required_conversation(session_id)
            now = iso_now(self._clock)
            message = {
                "sequence": len(session["messages"]) + 1,
                "role": normalized_role,
                "at": now,
                "payload": deepcopy(payload),
            }
            session["messages"].append(message)
            session["updated_at"] = now
            return deepcopy(message)

    def save_advisor_memory(
        self,
        session_id: str,
        *,
        summary: str,
        preferences: list[str],
    ) -> dict[str, Any]:
        with self._state.lock:
            session = self._required_advisor(session_id)
            now = iso_now(self._clock)
            safe_summary = str(summary or "").strip()[:6000]
            safe_preferences = list(
                dict.fromkeys(str(item).strip()[:500] for item in preferences if str(item).strip())
            )[:30]
            if safe_summary:
                session["session_summary"] = safe_summary
                session["summary_updated_at"] = now
            session["pinned_user_preferences"] = safe_preferences
            session["updated_at"] = now
            return {
                "session_id": session_id,
                "session_summary": safe_summary,
                "pinned_user_preferences": deepcopy(safe_preferences),
                "updated_at": now,
            }

    def save_delegation_policy(self, project_root: str, policy: dict[str, Any]) -> dict[str, Any]:
        with self._state.lock:
            record = {
                "project_root": project_root,
                "policy": deepcopy(policy),
                "updated_at": iso_now(self._clock),
            }
            self._state.delegation_policies[project_root] = record
            return deepcopy(record)

    def read_delegation_policy(self, project_root: str) -> dict[str, Any] | None:
        with self._state.lock:
            record = self._state.delegation_policies.get(project_root)
            return deepcopy(record) if record is not None else None

    def upsert_agent_session(
        self,
        session_id: str,
        *,
        project_root: str,
        role: str,
        runtime: str,
        model: str = "",
        status: str = "running",
        task_id: str = "",
        route: str = "",
        controller_id: str = "",
        last_event: str = "",
        last_message: str = "",
        retry_count: int = 0,
        context_ledger_id: str = "",
        context_ledger_digest: str = "",
    ) -> dict[str, Any]:
        normalized_status = str(status or "running").strip().lower()
        allowed = {
            "queued", "running", "waiting", "waiting_human", "idle",
            "complete", "failed", "cancelled", "stopped",
        }
        if normalized_status not in allowed:
            raise ValueError(f"unsupported Agent session status: {status}")
        with self._state.lock:
            now = iso_now(self._clock)
            previous = self._state.agent_sessions.get(session_id, {})
            values = _agent_session_values(
                previous,
                session_id=session_id, project_root=project_root, role=role,
                runtime=runtime, model=model, status=normalized_status,
                task_id=task_id, route=route, controller_id=controller_id,
                last_event=last_event, last_message=last_message,
                retry_count=retry_count, context_ledger_id=context_ledger_id,
                context_ledger_digest=context_ledger_digest, now=now,
            )
            self._state.agent_sessions[session_id] = values
            return deepcopy(values)

    def read_agent_session(self, session_id: str) -> dict[str, Any]:
        with self._state.lock:
            try:
                return deepcopy(self._state.agent_sessions[session_id])
            except KeyError as exc:
                raise FileNotFoundError(f"Agent session not found: {session_id}") from exc

    def list_agent_sessions(
        self,
        project_root: str,
        *,
        include_finished: bool = True,
        limit: int = 60,
    ) -> list[dict[str, Any]]:
        terminal = {"complete", "failed", "cancelled", "stopped"}
        with self._state.lock:
            sessions = [
                item for item in self._state.agent_sessions.values()
                if item["project_root"] == project_root
                and (include_finished or item["status"] not in terminal)
            ]
            sessions.sort(
                key=lambda item: (bool(item["finished_at"]), item["updated_at"]),
                reverse=False,
            )
            return deepcopy(sessions[:max(1, min(200, int(limit)))])

    def _required_advisor(self, session_id: str) -> dict[str, Any]:
        session = self._required_conversation(session_id)
        if session.get("session_kind", "advisor") != "advisor":
            raise FileNotFoundError(f"Advisor session not found: {session_id}")
        return session

    def _required_conversation(self, session_id: str) -> dict[str, Any]:
        try:
            return self._state.advisor_sessions[session_id]
        except KeyError as exc:
            raise FileNotFoundError(f"Conversation session not found: {session_id}") from exc


__all__ = ["InMemorySessionRepository"]


def _conversation_kind(value: str) -> str:
    kind = str(value or "").strip().lower()
    if kind not in _CONVERSATION_KINDS:
        raise ValueError(f"unsupported conversation session kind: {value}")
    return kind


def _default_conversation_title(kind: str) -> str:
    return "项目问答" if kind == "advisor" else "项目 Agent"


def _agent_session_values(previous: dict[str, Any], **fields: Any) -> dict[str, Any]:
    now = fields["now"]
    status = fields["status"]
    text_names = (
        "project_root", "role", "runtime", "model", "task_id", "route",
        "controller_id", "last_message", "context_ledger_id", "context_ledger_digest",
    )
    values = {
        name: _prefer(fields.get(name), previous.get(name))
        for name in text_names
    }
    values.update(
        session_id=fields["session_id"],
        status=status,
        started_at=previous.get("started_at", now),
        updated_at=now,
        finished_at=now if status in {"complete", "failed", "cancelled", "stopped"} else "",
        event_count=int(previous.get("event_count") or 0) + (1 if fields.get("last_event") else 0),
        last_event=str(fields.get("last_event") or "")[:120],
        retry_count=max(int(previous.get("retry_count") or 0), max(0, int(fields.get("retry_count") or 0))),
    )
    return values


def _prefer(current: Any, previous: Any) -> str:
    return str(current if current else previous or "")
