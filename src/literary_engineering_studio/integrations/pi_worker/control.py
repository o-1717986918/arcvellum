"""Credential and model controls for the embedded ArcVellum Pi Worker."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

from ...subprocess_utils import run_hidden
from .installation import locate_pi_worker


_PROVIDER_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def pi_worker_catalog(config: dict[str, Any]) -> dict[str, Any]:
    settings = _settings(config)
    installation = locate_pi_worker(settings)
    if not installation.available or installation.entrypoint is None:
        raise RuntimeError("ArcVellum Pi Worker is not installed")
    auth_path = pi_auth_path(settings)
    try:
        completed = run_hidden(
            [
                installation.executable,
                str(installation.entrypoint),
                "--catalog",
                "--auth-path",
                str(auth_path),
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Pi Worker model catalog failed: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "catalog process failed").strip()
        raise RuntimeError(f"Pi Worker model catalog failed: {detail[:500]}")
    try:
        payload = json.loads(completed.stdout.lstrip("\ufeff"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("Pi Worker returned an invalid model catalog") from exc
    if not isinstance(payload, dict) or payload.get("schema") != "arcvellum/pi-worker-catalog/v1":
        raise RuntimeError("Pi Worker returned an unsupported model catalog")
    selected = str(settings.get("model") or "")
    return {
        **payload,
        "runner": "pi-worker",
        "selected_model": selected,
        "installed": True,
        "auth_path": _public_auth_location(auth_path),
    }


def set_pi_api_credential(config: dict[str, Any], provider_id: str, credential: str) -> dict[str, Any]:
    provider = _valid_provider(provider_id)
    secret = str(credential or "").strip()
    if len(secret) < 8:
        raise ValueError("Pi Worker API credential is too short")
    path = pi_auth_path(_settings(config))
    payload = _read_auth(path)
    payload[provider] = {"type": "api_key", "key": secret}
    _write_auth(path, payload)
    return pi_worker_catalog(config)


def disconnect_pi_provider(config: dict[str, Any], provider_id: str) -> dict[str, Any]:
    provider = _valid_provider(provider_id)
    path = pi_auth_path(_settings(config))
    payload = _read_auth(path)
    payload.pop(provider, None)
    _write_auth(path, payload)
    settings = _settings(config)
    if str(settings.get("model") or "").startswith(provider + "/"):
        settings["model"] = ""
    return pi_worker_catalog(config)


def select_pi_model(config: dict[str, Any], model: str) -> dict[str, Any]:
    value = str(model or "").strip()
    catalog = pi_worker_catalog(config)
    available = {
        str(item.get("qualified_id") or "")
        for provider in catalog.get("providers", [])
        if isinstance(provider, dict) and provider.get("connected")
        for item in provider.get("models", [])
        if isinstance(item, dict)
    }
    if value not in available:
        raise ValueError("selected Pi Worker model is not connected or unavailable")
    _settings(config)["model"] = value
    return {**catalog, "selected_model": value}


def pi_auth_path(settings: dict[str, Any]) -> Path:
    explicit = str(settings.get("auth_path") or "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    root = os.environ.get("PI_CODING_AGENT_DIR", "").strip()
    return (Path(root).expanduser().resolve() if root else Path.home() / ".pi" / "agent") / "auth.json"


def _settings(config: dict[str, Any]) -> dict[str, Any]:
    runners = config.setdefault("agent_runners", {})
    value = runners.setdefault("pi-worker", {})
    if not isinstance(value, dict):
        raise ValueError("Pi Worker configuration must be an object")
    return value


def _valid_provider(value: str) -> str:
    provider = str(value or "").strip().lower()
    if not _PROVIDER_ID.fullmatch(provider):
        raise ValueError("invalid Pi Worker provider id")
    return provider


def _read_auth(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Pi Worker credential store is invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("Pi Worker credential store must contain an object")
    return payload


def _write_auth(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _public_auth_location(path: Path) -> str:
    default = (Path.home() / ".pi" / "agent" / "auth.json").resolve()
    return "用户凭证库" if path.resolve() == default else "自定义本机凭证库"
