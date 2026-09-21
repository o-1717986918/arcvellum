"""Safe transition from an existing creation run to a durable Agent goal."""

from __future__ import annotations

from pathlib import Path
import threading
from typing import Any

from .policy import normalize_policy
from ..runtime.runtime_selection import DEFAULT_CREATIVE_RUNTIME


def start_managed_goal(
    service: Any,
    project_root: Path,
    policy: dict[str, Any],
    *,
    runtime: str = "",
    stop_timeout: float = 5.0,
) -> dict[str, Any]:
    """Start a goal run after an incompatible controller has stopped."""

    root = project_root.expanduser().resolve()
    active = service.runs.latest_autopilot_run(str(root))
    selected_runtime = str(runtime or (active or {}).get("runtime") or DEFAULT_CREATIVE_RUNTIME)
    normalized = normalize_policy(policy)
    if active and active["status"] == "running":
        if _same_execution_policy(active, normalized):
            return active
        _stop_active_run(service, active, stop_timeout)
    service.save_policy(root, normalized)
    return service.start(root, runtime=selected_runtime)


def _same_execution_policy(run: dict[str, Any], target: dict[str, Any]) -> bool:
    active = normalize_policy(run.get("policy"))
    return all(
        active.get(key) == target.get(key)
        for key in ("mode", "literary_kernel", "release_policy", "scene_execution_mode", "limits")
    )


def _stop_active_run(service: Any, run: dict[str, Any], timeout: float) -> None:
    run_id = str(run["run_id"])
    service.pause(run_id, reason="project-agent-goal-transition")
    with service._lock:
        thread = service._threads.get(run_id)
    if thread is not None and thread is not threading.current_thread():
        thread.join(timeout=max(0.1, timeout))
    if thread is not None and thread.is_alive():
        raise RuntimeError("旧创作运行仍在收尾，请稍后重试长期目标")


__all__ = ["start_managed_goal"]
