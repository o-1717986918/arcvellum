"""Compose quality and rhythm controls from the literary public API."""

from __future__ import annotations

from typing import Any

from .routers.quality import QualityRouterDependencies, build_quality_router
from literary_engineering_studio_engine.public.literary import (
    lint_punctuation,
    load_creative_quality_profile,
    load_rhythm_plan,
    save_creative_quality_profile,
    save_rhythm_plan,
    style_lint_gate,
)


def register_quality_router(app: Any, read_models: Any) -> None:
    app.include_router(
        build_quality_router(
            QualityRouterDependencies(
                load_creative_quality_profile=load_creative_quality_profile,
                save_creative_quality_profile=save_creative_quality_profile,
                style_lint_gate=style_lint_gate,
                lint_punctuation=lint_punctuation,
                load_rhythm_plan=load_rhythm_plan,
                save_rhythm_plan=save_rhythm_plan,
                invalidate_project=read_models.invalidate,
            )
        )
    )


__all__ = ["register_quality_router"]
