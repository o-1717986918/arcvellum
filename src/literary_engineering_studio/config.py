"""Local Studio configuration without model-provider credentials."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


CONFIG_SCHEMA = "literary-engineering-studio/config/v0.3"


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_config_path() -> Path:
    override = os.environ.get("LES_CONFIG_PATH", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".literary-engineering-studio" / "config.json"


def default_runs_root() -> Path:
    override = os.environ.get("LES_RUNS_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".literary-engineering-studio" / "runs"


def default_data_root() -> Path:
    override = os.environ.get("LES_DATA_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".literary-engineering-studio"


def default_config() -> dict[str, Any]:
    return {
        "schema": CONFIG_SCHEMA,
        "engine": {
            "python": sys.executable,
            "module": "literary_engineering_studio_engine",
        },
        "application": {
            "data_root": str(default_data_root()),
            "database_path": str(default_data_root() / "studio.sqlite3"),
            "max_workers": 2,
            "lease_seconds": 90,
        },
        "worker": {
            "runs_root": str(default_runs_root()),
            "timeout_seconds": 1800,
            "auto_run_task_command": True,
            "pause_on_human_gate": True,
        },
        "agent_runners": {
            "opencode": {
                "enabled": True,
                "executable": "",
                "model": "opencode/big-pickle",
                "data_root": str(default_data_root()),
            },
            "host-agent": {"enabled": True},
            "claude-code": {
                "enabled": True,
                "executable": "claude.cmd" if os.name == "nt" else "claude",
                "permission_mode": "acceptEdits",
                "model": "",
                "max_budget_usd": 2.0,
            },
            "codex-cli": {
                "enabled": True,
                "executable": "codex",
                "sandbox": "workspace-write",
            },
        },
        "model_connections": {
            "managed_by": "agent-runner",
            "connections": [
                {
                    "connection_id": "opencode-starter",
                    "provider_family": "opencode",
                    "connection_method": "bundled-free-provider",
                    "agent_runner": "opencode",
                    "authentication_state": "runner-managed",
                    "selected_model": "opencode/big-pickle",
                    "available_models": [],
                    "endpoint_health": "probe-required",
                    "privacy_class": "cloud",
                    "detail": "Starter connection; availability and limits are verified by the bundled Runner."
                }
            ],
        },
        "server": {
            "host": "127.0.0.1",
            "port": 8791,
        },
    }


def load_config(path: Path | None = None) -> dict[str, Any]:
    target = (path or default_config_path()).resolve()
    base = default_config()
    if not target.exists():
        return base
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"invalid Studio config: {target}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Studio config must be a JSON object: {target}")
    payload = _migrate_config(payload)
    payload.pop("core", None)
    merged = _deep_merge(base, payload)
    merged["schema"] = CONFIG_SCHEMA
    return merged


def save_config(data: dict[str, Any], path: Path | None = None) -> Path:
    target = (path or default_config_path()).resolve()
    payload = _deep_merge(default_config(), _migrate_config(dict(data)))
    payload.pop("core", None)
    payload["schema"] = CONFIG_SCHEMA
    _assert_no_model_credentials(payload)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def _migrate_config(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(payload)
    legacy_runtimes = migrated.pop("runtimes", None)
    if isinstance(legacy_runtimes, dict) and not isinstance(migrated.get("agent_runners"), dict):
        migrated["agent_runners"] = legacy_runtimes
    return migrated


def _assert_no_model_credentials(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    forbidden = ("api_key", "apikey", "model_provider", "deepseek_api", "openai_api")
    found = [token for token in forbidden if token in serialized]
    if found:
        raise ValueError(
            "Studio configuration must not contain model-provider credentials or API configuration: "
            + ", ".join(found)
        )
