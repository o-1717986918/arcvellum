"""Autopilot controls and Agent execution observability routes."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..common import call_handler, project_root as resolve_project_root
from ..models import AutopilotControlRequest, AutopilotPolicyRequest, AutopilotStartRequest


@dataclass(frozen=True)
class AutomationRouterDependencies:
    jobs: Any
    autopilot: Any
    lifecycle: Any
    dashboard_snapshot: Callable[[Path], dict[str, Any]]
    build_agent_observability: Callable[..., dict[str, Any]]
    sse: Callable[[str, dict[str, Any], int | str | None], str]


def _observability_payload(deps: AutomationRouterDependencies, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    status = deps.autopilot.status(root)
    run = status.get("run") if isinstance(status.get("run"), dict) else {}
    events = deps.jobs.autopilot_events_since(str(run.get("run_id") or ""), limit=80) if run.get("run_id") else []
    payload = deps.build_agent_observability(
        str(root),
        status,
        events,
        deps.dashboard_snapshot(root),
        deps.jobs.list_agent_sessions(str(root), limit=30),
        deps.lifecycle.opencode_pool.status(),
    )
    return payload, run


def build_automation_router(deps: AutomationRouterDependencies) -> APIRouter:
    """Build control/observability endpoints around one Autopilot service instance."""

    router = APIRouter()

    @router.get("/autopilot/status")
    def autopilot_status(project_root: str):
        def read():
            payload = deps.autopilot.status(resolve_project_root(project_root))
            run = payload.get("run")
            payload["decisions"] = deps.jobs.delegated_decisions(run["run_id"])[-20:] if run else []
            return payload

        return call_handler(read)

    @router.get("/agent-observability")
    def agent_observability(project_root: str):
        return call_handler(lambda: _observability_payload(deps, resolve_project_root(project_root))[0])

    @router.get("/agent-observability/stream")
    def agent_observability_stream(project_root: str, interval_seconds: float = 1.0, max_events: int = 0):
        root = resolve_project_root(project_root)
        interval = max(0.5, min(15.0, float(interval_seconds or 1.0)))
        limit = max(0, int(max_events or 0))

        def stream():
            previous_revision = ""
            sent = 0
            while True:
                payload, run = _observability_payload(deps, root)
                revision = str(payload.get("revision") or "")
                if revision != previous_revision:
                    yield deps.sse("agent.observability", payload, None)
                    previous_revision = revision
                    sent += 1
                    if limit and sent >= limit:
                        break
                else:
                    yield ": agent heartbeat\n\n"
                if str(run.get("status") or "") in {"complete", "paused", "blocked", "cancelled", "failed"} and sent:
                    break
                time.sleep(interval)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @router.put("/autopilot/policy")
    def autopilot_policy_save(payload: AutopilotPolicyRequest):
        return call_handler(lambda: {"ok": True, **deps.autopilot.save_policy(resolve_project_root(payload.project_root), payload.policy)})

    @router.post("/autopilot/start")
    def autopilot_start(payload: AutopilotStartRequest):
        def start():
            root = resolve_project_root(payload.project_root)
            policy = deps.autopilot.policy(root).get("policy", {})
            if policy.get("mode") == "full_auto" and not payload.authorized:
                raise ValueError("全自动交付需要用户在创作总控中明确确认授权。")
            return {"ok": True, "run": deps.autopilot.start(root, runtime=payload.runtime)}

        return call_handler(start)

    @router.post("/autopilot/runs/{run_id}/pause")
    def autopilot_pause(run_id: str, payload: AutopilotControlRequest):
        return call_handler(lambda: {"ok": True, "run": deps.autopilot.pause(run_id, reason=payload.reason)})

    @router.post("/autopilot/runs/{run_id}/resume")
    def autopilot_resume(run_id: str, payload: AutopilotControlRequest | None = None):
        return call_handler(
            lambda: {
                "ok": True,
                "run": deps.autopilot.resume(run_id, authorized=bool(payload and payload.authorized)),
            }
        )

    @router.get("/autopilot/runs/{run_id}/events")
    def autopilot_events(run_id: str, after: int = 0, limit: int = 300):
        return call_handler(lambda: {"ok": True, "items": deps.jobs.autopilot_events_since(run_id, after, limit=limit)})

    @router.get("/autopilot/runs/{run_id}/stream")
    def autopilot_stream(run_id: str, after: int = 0):
        deps.jobs.read_autopilot_run(run_id)

        def stream():
            cursor = max(0, int(after))
            while True:
                items = deps.jobs.autopilot_events_since(run_id, cursor)
                for item in items:
                    cursor = max(cursor, int(item["sequence"]))
                    yield deps.sse(str(item["event"]), item, None)
                run = deps.jobs.read_autopilot_run(run_id)
                yield deps.sse("autopilot.status", {"run": run, "cursor": cursor}, None)
                if run["status"] in {"complete", "paused", "blocked", "cancelled", "failed"}:
                    break
                time.sleep(0.7)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return router
