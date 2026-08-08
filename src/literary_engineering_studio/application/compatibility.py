"""Load the release compatibility manifest without duplicating its policy."""

from __future__ import annotations

from importlib.resources import files
import json
from typing import Any


COMPATIBILITY_SCHEMA = "arcvellum/compatibility-manifest/v1"


def load_compatibility_manifest() -> dict[str, Any]:
    resource = files(__package__).joinpath("compatibility_manifest.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != COMPATIBILITY_SCHEMA:
        raise RuntimeError("ArcVellum compatibility manifest is invalid")
    return payload


def compatibility_summary() -> dict[str, Any]:
    manifest = load_compatibility_manifest()
    defaults = manifest.get("runtime_defaults")
    defaults = defaults if isinstance(defaults, dict) else {}
    aliases = manifest.get("deprecated_aliases")
    providers = manifest.get("legacy_providers")
    return {
        "schema": COMPATIBILITY_SCHEMA,
        "default_agent_runtime": str(defaults.get("agent_runtime") or ""),
        "model_invocation": str(defaults.get("model_invocation") or ""),
        "scene_generation": str(defaults.get("scene_generation") or ""),
        "deprecated_alias_count": len(aliases) if isinstance(aliases, list) else 0,
        "legacy_provider_count": len(providers) if isinstance(providers, list) else 0,
        "minimum_compatibility_window": str(
            manifest.get("minimum_compatibility_window") or ""
        ),
    }
