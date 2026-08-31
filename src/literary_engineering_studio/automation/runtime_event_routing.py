"""Route Runtime events into durable runs and the project live channel."""

from __future__ import annotations

from typing import Any, Callable
import uuid

from ..observability.creative_live.contracts import project_channel
from ..observability.event_policy import EventDurability, classify_runtime_event
from ..runtime.runtime_selection import DEFAULT_CREATIVE_RUNTIME


SessionTracker = Callable[..., None]


def runtime_event_context(
    run: dict[str, Any], event: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Attach stable identities without mutating the provider-owned payload."""

    result = dict(data)
    result.setdefault("runtime_event_id", uuid.uuid4().hex)
    result.setdefault("run_id", str(run.get("run_id") or ""))
    result.setdefault("controller_id", str(run.get("run_id") or ""))
    result.setdefault("task_id", str(run.get("current_task_id") or ""))
    result.setdefault("route", str(run.get("current_route") or ""))
    result.setdefault("runtime", str(run.get("runtime") or DEFAULT_CREATIVE_RUNTIME))
    result.setdefault("attempt_id", str(result.get("run_id") or run.get("run_id") or ""))
    result.setdefault("source_event", event)
    return result


def route_worker_event(
    *, runs: Any, live_events: Any | None, track_session: SessionTracker,
    run_id: str, event: str, data: dict[str, Any],
) -> None:
    run = runs.read_autopilot_run(run_id)
    enriched = runtime_event_context(run, event, data)
    track_session(
        project_root=str(run.get("project_root") or ""), role="worker",
        runtime=str(run.get("runtime") or DEFAULT_CREATIVE_RUNTIME), controller_id=run_id,
        task_id=str(run.get("current_task_id") or ""), route=str(run.get("current_route") or ""),
        event=event, data=enriched,
    )
    if event == "task.opened":
        runs.update_autopilot_run(
            run_id, current_task_id=str(data.get("task_id") or ""),
            current_route=str(data.get("route") or run.get("current_route") or ""),
        )
    if live_events is not None:
        live_events.publish(project_channel(str(run.get("project_root") or "")), event, enriched)
    if classify_runtime_event(event) is EventDurability.EPHEMERAL:
        if live_events is not None:
            live_events.publish(f"autopilot:{run_id}", event, enriched)
        return
    runs.append_autopilot_event(run_id, f"worker.{event}", enriched)
    _record_usage_cost(runs, run_id, event, data)


def route_steward_event(
    *, runs: Any, live_events: Any | None, track_session: SessionTracker,
    runtime: str, run_id: str, event: str, data: dict[str, Any],
) -> None:
    run = runs.read_autopilot_run(run_id)
    enriched = runtime_event_context(run, event, data)
    track_session(
        project_root=str(run.get("project_root") or ""), role="steward", runtime=runtime,
        controller_id=run_id, task_id=str(run.get("current_task_id") or ""),
        route=str(run.get("current_route") or ""), event=event, data=enriched,
    )
    runs.append_autopilot_event(run_id, event, enriched)
    if live_events is not None:
        live_events.publish(project_channel(str(run.get("project_root") or "")), event, enriched)


def _record_usage_cost(runs: Any, run_id: str, event: str, data: dict[str, Any]) -> None:
    if event != "usage.updated":
        return
    cost = float(data.get("cost_usd") or 0)
    if cost <= 0:
        return
    run = runs.read_autopilot_run(run_id)
    runs.update_autopilot_run(run_id, estimated_cost=float(run["estimated_cost"]) + cost)


__all__ = ["route_steward_event", "route_worker_event", "runtime_event_context"]
