"""No-progress accounting and bounded campaign recovery."""

from __future__ import annotations

import time
from typing import Any, Callable

from .support import _now
from ..orchestration import recovery_step


NO_PROGRESS_LIMIT = 3


def register_no_progress(
    runs: Any,
    *,
    run_id: str,
    task_id: str,
    route: str,
    message: str,
    campaign_runtime_enabled: bool,
    pause: Callable[[str, str, str], None],
) -> bool:
    run = runs.read_autopilot_run(run_id)
    stalled_cycles = int(run.get("stalled_cycles") or 0) + 1
    changes: dict[str, Any] = {
        "stalled_cycles": stalled_cycles,
        "last_error": message,
        "current_task_id": task_id,
    }
    if stalled_cycles == 2:
        changes["last_recovery_at"] = _now()
        if campaign_runtime_enabled:
            changes["current_task_id"] = ""
    runs.update_autopilot_run(run_id, **changes)
    runs.append_autopilot_event(
        run_id,
        "progress.stalled",
        {
            "route": route,
            "task_id": task_id,
            "stalled_cycles": stalled_cycles,
            "message": message,
        },
    )
    if stalled_cycles == 2:
        runs.append_autopilot_event(
            run_id,
            "task.recovery_requested",
            {
                "route": route,
                "task_id": task_id,
                "strategy": "re-open-current-formal-task",
            },
        )
    if campaign_runtime_enabled and stalled_cycles >= 2:
        _record_campaign_recovery(runs, run_id, task_id, stalled_cycles)
    if stalled_cycles >= NO_PROGRESS_LIMIT:
        pause(
            run_id,
            "no-progress",
            f"{message} 已连续 {stalled_cycles} 次未推进；系统已暂停，避免空转消耗。",
        )
        return True
    time.sleep(0.15 * stalled_cycles)
    return False


def _record_campaign_recovery(
    runs: Any,
    run_id: str,
    task_id: str,
    stalled_cycles: int,
) -> None:
    attempt = 1 if stalled_cycles < NO_PROGRESS_LIMIT else 2
    decision = recovery_step("no_progress", attempt)
    runs.append_autopilot_event(
        run_id,
        "campaign.recovery.selected",
        {
            "task_id": task_id,
            "failure_code": "no_progress",
            "attempt": attempt,
            "step": decision.step.value,
            "reasons": list(decision.reasons),
        },
    )


__all__ = ["register_no_progress"]
