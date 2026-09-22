"""Transport-neutral contracts for the Project Agent bridge."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
from typing import Any


PROJECT_AGENT_BRIDGE_SCHEMA = "arcvellum/project-agent-bridge/v1"
MAX_BRIDGE_FRAME_BYTES = 256 * 1024
MAX_TOOL_RESULT_BYTES = 64 * 1024


class BridgeMessageType(str, Enum):
    TURN_START = "turn.start"
    TURN_CANCEL = "turn.cancel"
    BRIDGE_READY = "bridge.ready"
    AGENT_EVENT = "agent.event"
    TOOL_CALL = "tool.call"
    TOOL_RESULT = "tool.result"
    TURN_COMPLETE = "turn.complete"
    BRIDGE_ERROR = "bridge.error"


class DelegationMode(str, Enum):
    COLLABORATIVE = "collaborative"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


class ToolRisk(str, Enum):
    READ = "read"
    REVERSIBLE_WRITE = "reversible_write"
    FORMAL_WRITE = "formal_write"


@dataclass(frozen=True)
class BridgeEnvelope:
    type: BridgeMessageType
    message_id: str
    turn_id: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    schema: str = PROJECT_AGENT_BRIDGE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != PROJECT_AGENT_BRIDGE_SCHEMA:
            raise ValueError(f"unsupported Project Agent bridge schema: {self.schema}")
        if not self.message_id.strip():
            raise ValueError("bridge message_id is required")
        if not self.turn_id.strip():
            raise ValueError("bridge turn_id is required")
        if not isinstance(self.payload, Mapping):
            raise ValueError("bridge payload must be an object")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "type": self.type.value,
            "message_id": self.message_id,
            "turn_id": self.turn_id,
            "payload": dict(self.payload),
        }

    def to_json_line(self) -> str:
        line = json.dumps(self.as_dict(), ensure_ascii=False, separators=(",", ":"))
        if len(line.encode("utf-8")) > MAX_BRIDGE_FRAME_BYTES:
            raise ValueError(f"bridge frame exceeds {MAX_BRIDGE_FRAME_BYTES} bytes")
        return line + "\n"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BridgeEnvelope":
        if not isinstance(value, Mapping):
            raise ValueError("bridge frame must be an object")
        try:
            message_type = BridgeMessageType(str(value.get("type") or ""))
        except ValueError as exc:
            raise ValueError(f"unsupported bridge message type: {value.get('type')}") from exc
        payload = value.get("payload", {})
        if not isinstance(payload, Mapping):
            raise ValueError("bridge payload must be an object")
        return cls(
            schema=str(value.get("schema") or ""),
            type=message_type,
            message_id=str(value.get("message_id") or ""),
            turn_id=str(value.get("turn_id") or ""),
            payload=payload,
        )

    @classmethod
    def from_json_line(cls, line: str) -> "BridgeEnvelope":
        if len(line.encode("utf-8")) > MAX_BRIDGE_FRAME_BYTES:
            raise ValueError(f"bridge frame exceeds {MAX_BRIDGE_FRAME_BYTES} bytes")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError("bridge frame must be valid JSON") from exc
        if not isinstance(value, Mapping):
            raise ValueError("bridge frame must be an object")
        return cls.from_dict(value)


@dataclass(frozen=True)
class ProjectAgentTurnRequest:
    session_id: str
    turn_id: str
    prompt: str
    system_prompt: str
    allowed_tools: tuple[str, ...] = ("project_overview",)

    def __post_init__(self) -> None:
        if not self.session_id.strip() or not self.turn_id.strip():
            raise ValueError("session_id and turn_id are required")
        if not self.prompt.strip():
            raise ValueError("Project Agent prompt is required")
        if not self.system_prompt.strip():
            raise ValueError("Project Agent system prompt is required")
        if not self.allowed_tools:
            raise ValueError("at least one Project Agent tool is required")

    def start_envelope(self, message_id: str) -> BridgeEnvelope:
        return BridgeEnvelope(
            type=BridgeMessageType.TURN_START,
            message_id=message_id,
            turn_id=self.turn_id,
            payload={
                "session_id": self.session_id,
                "prompt": self.prompt,
                "system_prompt": self.system_prompt,
                "allowed_tools": list(self.allowed_tools),
            },
        )


@dataclass(frozen=True)
class ProjectAgentToolCall:
    request_id: str
    turn_id: str
    name: str
    arguments: Mapping[str, Any]

    @classmethod
    def from_envelope(cls, envelope: BridgeEnvelope) -> "ProjectAgentToolCall":
        if envelope.type is not BridgeMessageType.TOOL_CALL:
            raise ValueError("expected a tool.call envelope")
        request_id = str(envelope.payload.get("request_id") or "").strip()
        name = str(envelope.payload.get("name") or "").strip()
        arguments = envelope.payload.get("arguments", {})
        if not request_id or not name or not isinstance(arguments, Mapping):
            raise ValueError("tool.call requires request_id, name, and object arguments")
        return cls(request_id, envelope.turn_id, name, arguments)


@dataclass(frozen=True)
class ProjectAgentToolResult:
    request_id: str
    turn_id: str
    name: str
    ok: bool
    result: Any = None
    error: str = ""

    def envelope(self, message_id: str) -> BridgeEnvelope:
        return BridgeEnvelope(
            type=BridgeMessageType.TOOL_RESULT,
            message_id=message_id,
            turn_id=self.turn_id,
            payload={
                "request_id": self.request_id,
                "name": self.name,
                "ok": self.ok,
                "result": self.result,
                "error": self.error,
            },
        )


@dataclass(frozen=True)
class ProjectAgentTurnResult:
    status: str
    answer: str
    turn_id: str
    returncode: int | None
    tool_calls: int
    message: str = ""


ProjectReadModel = Callable[[Path, Mapping[str, Any]], Mapping[str, Any]]
ProjectAction = Callable[[Path, Mapping[str, Any]], Mapping[str, Any]]
ProjectScopeResolver = Callable[[Path, Mapping[str, Any]], Path]


@dataclass(frozen=True)
class ProjectAgentDependencies:
    """Composition-root references to existing read models.

    These callables are adapters over existing services. They are deliberately
    data-oriented so the Project Agent package never imports API routers.
    """

    project_overview: ProjectReadModel
    project_search: ProjectReadModel
    creation_observe: ProjectReadModel
    project_controls: ProjectReadModel | None = None
    workspace_catalog: ProjectReadModel | None = None
    project_diagnose: ProjectReadModel | None = None
    resolve_project: ProjectScopeResolver | None = None


@dataclass(frozen=True)
class ProjectAgentActionDependencies:
    """Narrow adapters over existing application services that may mutate state."""

    record_direction: ProjectAction
    creation_control: ProjectAction
    resolve_decision: ProjectAction | None = None
    update_quality: ProjectAction | None = None
    update_rhythm: ProjectAction | None = None
    mount_style: ProjectAction | None = None
    promote_asset: ProjectAction | None = None
    create_project: ProjectAction | None = None
    manage_goal: ProjectAction | None = None
    extend_chapter: ProjectAction | None = None
