"""Local Studio configuration without model-provider credentials."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


CONFIG_SCHEMA = "literary-engineering-studio/config/v0.1"


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


def discover_core_repo() -> Path | None:
    override = os.environ.get("LEW_CORE_REPO", "").strip()
    candidates = [
        Path(override).expanduser() if override else None,
        repository_root().parent / "literary-engineering-project-skill",
    ]
    for candidate in candidates:
        if candidate and (candidate / "src" / "literary_engineering_workbench").is_dir():
            return candidate.resolve()
    return None


def default_config() -> dict[str, Any]:
    core_repo = discover_core_repo()
    return {
        "schema": CONFIG_SCHEMA,
        "core": {
            "repo": str(core_repo) if core_repo else "",
            "python": sys.executable,
            "module": "literary_engineering_workbench",
        },
        "worker": {
            "runs_root": str(default_runs_root()),
            "timeout_seconds": 1800,
            "auto_run_task_command": True,
            "pause_on_human_gate": True,
        },
        "runtimes": {
            "host-agent": {"enabled": True},
            "claude-code": {
                "enabled": True,
                "executable": "claude.cmd" if os.name == "nt" else "claude",
                "permission_mode": "acceptEdits",
            },
            "codex-cli": {
                "enabled": True,
                "executable": "codex",
                "sandbox": "workspace-write",
            },
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
    merged = _deep_merge(base, payload)
    merged["schema"] = CONFIG_SCHEMA
    return merged


def save_config(data: dict[str, Any], path: Path | None = None) -> Path:
    target = (path or default_config_path()).resolve()
    payload = _deep_merge(default_config(), data)
    payload["schema"] = CONFIG_SCHEMA
    _assert_no_model_credentials(payload)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def core_repo_from_config(config: dict[str, Any]) -> Path:
    value = str(config.get("core", {}).get("repo", "") or "").strip()
    if not value:
        raise FileNotFoundError("Literary Engineering core repo is not configured. Set core.repo or LEW_CORE_REPO.")
    path = Path(value).expanduser().resolve()
    if not (path / "src" / "literary_engineering_workbench").is_dir():
        raise FileNotFoundError(f"Literary Engineering core repo is invalid: {path}")
    return path


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def _assert_no_model_credentials(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    forbidden = ("api_key", "apikey", "model_provider", "deepseek_api", "openai_api")
    found = [token for token in forbidden if token in serialized]
    if found:
        raise ValueError(
            "Studio configuration must not contain model-provider credentials or API configuration: "
            + ", ".join(found)
        )

