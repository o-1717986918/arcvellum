"""Agent Runner discovery, bundled OpenCode, and model connection routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from fastapi import APIRouter, HTTPException

from ..common import call_handler
from ..models import ModelSelectionRequest, OpenCodeCredentialRequest, RunnerProbeRequest


@dataclass(frozen=True)
class RunnerRouterDependencies:
    config: dict[str, Any]
    lifecycle: Any
    locate_opencode: Callable[[dict[str, Any]], Any]
    verify_opencode: Callable[[Any], dict[str, Any]]
    install_pinned_opencode: Callable[[], dict[str, Any]]
    probe_agent_runner: Callable[..., dict[str, Any]]
    provider_catalog: Callable[..., dict[str, Any]]
    set_api_credential: Callable[..., dict[str, Any]]
    disconnect_provider: Callable[..., dict[str, Any]]
    select_model: Callable[..., dict[str, Any]]
    model_connection_status: Callable[[dict[str, Any]], list[dict[str, Any]]]


def build_runner_router(deps: RunnerRouterDependencies) -> APIRouter:
    """Build the runner control surface without embedding credential logic in the app factory."""

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

    @router.get("/agent-runners/opencode/bundle")
    def opencode_bundle_status():
        settings = deps.config.get("agent_runners", {})
        executable = deps.locate_opencode(settings.get("opencode", {}) if isinstance(settings, dict) else {})
        return {
            "ok": True,
            "installed": executable is not None,
            "verification": deps.verify_opencode(executable) if executable else {},
        }

    @router.post("/agent-runners/opencode/install")
    def opencode_bundle_install():
        return call_handler(lambda: {"ok": True, **deps.install_pinned_opencode()})

    @router.post("/agent-runners/{runner_id}/probe")
    def agent_runner_probe(runner_id: str, payload: RunnerProbeRequest):
        if runner_id not in {"opencode", "claude-code", "codex-cli"}:
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
                    runtime_pool=deps.lifecycle.opencode_pool if runner_id == "opencode" else None,
                ),
            }
        )

    @router.get("/model-connections/opencode/catalog")
    def opencode_model_catalog():
        return call_handler(lambda: {"ok": True, **deps.provider_catalog(deps.config, runtime_pool=deps.lifecycle.opencode_pool)})

    @router.put("/model-connections/opencode/credential")
    def opencode_model_credential(payload: OpenCodeCredentialRequest):
        return call_handler(
            lambda: {
                "ok": True,
                **deps.set_api_credential(
                    deps.config,
                    payload.provider_id,
                    payload.credential,
                    runtime_pool=deps.lifecycle.opencode_pool,
                ),
            }
        )

    @router.delete("/model-connections/opencode/credential/{provider_id}")
    def opencode_model_disconnect(provider_id: str):
        return call_handler(
            lambda: {
                "ok": True,
                **deps.disconnect_provider(deps.config, provider_id, runtime_pool=deps.lifecycle.opencode_pool),
            }
        )

    @router.put("/model-connections/opencode/model")
    def opencode_model_select(payload: ModelSelectionRequest):
        return call_handler(lambda: {"ok": True, **deps.select_model(deps.config, payload.model, role=payload.role)})

    @router.get("/model-connections")
    def model_connections():
        return {"ok": True, "items": deps.model_connection_status(deps.config), "managed_by": "agent-runner"}

    return router
