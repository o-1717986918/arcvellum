"""Literary review prompt, separate from the Pi scene transaction adapter."""

from __future__ import annotations

import json

from literary_engineering_studio_engine.public.literary import CreativeResult, SceneBrief, VerificationReport
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec, render_prompt_template, scene_prompt_fallback

from ..runtime.prompt_recipes import lean_scene_prompt_recipe
from .pi_scene_prompt_rules import QUANTITATIVE_DETAIL_RULE


def render_scene_review_prompt(
    brief: SceneBrief,
    result: CreativeResult,
    verification: VerificationReport,
    *,
    source_evidence: str = "",
    revision_attempts: int = 0,
    expression_context_block: str = "",
    performance_material_block: str = "",
    creative_intent_block: str = "",
    literary_guidance: str = "",
) -> str:
    recipe = lean_scene_prompt_recipe("review")
    convergence = (render_prompt_template("scene.review.convergence.strict.protocol", (revision_attempts,))
                   if revision_attempts >= 2 else
                   prompt_layer_spec("scene.review.convergence.normal.protocol").default_text)
    prompt = render_prompt_template("scene.review.protocol", (
        convergence,
        json.dumps(brief.to_dict(), ensure_ascii=False, separators=(',', ':')),
        creative_intent_block or scene_prompt_fallback("review.intent"),
        literary_guidance or prompt_layer_spec("scene.review").default_text,
        expression_context_block or scene_prompt_fallback("review.expression"),
        json.dumps(verification.to_dict(), ensure_ascii=False, separators=(',', ':')),
        result.prose,
        performance_material_block or scene_prompt_fallback("review.materials"),
        source_evidence or scene_prompt_fallback("review.sources"),
        QUANTITATIVE_DETAIL_RULE,
    ))
    if len(prompt) > recipe.hard_character_limit:
        raise ValueError("lean scene review prompt exceeds hard character limit")
    return prompt


__all__ = ["render_scene_review_prompt"]
