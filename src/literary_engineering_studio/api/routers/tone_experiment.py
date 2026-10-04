"""HTTP adapter for the opt-in editing preference."""
from fastapi import APIRouter
from pydantic import BaseModel, StrictBool
from ...application.less_ai_tone_preferences import (
    get_less_ai_tone_preferences, set_less_ai_tone_preferences,
)
from ..common import call_handler


class ToneExperimentRequest(BaseModel):
    enabled: StrictBool


def build_tone_experiment_router(config) -> APIRouter:
    router = APIRouter(prefix="/experiments/less-ai-tone")

    @router.get("")
    def preferences():
        return call_handler(lambda: {"ok": True, "preferences": get_less_ai_tone_preferences(config)})

    @router.put("")
    def save_preferences(payload: ToneExperimentRequest):
        return call_handler(lambda: {"ok": True,
            "preferences": set_less_ai_tone_preferences(config, payload.enabled)})

    return router
