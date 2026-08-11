"""Public controls for the embedded ArcVellum Pi Worker."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ...application.config import save_config
from ...integrations.pi_worker import (
    disconnect_pi_provider,
    pi_worker_catalog,
    select_pi_model,
    set_pi_api_credential,
)
from ...runtimes import clear_agent_runner_status_cache
from ..common import call_handler
from ..models import ModelSelectionRequest, PiWorkerCredentialRequest


def build_pi_worker_router(config: dict[str, Any]) -> APIRouter:
    router = APIRouter()

    @router.get("/model-connections/pi-worker/catalog")
    def catalog():
        return call_handler(lambda: {"ok": True, **pi_worker_catalog(config)})

    @router.put("/model-connections/pi-worker/credential")
    def credential(payload: PiWorkerCredentialRequest):
        return call_handler(
            lambda: {"ok": True, **set_pi_api_credential(config, payload.provider_id, payload.credential)}
        )

    @router.delete("/model-connections/pi-worker/credential/{provider_id}")
    def disconnect(provider_id: str):
        def apply():
            result = disconnect_pi_provider(config, provider_id)
            save_config(config)
            clear_agent_runner_status_cache()
            return {"ok": True, **result}

        return call_handler(apply)

    @router.put("/model-connections/pi-worker/model")
    def select(payload: ModelSelectionRequest):
        def apply():
            result = select_pi_model(config, payload.model)
            save_config(config)
            clear_agent_runner_status_cache()
            return {"ok": True, **result}

        return call_handler(apply)

    return router


__all__ = ["build_pi_worker_router"]
