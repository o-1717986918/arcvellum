"""Frozen prompt rendering and version selection for legacy scene transactions."""
from functools import wraps
import hashlib
import json
from pathlib import Path
from typing import Any
from literary_engineering_studio_engine.public.prompting import prompt_layer_scope

def _frozen_legacy_prompts(operation):
    @wraps(operation)
    def run(self, transaction_id, *args, **kwargs):
        if self._uses_creator_v2(transaction_id):
            return operation(self, transaction_id, *args, **kwargs)
        with prompt_layer_scope(self._prompt_snapshot(transaction_id)["texts"]):
            return operation(self, transaction_id, *args, **kwargs)
    return run


def _validated_prompt_assembly(path: Path) -> dict[str, Any] | None:
    saved = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    if saved is not None and (
        saved.get("schema") != "arcvellum/prompt-assembly/v1"
        or not isinstance(saved.get("texts"), dict)
    ):
        raise ValueError("scene prompt assembly cache is invalid")
    return saved


def _migrate_prompt_assembly(saved: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    old_layers = {entry["layer_id"]: entry for entry in saved.get("layers", [])
                  if isinstance(entry, dict) and isinstance(entry.get("layer_id"), str)}
    for entry in current["layers"]:
        old = old_layers.get(entry["layer_id"])
        if old and entry["layer_id"] in saved["texts"]:
            entry.update(old)
            current["texts"][entry["layer_id"]] = saved["texts"][entry["layer_id"]]
    current["digest"] = hashlib.sha256(
        json.dumps(current["layers"], sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    current["migration"] = "scene-layers-expanded-v2"
    return current


def direct_environment_identity(snapshot: dict[str, Any]) -> bool:
    return any(layer["layer_id"] == "scene.environment.identity" and int(layer["version"]) >= 2
               for layer in snapshot["layers"] if str(layer.get("version", "")).isdigit())
