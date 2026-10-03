"""Stable prompt registry and structured-output schema API."""

from ..prompting.agents.schema import load_schema_spec, validate_payload
from ..prompting.registry import list_prompt_assets, resolve_prompt_asset
from ..prompting.layers import (
    PromptLayerOverride, PromptLayerSpec, ResolvedPromptLayer,
    list_prompt_layer_specs, prompt_assembly_manifest, prompt_layer_spec, render_prompt_template, render_prompt_text,
    scene_prompt_fallback,
    resolve_prompt_layer,
)

__all__ = [
    "list_prompt_assets",
    "load_schema_spec",
    "resolve_prompt_asset",
    "PromptLayerOverride",
    "PromptLayerSpec",
    "ResolvedPromptLayer",
    "list_prompt_layer_specs",
    "prompt_assembly_manifest",
    "prompt_layer_spec",
    "render_prompt_template",
    "render_prompt_text",
    "scene_prompt_fallback",
    "resolve_prompt_layer",
    "validate_payload",
]
