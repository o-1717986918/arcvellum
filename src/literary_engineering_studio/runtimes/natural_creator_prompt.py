"""Versioned prompt layout. Reordering preserves all values and every array's order."""
import json
from copy import deepcopy

STABLE_PREFIX_LAYOUT = "stable-prefix-v2"
LEGACY_STABLE_PREFIX_LAYOUT = "stable-prefix-v1"
_SHARED = ("scene.v2.creator.bootstrap", "scene.v2.creator.delegation",
           "scene.v2.creator.archive", "scene.v2.creator.sandbox", "scene.v2.creator.selection")
_STABLE = ("briefing", "actor_card_context", "eligible_actor_refs", "eligible_actors",
           "free_character_subjects", "actor_card_schema", "actor_system_template",
           "available_delta_targets", "frozen_material_plan", "material_need_contract")


def stable_creator_prompt(layers, mode, context, *, include_actor, layout=STABLE_PREFIX_LAYOUT):
    guidance = "\n\n".join(layers[key] for key in _SHARED)
    value = deepcopy(context)
    if "briefing" in value:
        briefing = value["briefing"]
        leading = ("creator_persona", "style", "archive_tool", "schema")
        value["briefing"] = {**{k: briefing[k] for k in leading if k in briefing},
                             **{k: v for k, v in briefing.items() if k not in leading}}
    stable = _STABLE if layout == LEGACY_STABLE_PREFIX_LAYOUT else tuple(key for key in _STABLE if key not in {"actor_card_context", "frozen_material_plan"})
    ordered = {key: value.pop(key) for key in stable if key in value}
    ordered["phase_guidance"] = layers[f"scene.v2.creator.{mode}"]
    if include_actor:
        ordered["actor_card_design_guidance"] = layers["scene.v2.creator.actor-card"]
    ordered.update(value)
    return guidance + "\n\n本次创作资料：\n" + _json_ordered(ordered, canonical=layout != LEGACY_STABLE_PREFIX_LAYOUT)


def _json_ordered(value, *, canonical=False):
    # Keep the deliberately ordered top-level and briefing fields; nested object
    # formatting is deterministic without sorting source arrays or editing strings.
    if canonical:
        def nested(item):
            if isinstance(item, dict):
                return {key:nested(item[key]) for key in sorted(item)}
            if isinstance(item, list):
                return [nested(row) for row in item]
            return item
        value = {key:nested(item) for key,item in value.items()}
    return json.dumps(value, ensure_ascii=False)
