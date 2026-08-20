"""In-memory Autopilot run, event, lease, and decision repository."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any

from ...persistence.primitives import _redact
from .primitives import iso_now
from .state import MemoryPersistenceState


class InMemoryAutopilotRepository:
    def __init__(self, state: MemoryPersistenceState, clock, ids):
        self._state = state
        self._clock = clock
        self._ids = ids

    def create_autopilot_run(
        self,
        project_root: str,
        *,
        mode: str,
        runtime: str,
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        with self._state.lock:
            run_id = self._ids.new_id("autopilot")
            now = iso_now(self._clock)
            record = {
                "run_id": run_id,
                "project_root": project_root,
                "mode": mode,
                "runtime": runtime,
                "status": "running",
                "policy": deepcopy(policy),
                "created_at": now,
                "updated_at": now,
                "started_at": now,
                "finished_at": "",
                "current_route": "",
                "current_task_id": "",
                "tasks_completed": 0,
                "failures": 0,
                "consecutive_revisions": 0,
                "estimated_cost": 0.0,
                "last_error": "",
                "stop_reason": "",
                "route_index": 0,
                "progress_fingerprint": "",
                "stalled_cycles": 0,
                "last_progress_at": "",
                "last_recovery_at": "",
            }
            self._state.autopilot_runs[run_id] = record
            self._append_event(run_id, "autopilot.started", {"mode": mode, "runtime": runtime})
            return deepcopy(record)

    def read_autopilot_run(self, run_id: str) -> dict[str, Any]:
        with self._state.lock:
            return deepcopy(self._required(run_id))

    def latest_autopilot_run(self, project_root: str) -> dict[str, Any] | None:
        with self._state.lock:
            matches = [
                item for item in self._state.autopilot_runs.values()
                if item["project_root"] == project_root
            ]
            if not matches:
                return None
            return deepcopy(max(matches, key=lambda item: (item["created_at"], item["run_id"])))

    def update_autopilot_run(self, run_id: str, **changes: Any) -> dict[str, Any]:
        allowed = {
            "status", "current_route", "current_task_id", "tasks_completed", "failures",
            "consecutive_revisions", "estimated_cost", "last_error", "stop_reason", "finished_at",
            "route_index", "progress_fingerprint", "stalled_cycles", "last_progress_at",
            "last_recovery_at",
        }
        with self._state.lock:
            record = self._required(run_id)
            record.update(deepcopy({key: value for key, value in changes.items() if key in allowed}))
            record["updated_at"] = iso_now(self._clock)
            return deepcopy(record)

    def update_autopilot_run_policy(self, run_id: str, policy: dict[str, Any]) -> dict[str, Any]:
        with self._state.lock:
            record = self._required(run_id)
            record["policy"] = deepcopy(policy)
            record["mode"] = str(policy.get("mode") or "collaborative")
            record["updated_at"] = iso_now(self._clock)
            return deepcopy(record)

    def advance_autopilot_run(self, run_id: str, **changes: Any) -> dict[str, Any]:
        with self._state.lock:
            record = self._required(run_id)
            record["tasks_completed"] += 1
            allowed = {
                "failures", "consecutive_revisions", "estimated_cost", "last_error",
                "current_route", "current_task_id", "route_index", "progress_fingerprint",
                "stalled_cycles", "last_progress_at", "last_recovery_at",
            }
            record.update(deepcopy({key: value for key, value in changes.items() if key in allowed}))
            record["updated_at"] = iso_now(self._clock)
            return deepcopy(record)

    def acquire_autopilot_lease(self, run_id: str, owner_id: str, *, lease_seconds: int = 90) -> bool:
        owner = str(owner_id or "").strip()
        if not owner:
            raise ValueError("autopilot lease owner must not be empty")
        with self._state.lock:
            self._required(run_id)
            self._discard_expired_leases()
            current = self._state.autopilot_leases.get(run_id)
            if current and current["owner_id"] != owner:
                return False
            now = self._clock.now()
            self._state.autopilot_leases[run_id] = {
                "owner_id": owner,
                "lease_expires_at": (now + timedelta(seconds=max(30, lease_seconds))).isoformat(),
                "updated_at": iso_now(self._clock),
            }
            return True

    def renew_autopilot_lease(self, run_id: str, owner_id: str, *, lease_seconds: int = 90) -> bool:
        with self._state.lock:
            self._discard_expired_leases()
            current = self._state.autopilot_leases.get(run_id)
            if not current or current["owner_id"] != str(owner_id or ""):
                return False
            current["lease_expires_at"] = (
                self._clock.now() + timedelta(seconds=max(30, lease_seconds))
            ).isoformat()
            current["updated_at"] = iso_now(self._clock)
            return True

    def release_autopilot_lease(self, run_id: str, owner_id: str) -> None:
        with self._state.lock:
            current = self._state.autopilot_leases.get(run_id)
            if current and current["owner_id"] == str(owner_id or ""):
                del self._state.autopilot_leases[run_id]

    def append_autopilot_event(self, run_id: str, event: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._state.lock:
            self._required(run_id)
            return deepcopy(self._append_event(run_id, event, data))

    def autopilot_events_since(
        self,
        run_id: str,
        after: int = 0,
        *,
        limit: int = 300,
    ) -> list[dict[str, Any]]:
        with self._state.lock:
            self._required(run_id)
            events = self._state.autopilot_events.get(run_id, [])
            return deepcopy([item for item in events if item["sequence"] > max(0, int(after))][:max(1, int(limit))])

    def latest_autopilot_event(self, run_id: str, event: str) -> dict[str, Any] | None:
        with self._state.lock:
            self._required(run_id)
            matches = [item for item in self._state.autopilot_events.get(run_id, []) if item["event"] == event]
            return deepcopy(matches[-1]) if matches else None

    def record_delegated_decision(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._state.lock:
            self._required(run_id)
            record = {
                **deepcopy(payload),
                "decision_id": self._ids.new_id("decision"),
                "run_id": run_id,
                "created_at": iso_now(self._clock),
                "revoked_at": "",
            }
            self._state.delegated_decisions.setdefault(run_id, []).append(record)
            self._append_event(
                run_id,
                "decision.delegated",
                {
                    "decision_id": record["decision_id"],
                    "decision_type": record.get("decision_type"),
                    "selected_option": record.get("selected_option"),
                },
            )
            return deepcopy(record)

    def delegated_decisions(self, run_id: str) -> list[dict[str, Any]]:
        with self._state.lock:
            self._required(run_id)
            return deepcopy(self._state.delegated_decisions.get(run_id, []))

    def recover_autopilot_runs(self) -> int:
        recovered = 0
        with self._state.lock:
            for run_id, record in self._state.autopilot_runs.items():
                if record["status"] not in {"running", "stopping"}:
                    continue
                record.update(
                    status="paused",
                    stop_reason="application-restart",
                    updated_at=iso_now(self._clock),
                )
                self._append_event(
                    run_id,
                    "autopilot.recovered",
                    {"status": "paused", "reason": "application-restart"},
                )
                recovered += 1
        return recovered

    def _required(self, run_id: str) -> dict[str, Any]:
        try:
            return self._state.autopilot_runs[run_id]
        except KeyError as exc:
            raise FileNotFoundError(f"Autopilot run not found: {run_id}") from exc

    def _append_event(self, run_id: str, event: str, data: dict[str, Any]) -> dict[str, Any]:
        if not event or any(char.isspace() for char in event):
            raise ValueError(f"invalid autopilot event: {event}")
        sequence = 1 + sum(len(items) for items in self._state.autopilot_events.values())
        record = {
            "sequence": sequence,
            "run_id": run_id,
            "event": event,
            "at": iso_now(self._clock),
            "data": _redact(deepcopy(data)),
        }
        self._state.autopilot_events.setdefault(run_id, []).append(record)
        return record

    def _discard_expired_leases(self) -> None:
        now = iso_now(self._clock)
        for key in [key for key, value in self._state.autopilot_leases.items() if value["lease_expires_at"] < now]:
            del self._state.autopilot_leases[key]


__all__ = ["InMemoryAutopilotRepository"]
