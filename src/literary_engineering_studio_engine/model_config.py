"""Global model provider configuration for the workbench."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONFIG_ENV = "LEW_CONFIG_PATH"
DEFAULT_CONFIG_PATH = Path.home() / ".lew" / "config.json"
MODEL_PROVIDER_CHOICES = {"auto", "dry-run", "http-chat"}


@dataclass(frozen=True)
class ModelSettings:
    api_base: str
    model: str
    api_key: str
    api_key_env: str
    temperature: float
    max_tokens: int
    timeout: float
    active_profile: str
    config_path: Path


def config_path() -> Path:
    custom = os.environ.get(CONFIG_ENV, "").strip()
    return Path(custom).expanduser().resolve() if custom else DEFAULT_CONFIG_PATH


def default_config() -> dict[str, Any]:
    return {
        "schema": "literary-engineering-workbench/global-config/v0.1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "active_profile": "deepseek",
        "profiles": {
            "deepseek": {
            "provider": "http-chat",
            "api_base": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "api_key_env": "DEEPSEEK_API_KEY",
            "api_key": "",
            "temperature": 0.4,
            "max_tokens": 4000,
            "timeout": 120,
            }
        },
        "defaults": {
            "project_root": "",
            "style_library_root": str(Path.home() / ".lew" / "style-library"),
            "scene": "scenes/scene_0001.yaml",
            "chapter_id": "chapter_0001",
            "workflow_mode": "scene-loop",
        },
    }


def ensure_config(path: Path | None = None) -> Path:
    target = path or config_path()
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(default_config(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def load_config(path: Path | None = None) -> dict[str, Any]:
    target = ensure_config(path)
    return json.loads(target.read_text(encoding="utf-8"))


def save_config(data: dict[str, Any], path: Path | None = None) -> Path:
    target = path or config_path()
    normalized = normalize_config(data)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def normalize_config(data: dict[str, Any]) -> dict[str, Any]:
    base = default_config()
    merged = {**base, **data}
    profiles = dict(base.get("profiles", {}))
    profiles.update(data.get("profiles", {}) if isinstance(data.get("profiles"), dict) else {})
    merged["profiles"] = profiles
    defaults = dict(base.get("defaults", {}))
    defaults.update(data.get("defaults", {}) if isinstance(data.get("defaults"), dict) else {})
    merged["defaults"] = defaults
    active = str(merged.get("active_profile") or "deepseek")
    if active not in profiles:
        profiles[active] = {
            "provider": "http-chat",
            "api_base": "",
            "model": "",
            "api_key_env": "LEW_MODEL_API_KEY",
            "api_key": "",
            "temperature": 0.4,
            "max_tokens": 2500,
            "timeout": 60,
        }
    merged["active_profile"] = active
    merged["schema"] = "literary-engineering-workbench/global-config/v0.1"
    merged["updated_at"] = datetime.now(timezone.utc).isoformat()
    return merged


def get_model_settings(default_temperature: float = 0.4, default_max_tokens: int = 2500) -> ModelSettings:
    cfg = load_config()
    active = str(cfg.get("active_profile") or "deepseek")
    profiles = cfg.get("profiles", {}) if isinstance(cfg.get("profiles"), dict) else {}
    profile = profiles.get(active, {}) if isinstance(profiles.get(active, {}), dict) else {}

    api_base = os.environ.get("LEW_MODEL_API_BASE", "").strip() or str(profile.get("api_base", "")).strip()
    model = os.environ.get("LEW_MODEL_NAME", "").strip() or str(profile.get("model", "")).strip()
    api_key_env = str(profile.get("api_key_env", "LEW_MODEL_API_KEY") or "LEW_MODEL_API_KEY").strip()
    api_key = (
        os.environ.get("LEW_MODEL_API_KEY", "").strip()
        or os.environ.get(api_key_env, "").strip()
        or str(profile.get("api_key", "")).strip()
    )
    timeout = _float_env("LEW_MODEL_TIMEOUT", profile.get("timeout", 60), 60)
    temperature = _float_env("LEW_MODEL_TEMPERATURE", profile.get("temperature", default_temperature), default_temperature)
    max_tokens = _int_env("LEW_MODEL_MAX_TOKENS", profile.get("max_tokens", default_max_tokens), default_max_tokens)
    return ModelSettings(
        api_base=api_base,
        model=model,
        api_key=api_key,
        api_key_env=api_key_env,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        active_profile=active,
        config_path=config_path(),
    )


def resolve_model_provider(provider: str = "auto", *, purpose: str = "LLM task") -> str:
    """Resolve auto/http-chat/dry-run into the concrete provider used for execution."""

    requested = (provider or "auto").strip()
    if requested not in MODEL_PROVIDER_CHOICES:
        raise ValueError(f"unknown provider: {provider}. valid: {', '.join(sorted(MODEL_PROVIDER_CHOICES))}")
    if requested != "auto":
        return requested

    settings = get_model_settings()
    missing = []
    if not settings.api_base:
        missing.append("api_base")
    if not settings.model:
        missing.append("model")
    if not settings.api_key:
        missing.append(f"api_key via LEW_MODEL_API_KEY, {settings.api_key_env}, or saved profile api_key")
    if missing:
        raise RuntimeError(
            f"{purpose} provider=auto requires a configured real LLM profile; missing "
            + ", ".join(missing)
            + ". Configure API Base, Model, and API Key in the frontend global config, "
            "or pass provider='dry-run' only for offline debugging."
        )
    return "http-chat"


def redacted_effective_config() -> dict[str, Any]:
    settings = get_model_settings()
    cfg = load_config()
    profiles = _redacted_profiles(cfg.get("profiles", {}))
    result = {
        "config_path": str(settings.config_path),
        "active_profile": settings.active_profile,
        "api_base": settings.api_base,
        "model": settings.model,
        "api_key_env": settings.api_key_env,
        "api_key_available": bool(settings.api_key),
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "timeout": settings.timeout,
        "defaults": cfg.get("defaults", {}),
        "profiles": profiles,
    }
    return result


def as_env_exports(settings: ModelSettings | None = None) -> dict[str, str]:
    value = settings or get_model_settings()
    return {
        "LEW_MODEL_API_BASE": value.api_base,
        "LEW_MODEL_NAME": value.model,
        "LEW_MODEL_API_KEY": f"<from LEW_MODEL_API_KEY, {value.api_key_env}, or saved profile api_key; available={str(bool(value.api_key)).lower()}>",
        "LEW_MODEL_TEMPERATURE": str(value.temperature),
        "LEW_MODEL_MAX_TOKENS": str(value.max_tokens),
        "LEW_MODEL_TIMEOUT": str(value.timeout),
    }


def _float_env(name: str, value: Any, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    candidate = raw if raw else value
    try:
        return float(candidate)
    except (TypeError, ValueError):
        return default


def _int_env(name: str, value: Any, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    candidate = raw if raw else value
    try:
        return int(candidate)
    except (TypeError, ValueError):
        return default


def settings_as_dict(settings: ModelSettings) -> dict[str, Any]:
    data = asdict(settings)
    data["config_path"] = str(settings.config_path)
    data["api_key"] = "<redacted>" if settings.api_key else ""
    return data


def _redacted_profiles(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    redacted: dict[str, Any] = {}
    for name, profile in value.items():
        if not isinstance(profile, dict):
            redacted[name] = profile
            continue
        item = dict(profile)
        api_key = str(item.pop("api_key", "") or "").strip()
        item["api_key_set"] = bool(api_key)
        redacted[name] = item
    return redacted
