"""Creative-quality lint profile and longform rhythm-plan API routes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter

from ..common import call_handler, project_root as resolve_project_root
from ..models import CreativeQualityPreviewRequest, CreativeQualityRequest, RhythmPlanRequest


@dataclass(frozen=True)
class QualityRouterDependencies:
    load_creative_quality_profile: Callable[[Path], dict[str, Any]]
    save_creative_quality_profile: Callable[..., dict[str, Any]]
    style_lint_gate: Callable[..., dict[str, Any]]
    lint_punctuation: Callable[..., list[Any]]
    load_rhythm_plan: Callable[[Path], dict[str, Any]]
    save_rhythm_plan: Callable[..., dict[str, Any]]
    invalidate_project: Callable[[Path, str], Any]


def build_quality_router(deps: QualityRouterDependencies) -> APIRouter:
    """Build profile/rhythm endpoints that affect future candidate generation only."""

    router = APIRouter()

    @router.get("/project/creative-quality")
    def project_creative_quality(project_root: str):
        root = resolve_project_root(project_root)
        return {"ok": True, "profile": deps.load_creative_quality_profile(root)}

    @router.put("/project/creative-quality")
    def project_creative_quality_update(payload: CreativeQualityRequest):
        root = resolve_project_root(payload.project_root)
        result = call_handler(
            lambda: {
                "ok": True,
                "profile": deps.save_creative_quality_profile(root, payload.profile, updated_by="studio-user"),
                "effect": "future-candidates",
                "review_required_for_existing_candidates": True,
            }
        )
        deps.invalidate_project(root, "creative-quality")
        return result

    @router.post("/project/creative-quality/preview")
    def project_creative_quality_preview(payload: CreativeQualityPreviewRequest):
        root = resolve_project_root(payload.project_root)
        profile = payload.profile or deps.load_creative_quality_profile(root)
        style_gate = deps.style_lint_gate(payload.text, profile=profile, scope=payload.scope)
        punctuation = deps.lint_punctuation(payload.text, profile=profile, scope=payload.scope)
        punctuation_items = [
            {"rule": issue.rule, "severity": issue.severity, "message": issue.message, "sample": issue.sample}
            for issue in punctuation
        ]
        blocking = list(style_gate.get("blocking") or []) + [item for item in punctuation_items if item["severity"] != "low"]
        notes = list(style_gate.get("notes") or []) + [item for item in punctuation_items if item["severity"] == "low"]
        return {
            "ok": True,
            "status": "blocking" if blocking else ("notes" if notes else "pass"),
            "blocking": blocking,
            "notes": notes,
            "profile_digest": profile.get("digest", ""),
            "summary": "存在必须修改的问题" if blocking else ("有可复核的表达提醒" if notes else "样文通过当前静态规则"),
        }

    @router.get("/project/rhythm-plan")
    def project_rhythm_plan(project_root: str):
        return call_handler(lambda: {"ok": True, "plan": deps.load_rhythm_plan(resolve_project_root(project_root))})

    @router.put("/project/rhythm-plan")
    def project_rhythm_plan_update(payload: RhythmPlanRequest):
        root = resolve_project_root(payload.project_root)
        result = call_handler(
            lambda: {
                "ok": True,
                "plan": deps.save_rhythm_plan(
                    root,
                    payload.entries,
                    updated_by="studio-user",
                    book_profile=payload.book_profile,
                ),
                "effect": "future-candidates",
                "review_required_for_existing_candidates": True,
            }
        )
        deps.invalidate_project(root, "rhythm-plan")
        return result

    return router
