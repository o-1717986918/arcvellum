"""Agent Runtime discovery and optional external-runner probes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from fastapi import APIRouter, HTTPException

from ..common import call_handler
from ..models import RunnerProbeRequest


@dataclass(frozen=True)
class RunnerRouterDependencies:
    config: dict[str, Any]
    lifecycle: Any
    probe_agent_runner: Callable[..., dict[str, Any]]
    model_connection_status: Callable[[dict[str, Any]], list[dict[str, Any]]]


def build_runner_router(deps: RunnerRouterDependencies) -> APIRouter:
    """Expose registered runtimes without coupling the API to one product."""

    router = APIRouter()

    @router.get("/runtime/adapters")
    def runtime_adapters():
        return {
            "ok": True,
            "items": deps.lifecycle.health().get("agent_runners", []),
            "deprecated_alias": True,
            "replacement": "/agent-runners",
        }

    @router.get("/agent-runners")
    def agent_runners():
        return {"ok": True, "items": deps.lifecycle.refresh_agent_runners(wait=True, force=True)}

    @router.post("/agent-runners/{runner_id}/probe")
    def agent_runner_probe(runner_id: str, payload: RunnerProbeRequest):
        if runner_id not in {"pi-worker", "claude-code", "codex-cli"}:
            raise HTTPException(status_code=404, detail="unknown Agent Runner")
        return call_handler(
            lambda: {
                "ok": True,
                **deps.probe_agent_runner(
                    deps.config,
                    runner_id,
                    model=payload.model,
                    role=payload.role,
                    timeout=max(10, min(600, payload.timeout)),
                    runtime_pool=deps.lifecycle.runtime_pool,
                ),
            }
        )

    @router.get("/model-connections")
    def model_connections():
        return {
            "ok": True,
            "items": deps.model_connection_status(deps.config),
            "managed_by": "agent-runner",
        }

    return router


__all__ = ["RunnerRouterDependencies", "build_runner_router"]
