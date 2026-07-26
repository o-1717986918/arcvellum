"""Runtime-backed transport for isolated orchestration Agent sessions."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from time import perf_counter
from typing import Any, Protocol

from literary_engineering_studio_engine.foundation.atomic_io import atomic_write_text

from ..runtimes import build_runtime
from .profiles import OrchestrationAgentRole


@dataclass(frozen=True)
class OrchestrationAgentResponse:
    role: OrchestrationAgentRole
    session_id: str
    payload: dict[str, Any]
    raw_text: str
    deltas: tuple[str, ...]
    elapsed_ms: float


class OrchestrationAgentTransport(Protocol):
    def invoke(
        self,
        role: OrchestrationAgentRole,
        *,
        prompt: str,
        audit_root: Path,
    ) -> OrchestrationAgentResponse: ...


class RuntimeOrchestrationAgentTransport:
    """Run a read-only Planner or Reviewer through the configured Agent runtime."""

    def __init__(
        self,
        config: dict[str, Any],
        *,
        runtime_id: str = "opencode",
        runtime_pool=None,
        timeout_seconds: int = 300,
    ):
        self.config = config
        self.runtime_id = str(runtime_id or "opencode").strip().lower()
        if self.runtime_id != "opencode":
            raise ValueError(
                "AO-3 orchestration sessions currently require the role-isolated OpenCode runtime"
            )
        self.runtime_pool = runtime_pool
        self.timeout_seconds = max(30, int(timeout_seconds))

    def invoke(
        self,
        role: OrchestrationAgentRole,
        *,
        prompt: str,
        audit_root: Path,
    ) -> OrchestrationAgentResponse:
        if role not in {OrchestrationAgentRole.PLANNER, OrchestrationAgentRole.REVIEWER}:
            raise ValueError(f"unsupported orchestration transport role: {role}")
        root = audit_root.expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        workspace = root / "workspace"
        run_root = root / "runtime"
        workspace.mkdir(parents=True, exist_ok=True)
        run_root.mkdir(parents=True, exist_ok=True)
        prompt_path = root / "request.md"
        atomic_write_text(prompt_path, prompt)
        deltas: list[str] = []

        def collect(event: str, data: dict[str, Any]) -> None:
            if event == "agent.message.delta" and isinstance(data.get("text"), str):
                deltas.append(str(data["text"]))

        runtime = build_runtime(
            self.runtime_id,
            self.config,
            runtime_pool=self.runtime_pool,
            role=_runtime_role(role),
        )
        started = perf_counter()
        result = runtime.execute(
            workspace,
            prompt_path,
            run_root,
            timeout=self.timeout_seconds,
            event_sink=collect,
        )
        if result.status != "completed" or result.output_path is None:
            raise RuntimeError(
                f"{role.value} runtime failed: {result.status}: {result.message}"
            )
        output_path = result.output_path.expanduser().resolve()
        if root not in output_path.parents:
            raise RuntimeError("orchestration runtime output escaped its audit directory")
        raw_text = output_path.read_text(encoding="utf-8")
        return OrchestrationAgentResponse(
            role=role,
            session_id=str(result.metadata.get("session_id") or "").strip(),
            payload=parse_structured_agent_response(raw_text),
            raw_text=raw_text,
            deltas=tuple(deltas),
            elapsed_ms=round((perf_counter() - started) * 1000.0, 3),
        )


def parse_structured_agent_response(text: str) -> dict[str, Any]:
    """Accept one JSON object, optionally wrapped in one Markdown code fence."""

    value = str(text or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", value, flags=re.DOTALL)
    if fenced:
        value = fenced.group(1)
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("orchestration Agent response must be one JSON object") from exc
    if not isinstance(payload, dict):
        raise ValueError("orchestration Agent response must be one JSON object")
    return payload


def _runtime_role(role: OrchestrationAgentRole) -> str:
    if role is OrchestrationAgentRole.PLANNER:
        return "planner"
    return "reviewer"
