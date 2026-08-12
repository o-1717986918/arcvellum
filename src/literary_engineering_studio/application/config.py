"""Local Studio configuration without model-provider credentials."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


CONFIG_SCHEMA = "literary-engineering-studio/config/v0.8"


def repository_root() -> Path:
    """Locate the checkout or frozen bundle root, not merely ``src/``.

    The application package lives below ``src/literary_engineering_studio``.
    Returning ``parents[2]`` after the module split pointed at ``src`` itself,
    so :class:`CoreBridge` did not detect a source checkout and could launch a
    stale installed sidecar.  Walk upward for the project sentinel instead.
    """

    current = Path(__file__).resolve()
    for candidate in current.parents:
        if (candidate / "pyproject.toml").is_file() and (candidate / "src").is_dir():
            return candidate
    # Frozen builds do not carry the source-layout sentinels.  This fallback
    # still resolves to the directory containing the bundled source tree.
    return current.parents[3]


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


def default_projects_root() -> Path:
    override = os.environ.get("LES_PROJECTS_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / "Documents" / "ArcVellum" / "Works"


def _default_worker_config() -> dict[str, Any]:
    return {
        "runs_root": str(default_runs_root()),
        "timeout_seconds": 1800,
        "max_repair_attempts": 2,
        "auto_run_task_command": True,
        "pause_on_human_gate": True,
        "prompt_program": {
            "mode": "enforced",
            "version": "v3",
            "enforcement": {
                "enabled": True,
                "runtimes": ["pi-worker"],
            },
            "fallback": "error",
            "lint": {
                "duplicate_warning_ratio": 0.15,
                "duplicate_error_ratio": 0.25,
            },
        },
        "execution_profile": {
            "mode": "shadow",
            "enforcement": {
                "enabled": False,
                "runtimes": ["pi-worker"],
                "routes": ["character-and-world-assets", "scene-development"],
                "states": ["asset-creation-agent-task", "candidate-review"],
                "task_kinds": ["creative", "review"],
            },
            "reasoning_budget": {
                "enabled": True,
                "max_escalations": 1,
            },
        },
        "prepared_context_cache": {
            "enabled": True,
            "max_entries": 32,
            "routes": ["scene-development"],
            "states": ["candidate-review"],
        },
        "context_budget": {
            "mode": "shadow",
            "legacy_max_inline_characters": 180000,
            "max_exact_on_demand_characters": 360000,
            "bounded_rollout": {
                "enabled": False,
                "routes": ["scene-development"],
                "states": ["candidate-review"],
                "contract_statuses": ["bounded-ready"],
            },
        },
    }


def _default_opencode_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "executable": "",
        "model": "opencode/big-pickle",
        "models": {
            "worker": "opencode/big-pickle",
            "advisor": "opencode/big-pickle",
            "steward": "opencode/big-pickle",
        },
        # Public endpoint/model definitions only. API keys remain in
        # OpenCode's credential store, never in this file.
        "custom_providers": [],
        "data_root": str(default_data_root()),
        "idle_timeout_seconds": 900,
        # Legacy reader compatibility. New runtimes use role-aware profiles.
        "session_idle_timeout_seconds": 120,
        "session_timeout_profiles": {
            "default": {"first_event_seconds": 180, "inter_event_seconds": 300},
            "worker": {"first_event_seconds": 180, "inter_event_seconds": 360},
            "reviewer": {"first_event_seconds": 240, "inter_event_seconds": 360},
            "planner": {"first_event_seconds": 240, "inter_event_seconds": 360},
            "advisor": {"first_event_seconds": 120, "inter_event_seconds": 180},
            "steward": {"first_event_seconds": 120, "inter_event_seconds": 180},
        },
        # Repair turns are concise file fixes rather than long-form generation.
        "repair_idle_timeout_seconds": 75,
    }


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
            "projects_root": str(default_projects_root()),
            "projects_root_source": "platform-default",
            "portable_mode": False,
            "max_workers": 2,
            "lease_seconds": 90,
        },
        "worker": _default_worker_config(),
        "orchestration": _default_orchestration_config(),
        "agent_runners": {
            "opencode": _default_opencode_config(),
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
            "pi-rpc": {
                "enabled": False,
                "executable": "",
                "entrypoint": "",
                "model": "",
                "experiment_only": True,
                "reasoning_visibility": "activity",
            },
            "pi-worker": {
                "enabled": True,
                "executable": "",
                "entrypoint": "",
                "model": "",
                "auth_path": "",
                "thinking": "low",
                "max_turns": 6,
                "max_tool_calls": 12,
                "max_repair_attempts": 1,
                "allowed_states": [
                    "asset-creation-agent-task",
                    "canon-review-agent-task",
                    "candidate-review",
                ],
                "experiment_only": False,
                "reasoning_visibility": "activity",
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
        "server": {"host": "127.0.0.1", "port": 8791},
        "updates": {
            "channel": "stable",
            "last_checked_at": "",
        },
    }


def _default_orchestration_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "mode": "fixed",
        "strategy_preset": "balanced",
        "constitution_version": "1",
        "production_chapter_horizon": False,
        "chapter_horizon_size": 3,
        "bundle_execution": False,
        "campaign_runtime": False,
        "campaign_checkpoint_interval_steps": 5,
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
    payload = _without_machine_local_engine_path(_migrate_config(payload))
    payload.pop("core", None)
    merged = _deep_merge(base, payload)
    merged["schema"] = CONFIG_SCHEMA
    return merged


def save_config(data: dict[str, Any], path: Path | None = None) -> Path:
    target = (path or default_config_path()).resolve()
    migrated = _without_machine_local_engine_path(_migrate_config(dict(data)))
    payload = _deep_merge(default_config(), migrated)
    payload.pop("core", None)
    payload = _without_machine_local_engine_path(payload)
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
    source_schema = str(migrated.get("schema") or "")
    legacy_runtimes = migrated.pop("runtimes", None)
    if isinstance(legacy_runtimes, dict) and not isinstance(migrated.get("agent_runners"), dict):
        migrated["agent_runners"] = legacy_runtimes
    runners = migrated.get("agent_runners")
    if isinstance(runners, dict) and isinstance(runners.get("opencode"), dict):
        opencode = dict(runners["opencode"])
        unified_model = str(opencode.get("model") or "").strip()
        if unified_model and not isinstance(opencode.get("models"), dict):
            opencode["models"] = {
                "worker": unified_model,
                "advisor": unified_model,
                "steward": unified_model,
            }
            runners = dict(runners)
            runners["opencode"] = opencode
            migrated["agent_runners"] = runners
    if source_schema != CONFIG_SCHEMA and isinstance(migrated.get("agent_runners"), dict):
        runners = dict(migrated["agent_runners"])
        pi_worker = runners.get("pi-worker")
        if isinstance(pi_worker, dict) and pi_worker.get("experiment_only") is True:
            # v0.5 shipped only an opt-in research adapter. v0.6 owns a bundled
            # installation, so discard prototype machine paths while retaining
            # the user's model, credential location, and execution budgets.
            pi_worker = dict(pi_worker)
            pi_worker.update(
                {
                    "enabled": True,
                    "executable": "",
                    "entrypoint": "",
                    "experiment_only": False,
                }
            )
            pi_worker.pop("experiment_authorized", None)
            runners["pi-worker"] = pi_worker
            migrated["agent_runners"] = runners
    if source_schema != CONFIG_SCHEMA:
        migrated = _migrate_pi_prompt_rollout(migrated)
    return migrated


def _migrate_pi_prompt_rollout(payload: dict[str, Any]) -> dict[str, Any]:
    """Use the Worker-native Prompt Program for every bounded Pi task."""

    migrated = dict(payload)
    worker = migrated.get("worker")
    if not isinstance(worker, dict):
        return migrated
    worker = dict(worker)
    prompt = worker.get("prompt_program")
    if not isinstance(prompt, dict):
        return migrated
    prompt = dict(prompt)
    enforcement = prompt.get("enforcement")
    if not isinstance(enforcement, dict):
        return migrated
    enforcement = dict(enforcement)
    runtimes = {str(item) for item in enforcement.get("runtimes") or []}
    if runtimes and runtimes != {"pi-worker"}:
        return migrated
    prompt.update(
        {
            "mode": "enforced",
            "fallback": "error",
            "enforcement": {
                "enabled": True,
                "runtimes": ["pi-worker"],
            },
        }
    )
    worker["prompt_program"] = prompt
    migrated["worker"] = worker
    return migrated


def _without_machine_local_engine_path(payload: dict[str, Any]) -> dict[str, Any]:
    """Discard an obsolete executable path that cannot survive reinstall or relocation."""

    normalized = dict(payload)
    engine = normalized.get("engine")
    if isinstance(engine, dict):
        normalized["engine"] = {key: value for key, value in engine.items() if key != "python"}
    return normalized


def _assert_no_model_credentials(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    forbidden = ("api_key", "apikey", "model_provider", "deepseek_api", "openai_api")
    found = [token for token in forbidden if token in serialized]
    if found:
        raise ValueError(
            "Studio configuration must not contain model-provider credentials or API configuration: "
            + ", ".join(found)
        )
