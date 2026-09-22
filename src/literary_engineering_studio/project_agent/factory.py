"""Production command composition for the embedded Project Agent process."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..integrations.pi_worker import locate_pi_worker
from ..runtimes.base import executable_prefix
from .runtime import ProjectAgentRuntime


def build_project_agent_runtime(config: dict[str, Any], project_root: Path) -> ProjectAgentRuntime:
    runners = config.get("agent_runners") if isinstance(config.get("agent_runners"), dict) else {}
    settings = dict(runners.get("pi-worker") or {}) if isinstance(runners.get("pi-worker"), dict) else {}
    if settings.get("enabled") is False:
        raise RuntimeError("ArcVellum Pi Worker is disabled")
    installation = locate_pi_worker(settings)
    if not installation.available or installation.entrypoint is None:
        raise RuntimeError("ArcVellum Pi Worker installation is incomplete")
    model = _project_agent_model(settings)
    if not model:
        raise RuntimeError("Project Agent model is not configured")
    command = [
        *executable_prefix(installation.executable),
        str(installation.entrypoint),
        "--workspace",
        str(project_root.expanduser().resolve()),
        "--model",
        model,
        "--thinking",
        _thinking(settings),
        "--mode",
        "project-agent",
    ]
    auth_path = str(settings.get("auth_path") or "").strip()
    if auth_path:
        command.extend(["--auth-path", str(Path(auth_path).expanduser().resolve())])
    return ProjectAgentRuntime(command, cwd=project_root)


def _project_agent_model(settings: dict[str, Any]) -> str:
    models = settings.get("models") if isinstance(settings.get("models"), dict) else {}
    return str(models.get("advisor") or settings.get("model") or "").strip()


def _thinking(settings: dict[str, Any]) -> str:
    value = str(settings.get("project_agent_thinking") or "xhigh").strip().lower()
    return value if value in {"off", "minimal", "low", "medium", "high", "xhigh", "max"} else "xhigh"


__all__ = ["build_project_agent_runtime"]
