"""Delegation policy normalization and authorization limits for the Autopilot."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .support import _parse_time


POLICY_SCHEMA = "arcvellum/delegation-policy/v0.1"
MODES = {"collaborative", "supervised_auto", "full_auto"}
VALID_ROUTES = (
    "source-ingest",
    "longform-planning",
    "style-engineering",
    "character-and-world-assets",
    "scene-development",
    "review-and-audit",
    "export-and-release",
)
# Kept under the historical name inside this domain module so its pure
# normalization functions remain self-contained.
ROUTE_ORDER = VALID_ROUTES
DECISION_ALIASES = {"word_budget_direction": "budget_expansion"}
REVISION_TASK_MARKERS = (
    "revision",
    "revise",
    "asset-review-pass",
    "asset-approval-revision",
    "canon-review-pass",
    "committee-pass",
)


def is_revision_task(task_id: str) -> bool:
    normalized = str(task_id or "").strip().lower()
    return bool(normalized) and any(marker in normalized for marker in REVISION_TASK_MARKERS)


def next_revision_count(run: dict[str, Any], task_id: str) -> int:
    return int(run.get("consecutive_revisions") or 0) + 1 if is_revision_task(task_id) else 0


def default_policy(mode: str = "collaborative") -> dict[str, Any]:
    normalized = mode if mode in MODES else "collaborative"
    decisions = [] if normalized == "collaborative" else [
        "branch_selection", "style_mount", "revision_direction", "budget_expansion",
        "asset_approval", "canon_patch_approval", "state_patch_confirmation",
    ]
    delegated_routes = [
        "longform-planning", "style-engineering", "character-and-world-assets",
        "scene-development", "review-and-audit",
    ]
    if normalized == "full_auto":
        delegated_routes.append("export-and-release")
    return {
        "schema": POLICY_SCHEMA,
        "version": "0.1",
        "mode": normalized,
        "delegated_routes": delegated_routes,
        "delegated_decisions": decisions,
        "limits": {
            "max_tasks": 500,
            "max_runtime_hours": 24,
            "max_consecutive_revisions": 3,
            "max_failures_per_task": 2,
            "max_cost": 100.0,
        },
        "release_policy": "delegated" if normalized == "full_auto" else "require_user",
        "expires_at": "",
    }


def normalize_policy(value: dict[str, Any] | None) -> dict[str, Any]:
    incoming = value or {}
    mode = str(incoming.get("mode") or "collaborative")
    if mode not in MODES:
        raise ValueError("mode must be collaborative, supervised_auto, or full_auto")
    policy = default_policy(mode)
    for key in ("delegated_routes", "delegated_decisions", "release_policy", "expires_at"):
        if key in incoming:
            policy[key] = incoming[key]
    limits = {**policy["limits"], **(incoming.get("limits") if isinstance(incoming.get("limits"), dict) else {})}
    limits["max_tasks"] = max(1, min(10000, int(limits["max_tasks"])))
    limits["max_runtime_hours"] = max(0.1, min(720.0, float(limits["max_runtime_hours"])))
    limits["max_consecutive_revisions"] = max(1, min(20, int(limits["max_consecutive_revisions"])))
    limits["max_failures_per_task"] = max(0, min(10, int(limits["max_failures_per_task"])))
    limits["max_cost"] = max(0.0, min(100000.0, float(limits["max_cost"])))
    policy["limits"] = limits
    policy["delegated_routes"] = sorted({str(item) for item in policy["delegated_routes"] if str(item) in ROUTE_ORDER})
    policy["delegated_decisions"] = sorted({str(item) for item in policy["delegated_decisions"]})
    if policy["release_policy"] not in {"require_user", "delegated"}:
        raise ValueError("release_policy must be require_user or delegated")
    return policy


class DelegationPolicy:
    def __init__(self, payload: dict[str, Any]):
        # This run-only anchor is intentionally kept outside the reusable
        # project policy.  A user who renews a paused run starts a new allowed
        # runtime window instead of being charged for the days it was paused.
        self.runtime_window_started_at = str(payload.get("runtime_window_started_at") or "")
        self.payload = normalize_policy(payload)

    @property
    def mode(self) -> str:
        return str(self.payload["mode"])

    def permits(self, route: str, decision_type: str) -> bool:
        if self.mode == "collaborative" or route not in self.payload["delegated_routes"]:
            return False
        normalized = DECISION_ALIASES.get(decision_type, decision_type)
        if normalized == "release_approval":
            return self.payload["release_policy"] == "delegated"
        return normalized in self.payload["delegated_decisions"]

    def permits_writeback(self, route: str) -> bool:
        if self.mode == "collaborative" or route not in self.payload["delegated_routes"]:
            return False
        return route != "export-and-release" or self.payload["release_policy"] == "delegated"

    def limit_reason(self, run: dict[str, Any]) -> str:
        limits = self.payload["limits"]
        if int(run["tasks_completed"]) >= int(limits["max_tasks"]):
            return "task-limit"
        started = _parse_time(self.runtime_window_started_at or str(run["started_at"]))
        if started and (datetime.now(timezone.utc) - started).total_seconds() > float(limits["max_runtime_hours"]) * 3600:
            return "runtime-limit"
        if float(run["estimated_cost"]) >= float(limits["max_cost"]) > 0:
            return "cost-limit"
        if int(run["consecutive_revisions"]) >= int(limits["max_consecutive_revisions"]):
            return "revision-limit"
        expires = _parse_time(str(self.payload.get("expires_at") or ""))
        if expires and datetime.now(timezone.utc) >= expires:
            return "authorization-expired"
        return ""
