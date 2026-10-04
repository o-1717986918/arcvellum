"""User preference for an independently frozen scene editing experiment."""
from copy import deepcopy
from pathlib import Path
from typing import Any
from .config import save_config


def get_less_ai_tone_preferences(config: dict[str, Any]) -> dict[str, Any]:
    settings = config.get("application", {}).get("less_ai_tone_experiment", {})
    data_root = Path(config["application"]["data_root"])
    return {"enabled": settings.get("enabled") is True, "rule_count": 11,
            "rule_source": "lieflat-less-ai-tone",
            "source_commit": "27d29232f10124db904ca9c0536d0b67cb3b2833",
            "prompt_layer_id": "experiment.less_ai_tone.editor",
            "audit_directory": str(data_root / "scene-transactions")}


def set_less_ai_tone_preferences(config: dict[str, Any], enabled: bool,
                                *, path: Path | None = None) -> dict[str, Any]:
    if type(enabled) is not bool:
        raise ValueError("experiment enabled must be a boolean")
    proposed = deepcopy(config)
    proposed.setdefault("application", {})["less_ai_tone_experiment"] = {"enabled": enabled}
    save_config(proposed, path)
    config.setdefault("application", {})["less_ai_tone_experiment"] = {"enabled": enabled}
    return get_less_ai_tone_preferences(config)
