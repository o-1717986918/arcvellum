"""Durable controller-lease renewal with retryable event evidence."""

from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Any, Callable, Literal, TypedDict

from ..persistence.job_store import JobStore


class LeaseFailureEvidence(TypedDict):
    stage: Literal["renew", "reclaim"]
    error_type: str
    message: str


@dataclass(frozen=True)
class LeaseRenewalResult:
    """One controller heartbeat outcome with retained failure evidence."""

    state: Literal["renewed", "reclaimed", "lost"]
    failures: tuple[LeaseFailureEvidence, ...] = ()


def renew_or_reclaim_lease(
    store: JobStore,
    run_id: str,
    lease_owner: str,
    *,
    lease_seconds: int,
) -> LeaseRenewalResult:
    failures: list[LeaseFailureEvidence] = []
    try:
        if store.renew_autopilot_lease(
            run_id, lease_owner, lease_seconds=lease_seconds
        ):
            return LeaseRenewalResult("renewed")
    except Exception as exc:
        failures.append(_lease_failure("renew", exc))
    try:
        if store.acquire_autopilot_lease(
            run_id, lease_owner, lease_seconds=lease_seconds
        ):
            return LeaseRenewalResult("reclaimed", tuple(failures))
    except Exception as exc:
        failures.append(_lease_failure("reclaim", exc))
    return LeaseRenewalResult("lost", tuple(failures))


def run_lease_heartbeat(
    store: JobStore,
    *,
    run_id: str,
    lease_owner: str,
    controller_id: str,
    stop: threading.Event,
    renew_stop: threading.Event,
    renew: Callable[[str, str], LeaseRenewalResult],
) -> None:
    pending_events: list[tuple[str, dict[str, Any]]] = []
    while True:
        pending_events = _flush_events(store, run_id, pending_events)
        if renew_stop.wait(20):
            break
        renewal = renew(run_id, lease_owner)
        if renewal.state == "renewed":
            continue
        event = (
            "autopilot.controller_lease_reclaimed"
            if renewal.state == "reclaimed"
            else "autopilot.controller_lease_lost"
        )
        data: dict[str, Any] = {
            "controller_id": controller_id,
            "failures": list(renewal.failures),
        }
        if renewal.state == "lost":
            data["reason"] = "reclaim-refused"
        pending_events.append((event, data))
        pending_events = _flush_events(store, run_id, pending_events)
        if renewal.state == "reclaimed":
            continue
        setattr(stop, "_arcvellum_lease_lost", True)
        if pending_events:
            setattr(stop, "_arcvellum_lease_event_backlog", tuple(pending_events))
        stop.set()
        return


def _flush_events(
    store: JobStore,
    run_id: str,
    pending: list[tuple[str, dict[str, Any]]],
) -> list[tuple[str, dict[str, Any]]]:
    for index, (event, data) in enumerate(pending):
        try:
            store.append_autopilot_event(run_id, event, data)
        except Exception:
            return pending[index:]
    return []


def _lease_failure(
    stage: Literal["renew", "reclaim"],
    exc: Exception,
) -> LeaseFailureEvidence:
    return {
        "stage": stage,
        "error_type": type(exc).__name__,
        "message": str(exc),
    }
