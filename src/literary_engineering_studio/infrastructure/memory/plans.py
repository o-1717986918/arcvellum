"""Small in-memory index for creative plan application tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .primitives import iso_now
from .state import MemoryPersistenceState


class InMemoryPlanRepository:
    def __init__(self, state: MemoryPersistenceState, clock):
        self._state = state
        self._clock = clock

    def reserve_creative_plan_revision(self, record: dict[str, Any]) -> dict[str, Any]:
        normalized = _normalized_revision(record, self._clock)
        plan_id, revision = normalized["plan_id"], normalized["revision"]
        key = (plan_id, revision)
        with self._state.lock:
            existing = self._state.plan_revisions.get(key)
            if existing is not None:
                if existing["digest"] != normalized["digest"]:
                    raise ValueError("creative plan revision conflicts with an existing digest")
                return deepcopy(existing)
            _reserve_plan_identity(self._state.plans, normalized)
            self._state.plan_revisions[key] = _revision_record(normalized)
            self._append_event(plan_id, revision, "revision.reserved", {"digest": normalized["digest"]})
            return deepcopy(self._state.plan_revisions[key])

    def finalize_creative_plan_revision(self, plan_id: str, revision: int, *, digest: str) -> dict[str, Any]:
        with self._state.lock:
            record = self._required_revision(plan_id, revision)
            if record["digest"] != digest:
                raise ValueError("creative plan revision finalize digest mismatch")
            if record["artifact_state"] != "ready":
                record["artifact_state"] = "ready"
                self._append_event(plan_id, revision, "revision.ready", {"digest": digest})
            return deepcopy(record)

    def read_creative_plan(self, plan_id: str) -> dict[str, Any]:
        with self._state.lock:
            try:
                return deepcopy(self._state.plans[plan_id])
            except KeyError as exc:
                raise FileNotFoundError(f"creative plan not found: {plan_id}") from exc

    def list_creative_plans(self, project_root: str, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._state.lock:
            plans = [item for item in self._state.plans.values() if item["project_root"] == project_root]
            plans.sort(key=lambda item: (item["updated_at"], item["plan_id"]), reverse=True)
            return deepcopy(plans[:max(1, min(1000, int(limit)))])

    def read_creative_plan_revision(self, plan_id: str, revision: int) -> dict[str, Any]:
        with self._state.lock:
            return deepcopy(self._required_revision(plan_id, revision))

    def authorize_creative_plan_revision(
        self,
        plan_id: str,
        revision: int,
        *,
        authorized_by: str,
        reason: str,
        verified_revision_digest: str,
    ) -> dict[str, Any]:
        with self._state.lock:
            record = self._required_revision(plan_id, revision)
            if record["digest"] != verified_revision_digest:
                raise ValueError("creative plan authorization digest mismatch")
            record["review"] = {
                **deepcopy(record.get("review") or {}),
                "lifecycle": "assisted_authorized",
                "authorization": {
                    "authorized_by": authorized_by,
                    "reason": reason,
                    "revision_digest": verified_revision_digest,
                    "authorized_at": iso_now(self._clock),
                },
            }
            self._append_event(plan_id, revision, "activation.authorized", {"authorized_by": authorized_by})
            return deepcopy(record)

    def creative_plan_events(
        self,
        plan_id: str,
        *,
        after: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with self._state.lock:
            events = self._state.plan_events.get(plan_id, [])
            return deepcopy([item for item in events if item["sequence"] > max(0, int(after))][:max(1, int(limit))])

    def _required_revision(self, plan_id: str, revision: int) -> dict[str, Any]:
        try:
            return self._state.plan_revisions[(plan_id, int(revision))]
        except KeyError as exc:
            raise FileNotFoundError(f"creative plan revision not found: {plan_id}@{revision}") from exc

    def _append_event(self, plan_id: str, revision: int, event: str, data: dict[str, Any]) -> None:
        events = self._state.plan_events.setdefault(plan_id, [])
        events.append(
            {
                "sequence": len(events) + 1,
                "plan_id": plan_id,
                "revision": revision,
                "event": event,
                "at": iso_now(self._clock),
                "data": deepcopy(data),
            }
        )


__all__ = ["InMemoryPlanRepository"]


def _normalized_revision(record: dict[str, Any], clock) -> dict[str, Any]:
    plan_id = str(record.get("plan_id") or "").strip()
    revision = int(record.get("revision") or 0)
    digest = str(record.get("digest") or "").strip()
    if not plan_id or revision < 1 or len(digest) != 64:
        raise ValueError("creative plan revision identity is invalid")
    return {
        **deepcopy(record),
        "plan_id": plan_id,
        "revision": revision,
        "digest": digest,
        "project_root": str(record.get("project_root") or ""),
        "scope_kind": str(record.get("scope_kind") or ""),
        "scope_key": str(record.get("scope_key") or ""),
        "base_project_fingerprint": str(record.get("base_project_fingerprint") or ""),
        "created_at": str(record.get("created_at") or iso_now(clock)),
    }


def _reserve_plan_identity(plans: dict[str, dict[str, Any]], record: dict[str, Any]) -> None:
    identity = {
        "plan_id": record["plan_id"],
        "project_root": record["project_root"],
        "scope_kind": record["scope_kind"],
        "scope_key": record["scope_key"],
        "status": "shadow",
        "active_revision": 0,
        "base_project_fingerprint": record["base_project_fingerprint"],
        "policy": deepcopy(record.get("policy") or {}),
        "created_at": record["created_at"],
        "updated_at": record["created_at"],
    }
    current = plans.get(record["plan_id"])
    if current is None:
        plans[record["plan_id"]] = identity
        return
    keys = ("project_root", "scope_kind", "scope_key", "base_project_fingerprint")
    if any(current[name] != identity[name] for name in keys):
        raise ValueError("creative plan identity conflicts with the existing index")


def _revision_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "plan_id": record["plan_id"],
        "revision": record["revision"],
        **{name: deepcopy(record.get(name) or {}) for name in (
            "candidate", "normalized", "compiled", "lint", "simulation", "review",
        )},
        "digest": record["digest"],
        "artifact_state": "reserved",
        "created_at": record["created_at"],
    }
