"""Versioned prompt layout. Reordering preserves all values and every array's order."""
import json
from copy import deepcopy

STABLE_PREFIX_LAYOUT = "stable-prefix-v1"
_SHARED = ("scene.v2.creator.bootstrap", "scene.v2.creator.delegation",
           "scene.v2.creator.archive", "scene.v2.creator.sandbox", "scene.v2.creator.selection")
_STABLE = ("briefing", "actor_card_context", "eligible_actor_refs", "eligible_actors",
           "free_character_subjects", "actor_card_schema", "actor_system_template",
           "available_delta_targets", "frozen_material_plan", "material_need_contract")


def stable_creator_prompt(layers, mode, context, *, include_actor):
    guidance = "\n\n".join(layers[key] for key in _SHARED)
    value = deepcopy(context)
    if "briefing" in value:
        briefing = value["briefing"]
        leading = ("creator_persona", "style", "archive_tool", "schema")
        value["briefing"] = {**{k: briefing[k] for k in leading if k in briefing},
                             **{k: v for k, v in briefing.items() if k not in leading}}
    ordered = {key: value.pop(key) for key in _STABLE if key in value}
    ordered["phase_guidance"] = layers[f"scene.v2.creator.{mode}"]
    if include_actor:
        ordered["actor_card_design_guidance"] = layers["scene.v2.creator.actor-card"]
    ordered.update(value)
    return guidance + "\n\n本次创作资料：\n" + _json_ordered(ordered)


def _json_ordered(value):
    # Keep the deliberately ordered top-level and briefing fields; nested object
    # formatting is deterministic without sorting source arrays or editing strings.
    return json.dumps(value, ensure_ascii=False)
