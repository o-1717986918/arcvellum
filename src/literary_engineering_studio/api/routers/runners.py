"""Agent Runner discovery, bundled OpenCode, and model connection routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from fastapi import APIRouter, HTTPException

from ..common import call_handler
from ..models import (
    CustomProviderConnectionRequest,
    ModelSelectionRequest,
    OpenCodeCredentialRequest,
    RunnerProbeRequest,
)


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
    connect_custom_provider: Callable[..., dict[str, Any]]
    disconnect_provider: Callable[..., dict[str, Any]]
    select_model: Callable[..., dict[str, Any]]
    model_connection_status: Callable[[dict[str, Any]], list[dict[str, Any]]]
    cache_model_catalog: Callable[[dict[str, Any]], None]


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
        def connect():
            catalog = deps.set_api_credential(
                deps.config,
                payload.provider_id,
                payload.credential,
                runtime_pool=deps.lifecycle.opencode_pool,
            )
            deps.cache_model_catalog(catalog)
            return {"ok": True, **catalog}

        return call_handler(connect)

    @router.put("/model-connections/opencode/custom")
    def opencode_custom_provider(payload: CustomProviderConnectionRequest):
        def connect():
            deps.lifecycle.opencode_pool.reload_provider_profiles()
            catalog = deps.connect_custom_provider(
                deps.config,
                {
                    "provider_id": payload.provider_id,
                    "display_name": payload.display_name,
                    "base_url": payload.base_url,
                    "models": [item.model_dump() for item in payload.models],
                },
                payload.credential,
                runtime_pool=deps.lifecycle.opencode_pool,
            )
            deps.cache_model_catalog(catalog)
            return {"ok": True, **catalog}

        return call_handler(connect)

    @router.delete("/model-connections/opencode/credential/{provider_id}")
    def opencode_model_disconnect(provider_id: str):
        def disconnect():
            catalog = deps.disconnect_provider(deps.config, provider_id, runtime_pool=deps.lifecycle.opencode_pool)
            deps.lifecycle.opencode_pool.reconcile_model_selection()
            deps.cache_model_catalog(catalog)
            return {"ok": True, **catalog}

        return call_handler(disconnect)

    @router.put("/model-connections/opencode/model")
    def opencode_model_select(payload: ModelSelectionRequest):
        def select():
            selection = deps.select_model(deps.config, payload.model, role=payload.role)
            runtime = deps.lifecycle.opencode_pool.reconcile_model_selection()
            catalog = deps.provider_catalog(deps.config, runtime_pool=deps.lifecycle.opencode_pool)
            deps.cache_model_catalog(catalog)
            return {"ok": True, **selection, "runtime": runtime, "catalog": catalog}

        return call_handler(select)

    @router.get("/model-connections")
    def model_connections():
        return {"ok": True, "items": deps.model_connection_status(deps.config), "managed_by": "agent-runner"}

    return router
