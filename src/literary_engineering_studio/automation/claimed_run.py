"""Claimed-run setup for both available literary execution policies."""

from __future__ import annotations

from pathlib import Path
import threading
from typing import Any

from .campaign_runtime import CampaignRuntimeCoordinator
from .run_loop import ClaimedRunLoop
from .support import _now
from ..orchestration import orchestration_settings


def run_claimed(
    host: Any,
    run_id: str,
    stop: threading.Event,
    route_order: tuple[str, ...],
    dependency_probe: Any,
) -> None:
    run = host.runs.read_autopilot_run(run_id)
    project = Path(run["project_root"])
    from .policy import DelegationPolicy
    policy = DelegationPolicy(run["policy"])
    settings = orchestration_settings(host.config)
    campaign = (
        CampaignRuntimeCoordinator(
            host.runs, project, run_id, max_autonomous_steps=None,
            checkpoint_interval_steps=settings.campaign_checkpoint_interval_steps,
        )
        if settings.enabled and settings.campaign_runtime else None
    )
    steward = host._build_steward(run_id) if policy.literary_kernel != "lean-v2" else None
    try:
        ClaimedRunLoop(
            host, run_id=run_id, project=project, policy=policy,
            steward=steward, stop=stop, route_order=route_order,
            dependency_probe=dependency_probe, campaign=campaign,
        ).run()
    except Exception as exc:
        host.runs.update_autopilot_run(
            run_id, status="blocked", last_error=str(exc),
            stop_reason="controller-error", finished_at=_now(),
        )
        host.runs.append_autopilot_event(run_id, "autopilot.blocked", {"message": str(exc)})
