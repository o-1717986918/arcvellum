"""Forward scene conversation events through one transaction adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..runtime.role_conversation import RoleConversationGateway


def invoke_role(
    gateway: RoleConversationGateway, project_root: Path, timeout: int,
    event_sink: Callable[[str, dict[str, Any]], None] | None, transaction_id: str,
    prompt: str, role: str,
) -> str:
    return gateway.run(project_root, prompt, role=role, timeout=timeout,
                       event_sink=_observer(event_sink, transaction_id)).answer


def invoke_role_sequence(
    gateway: RoleConversationGateway, project_root: Path, timeout: int,
    event_sink: Callable[[str, dict[str, Any]], None] | None, transaction_id: str,
    messages: tuple[str, ...], role: str,
) -> str:
    return gateway.run_sequence(project_root, messages, role=role, timeout=timeout,
                                event_sink=_observer(event_sink, transaction_id)).answer


def invoke_actor_turn(
    gateway: RoleConversationGateway, project_root: Path, timeout: int,
    event_sink: Callable[[str, dict[str, Any]], None] | None, transaction_id: str,
    initialization: str, initialization_answer: str,
    history: tuple[tuple[str, str], ...], prompt: str,
) -> tuple[str, str]:
    response = gateway.run_actor_turn(
        project_root, initialization=initialization,
        initialization_answer=initialization_answer, history=history, prompt=prompt,
        timeout=timeout, event_sink=_observer(event_sink, transaction_id),
    )
    return response.answer, response.initialization_answer


def _observer(
    sink: Callable[[str, dict[str, Any]], None] | None, transaction_id: str,
) -> Callable[[str, dict[str, Any]], None] | None:
    if sink is None:
        return None
    return lambda event, data: sink(event, {**data, "scene_transaction_id": transaction_id})


__all__ = ["invoke_role", "invoke_role_sequence", "invoke_actor_turn"]
