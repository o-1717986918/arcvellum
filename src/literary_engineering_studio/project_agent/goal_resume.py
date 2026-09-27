"""Persist a managed goal's checkpoint before resuming its existing run."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .action_receipts import goal_result


def current_goal_run(root: Path, autopilot: Any) -> Mapping[str, Any]:
    status = autopilot.status(root)
    run = status.get("run")
    return run if isinstance(run, Mapping) else {}


def resume_managed_goal(
    root: Path,
    operation: str,
    run: Mapping[str, Any],
    autopilot: Any,
    stop_after_formal_units: int | None,
) -> Mapping[str, Any]:
    if stop_after_formal_units is not None:
        policy = run.get("policy") if isinstance(run.get("policy"), Mapping) else {}
        limits = policy.get("limits") if isinstance(policy.get("limits"), Mapping) else {}
        saved = autopilot.save_policy(root, {
            **policy,
            "limits": {**limits, "stop_after_formal_units": stop_after_formal_units},
        })
        updated_run = saved.get("run") if isinstance(saved, Mapping) else None
        updated_policy = updated_run.get("policy") if isinstance(updated_run, Mapping) else None
        updated_limits = updated_policy.get("limits") if isinstance(updated_policy, Mapping) else None
        if not isinstance(updated_limits, Mapping) or updated_limits.get("stop_after_formal_units") != stop_after_formal_units:
            raise RuntimeError("formal scene checkpoint was not persisted; goal was not resumed")
    resumed = autopilot.resume(str(run["run_id"]), authorized=True)
    return goal_result(root, operation, resumed, "accepted")


__all__ = ["current_goal_run", "resume_managed_goal"]
