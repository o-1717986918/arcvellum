"""Versioned work-level creative loading choices, resolved by all entry points."""
import json
from pathlib import Path
from copy import deepcopy
from literary_engineering_studio_engine.public.projects import atomic_write_batch


def read_creative_configuration(root: Path):
    path = root.resolve() / "workflow/studio/creative_configuration.json"
    if not path.is_file():
        return {"schema": "arcvellum/creative-configuration/v1", "revision": 0, "overrides": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "arcvellum/creative-configuration/v1":
        raise ValueError("unknown work creative configuration schema")
    return value


def save_creative_configuration(root: Path, overrides, *, expected_revision):
    root = root.resolve()
    if not (root / "project.yaml").is_file():
        raise ValueError("creative configuration requires a work project")
    if set(overrides) - {"scene_creator_v2", "less_ai_tone_experiment"} or any(type(v) is not bool for v in overrides.values()):
        raise ValueError("creative overrides require supported boolean flags")
    prior = read_creative_configuration(root)
    if prior["revision"] != expected_revision:
        raise ValueError("creative configuration changed; reload current version")
    value = {**prior, "revision": expected_revision + 1, "overrides": overrides}
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    directory = root / "workflow/studio"
    atomic_write_batch({directory / "creative_configuration.json": text,
                        directory / "creative_configuration_history" / f"{value['revision']}.json": text})
    return value


def effective_creative_config(config, root: Path):
    result = deepcopy(config)
    overrides = read_creative_configuration(root)["overrides"]
    for key, enabled in overrides.items():
        result.setdefault("application", {}).setdefault(key, {})["enabled"] = enabled
    return result
