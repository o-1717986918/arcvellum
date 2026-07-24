"""Application, static UI and configuration endpoints for the legacy Engine API."""

from __future__ import annotations

from pathlib import Path

from ...model_config import as_env_exports, config_path, default_config, load_config, redacted_effective_config, save_config
from ..common import frontend_file, require_api_token
from ..models import SaveConfigRequest

try:
    from fastapi import APIRouter, Request
    from fastapi.responses import HTMLResponse
except ImportError:  # pragma: no cover - optional HTTP dependency
    APIRouter = None
    Request = object
    HTMLResponse = None


def build_application_router(*, version: str, api_token: str, allowed_roots: list[Path]):
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    def ui_root():
        return frontend_file("index.html", "text/html; charset=utf-8")

    @router.get("/ui/{path:path}")
    def ui_asset(path: str):
        suffix = Path(path).suffix.lower()
        content_type = {
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".svg": "image/svg+xml; charset=utf-8",
        }.get(suffix, "text/plain; charset=utf-8")
        return frontend_file(path, content_type)

    @router.get("/health")
    def health():
        return {
            "ok": True,
            "version": version,
            "auth_required": bool(api_token),
            "allowed_roots": [str(root) for root in allowed_roots],
        }

    @router.get("/config")
    def get_config(http_request: Request):
        require_api_token(http_request, api_token)
        return redacted_effective_config()

    @router.post("/config")
    def update_config(payload: SaveConfigRequest, http_request: Request):
        require_api_token(http_request, api_token)
        existing = load_config()
        existing["active_profile"] = payload.active_profile
        existing["profiles"] = merge_profiles_preserving_api_keys(existing.get("profiles", {}), payload.profiles)
        existing["defaults"] = payload.defaults or existing.get("defaults", {})
        path = save_config(existing)
        return {"ok": True, "config_path": str(path), "effective": redacted_effective_config()}

    @router.post("/config/default")
    def write_default_config(http_request: Request):
        require_api_token(http_request, api_token)
        path = save_config(default_config())
        return {"ok": True, "config_path": str(path), "effective": redacted_effective_config()}

    @router.get("/config/env")
    def config_env(http_request: Request):
        require_api_token(http_request, api_token)
        return {"config_path": str(config_path()), "exports": as_env_exports()}

    return router


def merge_profiles_preserving_api_keys(existing: object, incoming: object) -> dict[str, object]:
    current = existing if isinstance(existing, dict) else {}
    updates = incoming if isinstance(incoming, dict) else {}
    if not updates:
        return dict(current)
    merged = dict(current)
    for name, profile in updates.items():
        if not isinstance(profile, dict):
            merged[name] = profile
            continue
        previous = current.get(name, {}) if isinstance(current.get(name, {}), dict) else {}
        item = dict(previous)
        item.update(profile)
        if not str(profile.get("api_key", "") or "").strip():
            previous_key = str(previous.get("api_key", "") or "").strip()
            if previous_key:
                item["api_key"] = previous_key
            else:
                item.pop("api_key", None)
        item.pop("api_key_set", None)
        merged[name] = item
    return merged
