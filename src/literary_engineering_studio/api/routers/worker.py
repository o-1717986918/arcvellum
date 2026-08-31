"""Agent Worker HTTP orchestration over the existing job, lock, and sandbox contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import time
import uuid
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from ..streaming import numeric_resume_cursor, sse_headers, stream_terminal

from ...observability.event_policy import EventDurability, classify_runtime_event
from ...observability.creative_live.contracts import project_channel
from ...observability.context_ledger_tracking import persist_prepared_context
from ...observability.mutation_receipt_tracking import (
    persist_mutation_receipt_event,
)
from ..common import project_root as resolve_project_root
from ..models import WorkerRequest, WorkerRetryRequest, WritebackDecisionRequest


@dataclass(frozen=True)
class WorkerRouterDependencies:
    config: dict[str, Any]
    jobs: Any
    lifecycle: Any
    worker_factory: Callable[..., Any]
    project_lock_key: Callable[[str, str], str]
    track_agent_session_event: Callable[..., None]
    context_ledgers: Any
    mutation_receipts: Any
    invalidate_project: Callable[[Path, str], Any]
    coalesce_live_events: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


def _request_data(payload: WorkerRequest) -> dict[str, Any]:
    return payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()


def _worker_event_sink(
    deps: WorkerRouterDependencies, payload: WorkerRequest, job: dict[str, Any]
) -> Callable[[str, dict[str, Any]], None]:
    project = str(resolve_project_root(payload.project_root))
    job_id = str(job["job_id"])

    def emit(event: str, data: dict[str, Any]) -> None:
        enriched = {
            **data,
            "runtime_event_id": str(data.get("runtime_event_id") or uuid.uuid4().hex),
            "controller_id": job_id,
            "run_id": str(data.get("run_id") or job_id),
            "task_id": str(data.get("task_id") or payload.task_id),
            "route": str(data.get("route") or payload.route),
            "runtime": str(data.get("runtime") or payload.runtime),
            "attempt_id": str(data.get("attempt_id") or data.get("run_id") or job_id),
            "source_event": event,
        }
        deps.track_agent_session_event(
            project_root=project, role="worker", runtime=payload.runtime,
            controller_id=job_id, task_id=payload.task_id, route=payload.route,
            event=event, data=enriched,
        )
        channel = f"worker:{job_id}"
        if classify_runtime_event(event) is EventDurability.EPHEMERAL:
            deps.lifecycle.live_events.publish(channel, event, enriched)
        else:
            deps.jobs.append_event(job_id, event, enriched)
            deps.lifecycle.live_events.notify()
        deps.lifecycle.live_events.publish(project_channel(project), event, enriched)
        if event == "sandbox.prepared":
            deps.jobs.register_resources(
                job_id, formal_project=str(data.get("project_root") or payload.project_root),
                task_sandbox=str(data.get("run_root") or ""),
                agent_session=f"{data.get('runner_id') or payload.runtime}:{data.get('run_id') or job_id}",
                run_workspace=str(data.get("workspace") or ""),
            )

    return emit


def launch_worker(deps: WorkerRouterDependencies, payload: WorkerRequest, *, resume_run_root: Path | None = None):
    request_data = _request_data(payload)
    job = deps.jobs.create(request_data, idempotency_key=payload.idempotency_key)

    if resume_run_root is not None:
        run = json.loads((resume_run_root / "run.json").read_text(encoding="utf-8"))
        deps.jobs.register_resources(
            str(job["job_id"]),
            formal_project=str(run.get("project_root") or payload.project_root),
            task_sandbox=str(resume_run_root),
            agent_session=f"recovery:{run.get('run_id') or job['job_id']}",
            run_workspace=str(run.get("workspace") or ""),
            state="recovering",
        )

    def execute(cancel_event) -> dict[str, Any]:
        emit = _worker_event_sink(deps, payload, job)

        worker = deps.worker_factory(
            deps.config,
            event_sink=emit,
            cancel_event=cancel_event,
            runtime_pool=deps.lifecycle.opencode_pool,
        )
        if resume_run_root is not None:
            try:
                result = worker.resume_from_run(resume_run_root)
                emit("run.resumed", {"run_root": str(resume_run_root), "status": result.status})
                return result.as_dict()
            except (FileNotFoundError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
                emit("run.resume_fallback", {"run_root": str(resume_run_root), "error": str(exc)})
        result = worker.run_once(
            resolve_project_root(payload.project_root),
            route=payload.route,
            runtime_id=payload.runtime,
            task_id=payload.task_id,
            scene=payload.scene,
        )
        return result.as_dict()

    if job["status"] in {"queued", "interrupted"}:
        deps.lifecycle.supervisor.submit(
            str(job["job_id"]),
            execute,
            lock_key=deps.project_lock_key(payload.project_root, payload.route),
        )
    return {"ok": True, **job}


def build_worker_router(deps: WorkerRouterDependencies) -> APIRouter:
    """Build Worker endpoints without reimplementing Engine task gates in HTTP handlers."""

    router = APIRouter()

    @router.post("/worker/prepare")
    def worker_prepare(payload: WorkerRequest):
        try:
            task, sandbox, terminal = deps.worker_factory(deps.config, runtime_pool=deps.lifecycle.opencode_pool).prepare(
                resolve_project_root(payload.project_root),
                route=payload.route,
                runtime_id=payload.runtime,
                task_id=payload.task_id,
                scene=payload.scene,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if terminal:
            return {"ok": True, **terminal.as_dict()}
        return _prepared_worker_response(deps, payload, task, sandbox)

    @router.post("/worker/run")
    def worker_run(payload: WorkerRequest):
        return launch_worker(deps, payload)

    @router.get("/worker/jobs/{job_id}")
    def worker_job(job_id: str):
        try:
            return {"ok": True, **deps.jobs.read(job_id)}
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/worker/jobs/{job_id}/events")
    def worker_job_events(job_id: str, after: int = 0, limit: int = 200):
        try:
            deps.jobs.read(job_id)
            return {"ok": True, "items": deps.jobs.events_since(job_id, after, limit=limit)}
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/worker/jobs/{job_id}/stop")
    def worker_job_stop(job_id: str):
        try:
            return {"ok": True, **deps.lifecycle.supervisor.stop(job_id)}
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/worker/jobs/{job_id}/writeback")
    def worker_job_writeback(job_id: str, payload: WritebackDecisionRequest):
        try:
            job = deps.jobs.read(job_id)
            if job["status"] != "waiting_writeback":
                raise ValueError("job is not waiting for writeback approval")
            run_root = Path(str(job.get("result", {}).get("run_root") or ""))
            request = job.get("request") if isinstance(job.get("request"), dict) else {}
            project_root = str(request.get("project_root") or "")
            lock_key = deps.project_lock_key(project_root, str(request.get("route") or "auto"))
            owner = deps.lifecycle.supervisor.worker_id
            coordinator_owner = f"writeback:{job_id}"
            if not deps.lifecycle.execution_coordinator.acquire(project_root, coordinator_owner):
                raise RuntimeError("another active task owns this project")
            if not deps.jobs.acquire_lock(lock_key, job_id, owner, lease_seconds=180):
                deps.lifecycle.execution_coordinator.release(project_root, coordinator_owner)
                raise RuntimeError("another active task owns this project route")
            try:
                def emit(event: str, data: dict[str, Any]) -> None:
                    _persist_writeback_event(deps, project_root, job_id, event, data)

                worker = deps.worker_factory(deps.config, event_sink=emit, runtime_pool=deps.lifecycle.opencode_pool)
                decision = payload.decision.strip().lower()
                if decision == "approve":
                    result = worker.approve_writeback(run_root, approved_by="studio-user")
                elif decision == "reject":
                    result = worker.reject_writeback(run_root, rejected_by="studio-user", reason=payload.reason)
                else:
                    raise ValueError("writeback decision must be approve or reject")
                return {
                    "ok": True,
                    **deps.jobs.update(
                        job_id,
                        status=result.status,
                        result=result.as_dict(),
                        finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    ),
                }
            finally:
                deps.jobs.release_lock(lock_key, job_id)
                deps.lifecycle.execution_coordinator.release(project_root, coordinator_owner)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/worker/jobs/{job_id}/retry")
    def worker_job_retry(job_id: str, payload: WorkerRetryRequest):
        try:
            previous = deps.jobs.read(job_id)
            if previous["status"] in {"queued", "running", "stopping"}:
                raise ValueError("active jobs cannot be retried")
            request_data = dict(previous.get("request") or {})
            if payload.runtime.strip():
                if payload.runtime not in {"pi-worker", "opencode", "host-agent", "claude-code", "codex-cli"}:
                    raise ValueError("unknown Agent Runner")
                request_data["runtime"] = payload.runtime
            request_data["idempotency_key"] = ""
            retry = WorkerRequest(**request_data)
            resume_root = None
            if payload.resume and previous["status"] in {"interrupted", "runtime_failed", "failed"}:
                resources = deps.jobs.read_resources(job_id)
                candidate = Path(str((resources or {}).get("task_sandbox") or ""))
                if candidate.is_dir() and (candidate / "run.json").is_file():
                    resume_root = candidate
            return launch_worker(deps, retry, resume_run_root=resume_root)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (RuntimeError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/worker/jobs/{job_id}/stream")
    def worker_job_stream(job_id: str, request: Request, interval_seconds: float = 0.5, after: int = 0):
        interval = max(0.1, min(10.0, float(interval_seconds or 0.5)))
        resume_after = numeric_resume_cursor(
            after,
            request.headers.get("Last-Event-ID") or "",
        )

        return _worker_stream_response(
            deps, job_id, resume_after=resume_after, interval=interval
        )

    return router


def _worker_stream_response(
    deps: WorkerRouterDependencies,
    job_id: str,
    *,
    resume_after: int,
    interval: float,
) -> StreamingResponse:
    def stream():
        cursor = max(0, resume_after)
        live_cursor = 0
        previous_revision = -1
        last_heartbeat = time.monotonic()
        while True:
            payload = deps.jobs.read(job_id)
            for item in deps.jobs.events_since(job_id, cursor, limit=200):
                cursor = int(item["sequence"])
                yield f"id: {cursor}\nevent: {item['event']}\n"
                yield "data: " + json.dumps(item, ensure_ascii=False) + "\n\n"
            revision = int(payload.get("revision") or 0)
            if revision != previous_revision:
                yield "event: worker\n"
                yield "data: " + json.dumps({"ok": True, **payload}, ensure_ascii=False) + "\n\n"
                previous_revision = revision
            live = deps.lifecycle.live_events.wait_since(
                f"worker:{job_id}", live_cursor, timeout=0.1
            )
            for item in deps.coalesce_live_events(live):
                live_cursor = max(live_cursor, int(item.get("sequence") or 0))
                yield f"event: {item['event']}\n"
                yield "data: " + json.dumps(item, ensure_ascii=False) + "\n\n"
            if payload.get("status") not in {"queued", "running", "stopping"}:
                yield stream_terminal(
                    f"worker:{job_id}",
                    str(payload.get("status") or "unknown"),
                    cursor,
                )
                break
            if time.monotonic() - last_heartbeat >= 10:
                yield ": worker heartbeat\n\n"
                last_heartbeat = time.monotonic()
            deps.lifecycle.live_events.wait_since(
                f"worker:{job_id}", live_cursor, timeout=interval
            )

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers=sse_headers()
    )


def _prepared_worker_response(deps, payload, task, sandbox) -> dict[str, Any]:
    if task is None or sandbox is None:
        raise RuntimeError("worker preparation returned no task sandbox")
    persist_prepared_context(deps.context_ledgers, task, sandbox)
    return {
        "ok": True,
        "status": "prepared",
        "task_id": task.task_id,
        "route": task.route,
        "runtime": payload.runtime,
        "execution_contract": task.execution_contract.as_dict(),
        "run_root": str(sandbox.run_root),
        "workspace": str(sandbox.workspace),
        "prompt": str(sandbox.prompt_path),
    }


def _persist_writeback_event(
    deps: WorkerRouterDependencies,
    project_root: str,
    job_id: str,
    event: str,
    data: dict[str, Any],
) -> None:
    root = resolve_project_root(project_root)
    receipt = persist_mutation_receipt_event(
        deps.mutation_receipts,
        project_root=str(root),
        event=event,
        data=data,
    )
    if receipt is not None:
        deps.invalidate_project(root, "worker-writeback")
    deps.jobs.append_event(job_id, event, data)
