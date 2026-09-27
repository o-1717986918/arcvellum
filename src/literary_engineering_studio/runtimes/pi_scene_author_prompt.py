"""Pure create/revision prompt rendering for a lean scene author."""

from __future__ import annotations

import json
from typing import Any

from literary_engineering_studio_engine.public.literary import CreativeResult, ReviewResult, SceneBrief, VerificationReport
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec, render_prompt_template, scene_prompt_fallback
from ..runtime.prompt_recipes import lean_scene_prompt_recipe
from .pi_scene_prompt_rules import QUANTITATIVE_DETAIL_RULE as _QUANTITATIVE_DETAIL_RULE

def render_scene_create_prompt(
    brief: SceneBrief,
    *,
    source_evidence: str = "",
    allowed_refs: Any = (),
    style_reference_block: str = "",
    expression_context_block: str = "",
    performance_material_block: str = "",
    allow_material_requests: bool = False,
    creative_intent_block: str = "",
    creator_memory_block: str = "",
    literary_guidance: str = "",
) -> str:
    recipe = lean_scene_prompt_recipe("create")
    reference_contract = _reference_contract(brief, allowed_refs)
    material_section = _material_section(performance_material_block, "Character And Environment Candidate Materials")
    material_final_pass, material_length_priority = _create_material_guidance(bool(performance_material_block))
    request_guidance = _create_request_guidance(allow_material_requests, performance_material_block)
    literary_guidance = _creator_literary_guidance("scene.creator.create", literary_guidance)
    prompt = render_prompt_template("scene.creator.create.protocol", (
        literary_guidance,
        json.dumps(brief.to_dict(), ensure_ascii=False, separators=(',', ':')),
        creative_intent_block or scene_prompt_fallback("create.intent"),
        creator_memory_block or scene_prompt_fallback("create.memory"),
        expression_context_block or scene_prompt_fallback("create.expression"),
        source_evidence or scene_prompt_fallback("create.sources"),
        style_reference_block or scene_prompt_fallback("create.style"),
        material_section,
        json.dumps(reference_contract, ensure_ascii=False, separators=(',', ':')),
        brief.length.target_hanzi,
        brief.length.soft_min,
        brief.length.soft_max,
        material_length_priority,
        request_guidance,
        material_final_pass,
        _QUANTITATIVE_DETAIL_RULE,
    ))
    if len(prompt) > recipe.hard_character_limit:
        raise ValueError("lean scene create prompt exceeds hard character limit")
    return prompt


def render_scene_revision_prompt(
    brief: SceneBrief,
    result: CreativeResult,
    verification: VerificationReport,
    review: ReviewResult | None,
    *,
    source_evidence: str = "",
    allowed_refs: Any = (),
    style_reference_block: str = "",
    expression_context_block: str = "",
    performance_material_block: str = "",
    allow_material_requests: bool = False,
    creative_intent_block: str = "",
    creator_memory_block: str = "",
    literary_guidance: str = "",
) -> str:
    recipe = lean_scene_prompt_recipe("revise")
    instructions = list(review.revision_instructions) if review is not None else []
    reference_contract = _reference_contract(brief, allowed_refs)
    material_section = _material_section(performance_material_block, "Original First-Level Character And Environment Materials")
    request_guidance = _revision_request_guidance(allow_material_requests, performance_material_block)
    literary_guidance = _creator_literary_guidance("scene.creator.revise", literary_guidance)
    prompt = render_prompt_template("scene.creator.revise.protocol", (
        literary_guidance,
        json.dumps(brief.to_dict(), ensure_ascii=False, separators=(',', ':')),
        creative_intent_block or scene_prompt_fallback("revise.intent"),
        creator_memory_block or scene_prompt_fallback("revise.memory"),
        expression_context_block or scene_prompt_fallback("revise.expression"),
        result.prose,
        json.dumps(result.scene_delta.to_dict(), ensure_ascii=False, separators=(',', ':')),
        json.dumps(verification.to_dict(), ensure_ascii=False, separators=(',', ':')),
        json.dumps(instructions, ensure_ascii=False, separators=(',', ':')),
        source_evidence or scene_prompt_fallback("revise.sources"),
        style_reference_block or scene_prompt_fallback("revise.style"),
        material_section,
        json.dumps(reference_contract, ensure_ascii=False, separators=(',', ':')),
        brief.length.target_hanzi,
        brief.length.soft_min,
        brief.length.soft_max,
        request_guidance,
        _QUANTITATIVE_DETAIL_RULE,
    ))
    if len(prompt) > recipe.hard_character_limit:
        raise ValueError("lean scene revision prompt exceeds hard character limit")
    return prompt


def _reference_contract(brief: SceneBrief, allowed_refs: Any) -> list[str]:
    supplied = {str(item).strip() for item in allowed_refs if str(item).strip()}
    if not supplied:
        supplied.update(brief.source_refs)
        supplied.update(brief.canon_constraints)
        supplied.update(brief.chapter_obligations)
        supplied.update(brief.participants)
    return sorted(item for item in supplied if item)


def _creator_literary_guidance(stage_layer_id: str, supplied: str) -> str:
    if supplied.strip():
        return supplied
    return "\n\n".join((prompt_layer_spec("scene.creator.identity").default_text,
                        prompt_layer_spec(stage_layer_id).default_text))


def _material_section(materials: str, heading: str) -> str:
    return f"## {heading}\n{materials}\n\n" if materials else ""


def _create_material_guidance(has_materials: bool) -> tuple[str, str]:
    if not has_materials:
        return "", ""
    return (prompt_layer_spec("scene.creator.material-final-pass.protocol").default_text,
            prompt_layer_spec("scene.creator.material-length-priority.protocol").default_text)


def _create_request_guidance(allow_material_requests: bool, performance_material_block: str) -> str:
    return (prompt_layer_spec("scene.creator.material-request.protocol").default_text + "\n"
            if allow_material_requests or performance_material_block else "")


def _revision_request_guidance(allow_material_requests: bool, performance_material_block: str) -> str:
    return (prompt_layer_spec("scene.creator.revision-request.protocol").default_text + "\n"
            if allow_material_requests or performance_material_block else "")


__all__ = ["render_scene_create_prompt", "render_scene_revision_prompt"]
