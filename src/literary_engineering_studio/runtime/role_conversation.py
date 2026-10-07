"""Tool-free role conversations executed through the registered Pi Worker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import threading
import time
from typing import Any, Callable, Sequence

from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
from ..runtimes import build_runtime
from .runtime_selection import runtime_for_role


_INITIALIZED_ROLES = frozenset({
    "character-actor", "environment-writer", "character-describer", "event-narrator", "scene-describer",
})


@dataclass(frozen=True)
class RoleConversationResult:
    runtime: str
    run_id: str
    model: str
    answer: str
    initialization_answer: str = ""


class RoleConversationError(RuntimeError):
    """Preserve the registered runtime's failure evidence and partial output."""

    def __init__(self, message: str, *, run_root: Path, metadata: dict[str, Any] | None):
        values = metadata if isinstance(metadata, dict) else {}
        result = _worker_result(values)
        super().__init__(str(result.get("providerError") or message))
        self.failure_kind = values.get("failure_kind") or result.get("failureKind") or "unreported"
        self.retryable = result.get("providerFailureRetryable", values.get("retryable"))
        self.run_root = str(run_root)
        self.partial_answer = str(result.get("answer") or "")


class RoleConversationGateway:
    """Run bounded literary roles; only the scene creator gets material-file reads."""

    def __init__(self, config: dict[str, Any], *, data_root: Path):
        self.config = config
        self.data_root = data_root

    def run(
        self,
        workspace: Path,
        prompt: str,
        *,
        role: str,
        timeout: int,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> RoleConversationResult:
        if role == "character-actor":
            raise ValueError("character actor requires an initialized conversation")
        turns = _environment_turn_count(prompt) if role == "environment-writer" else 1
        return self._execute(workspace, prompt, role=role, timeout=timeout,
                             event_sink=event_sink, cancel_event=cancel_event, turns=turns)

    def run_sequence(
        self, workspace: Path, messages: Sequence[str], *, role: str, timeout: int,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> RoleConversationResult:
        if role != "character-actor" or len(messages) < 2 or any(not message.strip() for message in messages):
            raise ValueError("actor conversation requires initialization followed by nonempty messages")
        payload = json.dumps({"schema": "arcvellum/actor-conversation/v1",
                              "messages": list(messages)}, ensure_ascii=False)
        return self._execute(workspace, payload, role=role, timeout=timeout,
                             event_sink=event_sink, cancel_event=cancel_event, turns=len(messages))

    def run_actor_turn(
        self, workspace: Path, *, initialization: str, initialization_answer: str,
        history: Sequence[tuple[str, str]], prompt: str, timeout: int,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> RoleConversationResult:
        """Continue one actor's scene transcript without regenerating prior replies."""

        if not initialization.strip() or not prompt.strip():
            raise ValueError("actor turn requires initialization and preserved prior answers")
        payload = json.dumps({
            "schema": "arcvellum/actor-conversation/v2", "initialization": initialization,
            "initialization_answer": initialization_answer,
            "history": [{"prompt": question, "answer": answer} for question, answer in history],
            "prompt": prompt,
        }, ensure_ascii=False)
        return self._execute(workspace, payload, role="character-actor", timeout=timeout,
                             event_sink=event_sink, cancel_event=None, turns=1)

    def run_role_turn(
        self, workspace: Path, *, role: str, initialization: str,
        history: Sequence[tuple[str, str]], prompt: str, timeout: int,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> RoleConversationResult:
        if role not in {"environment-writer", "character-describer", "event-narrator", "scene-describer"}:
            raise ValueError("unsupported initialized literary role")
        if not initialization.strip() or not prompt.strip() or len(history) > 16:
            raise ValueError("role turn needs initialization, prompt, and bounded history")
        payload = json.dumps({
            "schema": "arcvellum/role-conversation/v1", "initialization": initialization,
            "initialization_answer": "",
            "history": [{"prompt": question, "answer": answer} for question, answer in history],
            "prompt": prompt,
        }, ensure_ascii=False)
        return self._execute(workspace, payload, role=role, timeout=timeout,
                             event_sink=event_sink, cancel_event=None, turns=1)

    def _execute(
        self, workspace: Path, prompt: str, *, role: str, timeout: int,
        event_sink: Callable[[str, dict[str, Any]], None] | None,
        cancel_event: threading.Event | None, turns: int,
    ) -> RoleConversationResult:
        prompt, scene_creator = _conversation_prompt(role, prompt)
        runtime_id = runtime_for_role(self.config, role)
        if runtime_id != "pi-worker":
            raise RuntimeError(f"tool-free role conversation is unsupported by runtime: {runtime_id}")
        settings, model = _role_settings(self.config, role)
        run_root, prompt_path = _prepare_run(self.data_root, role, prompt)
        pieces: list[str] = []

        def observe(event: str, data: dict[str, Any]) -> None:
            if event == "agent.message.delta":
                pieces.append(str(data.get("text") or ""))
            if event_sink is not None:
                event_sink(event, data)

        result = build_runtime("pi-worker", self.config, role=role).execute(
            workspace,
            prompt_path,
            run_root,
            timeout=max(10, min(900, int(timeout))),
            event_sink=observe,
            cancel_event=cancel_event,
            worker_mode="conversation",
            conversation_role=_conversation_role(role, scene_creator),
            reasoning_policy=str(settings.get("thinking") or "medium"),
            max_turns=turns,
            max_tool_calls=(64 if json.loads(prompt)["schema"] == "arcvellum/scene-creator/v2"
                            else 8) if scene_creator else 1,
            max_repairs=0,
        )
        worker_result = _worker_result(result.metadata)
        final_answer = str(worker_result.get("answer") or "").strip()
        answer = final_answer if scene_creator or role in _INITIALIZED_ROLES else "".join(pieces).strip() or final_answer
        if result.status != "completed":
            raise RoleConversationError(result.message or f"{role} conversation failed",
                                        run_root=run_root, metadata=result.metadata)
        if not answer:
            raise RuntimeError(f"{role} conversation returned no answer")
        return RoleConversationResult(
            runtime="pi-worker",
            run_id=str(worker_result.get("taskId") or run_root.name),
            model=model,
            answer=answer,
            initialization_answer=str(worker_result.get("initializationAnswer") or ""),
        )


def _conversation_prompt(role: str, prompt: str) -> tuple[str, bool]:
    scene_creator = role == "worker" and _scene_creator_envelope(prompt)
    if scene_creator or role in _INITIALIZED_ROLES:
        return prompt, scene_creator
    try:
        envelope = json.loads(prompt)
    except json.JSONDecodeError:
        envelope = None
    if isinstance(envelope, dict) and envelope.get("schema") == "arcvellum/default-conversation/v1":
        return prompt, False
    return json.dumps({
        "schema": "arcvellum/default-conversation/v1",
        "system_prompt": prompt_layer_spec("pi.conversation.system").default_text,
        "prompt": prompt,
    }, ensure_ascii=False), False


def _conversation_role(role: str, scene_creator: bool) -> str:
    if scene_creator:
        return "scene-creator"
    return role if role in _INITIALIZED_ROLES else "default"


def _role_settings(config: dict[str, Any], role: str) -> tuple[dict[str, Any], str]:
    settings = config.get("agent_runners", {}).get("pi-worker", {})
    settings = settings if isinstance(settings, dict) else {}
    models = settings.get("models") if isinstance(settings.get("models"), dict) else {}
    model = str(models.get(role) or settings.get("model") or "").strip()
    if "/" not in model:
        raise RuntimeError(f"select a Pi Worker provider/model before using the {role} role")
    return settings, model


def _prepare_run(data_root: Path, role: str, prompt: str) -> tuple[Path, Path]:
    run_root = data_root / role / "runs" / f"run-{int(time.time() * 1000)}"
    run_root.mkdir(parents=True, exist_ok=False)
    prompt_path = run_root / "conversation.prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    return run_root, prompt_path


def _worker_result(metadata: dict[str, Any] | None) -> dict[str, Any]:
    values = metadata if isinstance(metadata, dict) else {}
    result = values.get("worker_result")
    return result if isinstance(result, dict) else {}


def _environment_turn_count(prompt: str) -> int:
    try:
        payload = json.loads(prompt)
    except json.JSONDecodeError:
        return 1
    if not isinstance(payload, dict) or payload.get("schema") != "arcvellum/environment-conversation/v1":
        return 1
    if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in ("initialization", "prompt")):
        raise ValueError("environment conversation requires initialization and scene prompt")
    return 2


def _scene_creator_envelope(prompt: str) -> bool:
    try:
        payload = json.loads(prompt)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict) or payload.get("schema") not in {
        "arcvellum/scene-creator/v1", "arcvellum/scene-creator/v2",
    }:
        return False
    keys = ("system_prompt", "material_root", "prompt")
    if payload["schema"] == "arcvellum/scene-creator/v2":
        keys += ("archive_root", "scratch_root")
    if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in keys):
        raise ValueError("scene creator envelope is incomplete")
    return True
__all__ = ["RoleConversationGateway", "RoleConversationResult", "RoleConversationError"]
