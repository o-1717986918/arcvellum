"""Public application metadata and credential-safe diagnostic reports."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
from typing import Any

from . import __version__
from .config import default_config_path, default_data_root
from .model_connections import model_connection_status
from .opencode_binary import locate_opencode, verify_opencode
from .project_manager import list_projects
from .runtimes import agent_runner_status


APPLICATION_INFO_SCHEMA = "arcvellum/application-info/v0.1"
DIAGNOSTIC_SCHEMA = "arcvellum/diagnostic-report/v0.1"


def build_application_info(config: dict[str, Any]) -> dict[str, Any]:
    data_root = _configured_data_root(config)
    opencode_settings = _opencode_settings(config)
    executable = locate_opencode(opencode_settings)
    verification = verify_opencode(executable) if executable else {}
    updates = config.get("updates") if isinstance(config.get("updates"), dict) else {}
    return {
        "ok": True,
        "schema": APPLICATION_INFO_SCHEMA,
        "product_name": "ArcVellum",
        "product_tagline": "长篇文学创作观测台",
        "version": __version__,
        "build_number": os.environ.get("ARCVELLUM_BUILD_NUMBER", "development"),
        "release_channel": str(updates.get("channel") or "stable"),
        "last_update_check": str(updates.get("last_checked_at") or ""),
        "engine": {
            "name": "Literary Engineering Core",
            "protocol_version": "v0.3",
        },
        "opencode": {
            "installed": executable is not None,
            "version": str(verification.get("version") or ""),
            "verified": bool(verification.get("verified")),
        },
        "current_model": _selected_model(config),
        "paths": {
            "configuration": str(default_config_path()),
            "application_data": str(data_root),
            "logs": str(data_root / "logs"),
            "diagnostics": str(data_root / "diagnostics"),
        },
        "license": "MIT",
        "third_party_notices": [
            "OpenCode is distributed under its own license and notice.",
            "Tauri, Vue, FastAPI and other dependencies retain their respective licenses.",
        ],
        "privacy": "作品与流程数据保存在本机；模型请求由用户选择的 Agent Runner 和模型服务处理。",
    }


def build_diagnostic_report(config: dict[str, Any], lifecycle, bootstrap) -> dict[str, Any]:
    application = build_application_info(config)
    lifecycle_state = _safe_call(lifecycle.health)
    bootstrap_state = _safe_call(bootstrap.snapshot)
    projects = _safe_call(list_projects)
    project_items = projects.get("projects") if isinstance(projects.get("projects"), list) else []
    return {
        "schema": DIAGNOSTIC_SCHEMA,
        "generated_at": _now(),
        "application": application,
        "system": {
            "platform": platform.system(),
            "release": platform.release(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
        },
        "health": _redact(lifecycle_state),
        "bootstrap": {
            "phase": bootstrap_state.get("phase", "unknown"),
            "ready": bool(bootstrap_state.get("ready")),
            "degraded": bool(bootstrap_state.get("degraded")),
            "steps": bootstrap_state.get("steps", []),
            "notices": bootstrap_state.get("notices", []),
        },
        "agent_runners": _redact(agent_runner_status(config)),
        "model_connections": _redact(model_connection_status(config)),
        "configuration": _redact(_diagnostic_config(config)),
        "projects": {
            "count": len(project_items),
            "current": _path_fingerprint(str(projects.get("current_project") or "")),
            "items": [
                {
                    "title": str(item.get("title") or ""),
                    "status": str(item.get("status") or ""),
                    "path_fingerprint": _path_fingerprint(str(item.get("path") or "")),
                }
                for item in project_items[:24]
                if isinstance(item, dict)
            ],
        },
        "exclusions": [
            "API credentials and authentication tokens",
            "full project paths",
            "manuscript prose and private project contents",
            "raw Agent prompts and responses",
        ],
    }


def export_diagnostic_report(config: dict[str, Any], lifecycle, bootstrap) -> Path:
    root = _configured_data_root(config) / "diagnostics"
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = root / f"arcvellum-diagnostic-{timestamp}.json"
    target.write_text(
        json.dumps(build_diagnostic_report(config, lifecycle, bootstrap), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def _configured_data_root(config: dict[str, Any]) -> Path:
    application = config.get("application") if isinstance(config.get("application"), dict) else {}
    return Path(str(application.get("data_root") or default_data_root())).expanduser().resolve()


def _opencode_settings(config: dict[str, Any]) -> dict[str, object]:
    runners = config.get("agent_runners") if isinstance(config.get("agent_runners"), dict) else {}
    values = runners.get("opencode") if isinstance(runners.get("opencode"), dict) else {}
    return values


def _selected_model(config: dict[str, Any]) -> str:
    return str(_opencode_settings(config).get("model") or "")


def _diagnostic_config(config: dict[str, Any]) -> dict[str, Any]:
    allowed = {"schema", "application", "worker", "agent_runners", "model_connections", "server", "updates"}
    return {key: value for key, value in config.items() if key in allowed}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("key", "token", "secret", "password", "credential")):
                result[str(key)] = "[redacted]"
            elif lowered in {"project_root", "path", "workspace", "cwd"} and isinstance(item, str):
                result[str(key)] = _path_fingerprint(item)
            else:
                result[str(key)] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and ("sk-" in value.lower() or "bearer " in value.lower()):
        return "[redacted]"
    return value


def _path_fingerprint(value: str) -> str:
    if not value:
        return ""
    path = Path(value).expanduser()
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]
    return f"{path.name or 'root'}#{digest}"


def _safe_call(function) -> dict[str, Any]:
    try:
        value = function()
        return value if isinstance(value, dict) else {"value": value}
    except Exception as exc:
        return {"error_class": type(exc).__name__, "detail": str(exc)}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
