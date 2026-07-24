"""Safe, persistent definitions for OpenCode-compatible model connections.

Credentials never enter this module or the Studio configuration.  OpenCode owns
those in its local auth store.  Studio only persists the public connection
shape needed to recreate an isolated runner profile on later launches.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


COMMON_CONNECTION_PRESETS: tuple[dict[str, str], ...] = (
    {"id": "deepseek", "label": "DeepSeek", "group": "常用国内服务"},
    {"id": "zhipuai", "label": "智谱 AI（GLM）", "group": "常用国内服务"},
    {"id": "alibaba-cn", "label": "阿里云百炼（中国区）", "group": "常用国内服务"},
    {"id": "alibaba", "label": "Alibaba Model Studio（国际区）", "group": "常用国内服务"},
    {"id": "moonshotai-cn", "label": "月之暗面 Kimi（中国区）", "group": "常用国内服务"},
    {"id": "minimax-cn", "label": "MiniMax（中国区）", "group": "常用国内服务"},
    {"id": "siliconflow-cn", "label": "硅基流动（中国区）", "group": "常用国内服务"},
    {"id": "openai", "label": "OpenAI", "group": "国际服务"},
    {"id": "anthropic", "label": "Anthropic Claude", "group": "国际服务"},
    {"id": "google", "label": "Google Gemini", "group": "国际服务"},
    {"id": "openrouter", "label": "OpenRouter", "group": "国际服务"},
    {"id": "groq", "label": "Groq", "group": "国际服务"},
    {"id": "moonshotai", "label": "Moonshot AI（国际区）", "group": "国际服务"},
    {"id": "minimax", "label": "MiniMax（国际区）", "group": "国际服务"},
    {"id": "siliconflow", "label": "SiliconFlow（国际区）", "group": "国际服务"},
)


def connection_presets() -> list[dict[str, str]]:
    """Return UI-safe preset metadata without making it a source of truth for models."""

    return [dict(item) for item in COMMON_CONNECTION_PRESETS]


def custom_provider_definitions(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return validated custom provider records keyed by their OpenCode ID."""

    settings = _opencode_settings(config)
    entries = settings.get("custom_providers")
    if not isinstance(entries, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in entries:
        if not isinstance(item, dict):
            continue
        try:
            normalized = normalize_custom_provider(item)
        except ValueError:
            continue
        result[normalized["id"]] = normalized
    return result


def register_custom_provider(config: dict[str, Any], definition: dict[str, Any]) -> dict[str, Any]:
    """Store a credential-free OpenAI-compatible provider definition in config."""

    normalized = normalize_custom_provider(definition)
    runners = config.setdefault("agent_runners", {})
    if not isinstance(runners, dict):
        raise ValueError("agent runner configuration is invalid")
    settings = runners.setdefault("opencode", {})
    if not isinstance(settings, dict):
        raise ValueError("OpenCode configuration is invalid")
    current = custom_provider_definitions(config)
    current[normalized["id"]] = normalized
    settings["custom_providers"] = [current[key] for key in sorted(current)]
    return normalized


def opencode_provider_overrides(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Translate stored definitions to the public OpenCode profile schema."""

    result: dict[str, dict[str, Any]] = {}
    for provider_id, item in custom_provider_definitions(config).items():
        models: dict[str, dict[str, Any]] = {}
        for model in item["models"]:
            detail: dict[str, Any] = {"name": model["name"]}
            limits: dict[str, int] = {}
            if model.get("context"):
                limits["context"] = int(model["context"])
            if model.get("output"):
                limits["output"] = int(model["output"])
            if limits:
                detail["limit"] = limits
            models[model["id"]] = detail
        result[provider_id] = {
            "npm": "@ai-sdk/openai-compatible",
            "name": item["name"],
            "options": {"baseURL": item["base_url"]},
            "models": models,
        }
    return result


def normalize_custom_provider(value: dict[str, Any]) -> dict[str, Any]:
    """Validate one public custom-provider definition before it reaches a profile."""

    provider_id = _provider_id(value.get("id") or value.get("provider_id"))
    name = str(value.get("name") or value.get("display_name") or provider_id).strip()
    if not name or len(name) > 80:
        raise ValueError("custom provider name must contain between 1 and 80 characters")
    base_url = _base_url(value.get("base_url"))
    raw_models = value.get("models")
    if not isinstance(raw_models, list) or not raw_models:
        raise ValueError("custom provider requires at least one model")
    if len(raw_models) > 30:
        raise ValueError("custom provider supports at most 30 models")
    models: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_models:
        if not isinstance(raw, dict):
            raise ValueError("custom provider models must be objects")
        model_id = str(raw.get("id") or "").strip()
        if not model_id or len(model_id) > 180 or any(char.isspace() for char in model_id):
            raise ValueError("custom model id must be a non-empty, whitespace-free value")
        if model_id in seen:
            raise ValueError("custom model ids must be unique")
        seen.add(model_id)
        model_name = str(raw.get("name") or model_id).strip()
        if not model_name or len(model_name) > 120:
            raise ValueError("custom model display name must contain between 1 and 120 characters")
        context = _positive_int(raw.get("context"), "custom model context", maximum=10_000_000)
        output = _positive_int(raw.get("output"), "custom model output", maximum=2_000_000)
        models.append({"id": model_id, "name": model_name, "context": context, "output": output})
    return {"id": provider_id, "name": name, "base_url": base_url, "models": models}


def _opencode_settings(config: dict[str, Any]) -> dict[str, Any]:
    runners = config.get("agent_runners") if isinstance(config.get("agent_runners"), dict) else {}
    return runners.get("opencode") if isinstance(runners.get("opencode"), dict) else {}


def _provider_id(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized or len(normalized) > 64 or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for char in normalized):
        raise ValueError("custom provider id must use lowercase letters, numbers, hyphens, or underscores")
    return normalized


def _base_url(value: Any) -> str:
    normalized = str(value or "").strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or len(normalized) > 1024:
        raise ValueError("custom provider base URL must be a valid http or https URL")
    return normalized


def _positive_int(value: Any, label: str, *, maximum: int) -> int:
    if value in (None, ""):
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a whole number") from exc
    if number < 1 or number > maximum:
        raise ValueError(f"{label} must be between 1 and {maximum}")
    return number
