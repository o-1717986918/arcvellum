"""Delegation policy normalization and quality stops for Autopilot."""

from __future__ import annotations

from typing import Any


POLICY_SCHEMA = "arcvellum/delegation-policy/v0.1"
MODES = {"collaborative", "supervised_auto", "full_auto"}
LITERARY_KERNELS = {"strict-v1", "lean-v2"}
SCENE_EXECUTION_MODES = {"draft", "standard", "publication"}
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


def default_policy(
    mode: str = "collaborative",
    *,
    literary_kernel: str = "strict-v1",
    scene_execution_mode: str = "standard",
) -> dict[str, Any]:
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
        "literary_kernel": literary_kernel,
        "scene_execution_mode": scene_execution_mode,
        "delegated_routes": delegated_routes,
        "delegated_decisions": decisions,
        "limits": {
            "max_failures_per_task": 2,
            "stop_after_formal_units": 0,
        },
        "release_policy": "delegated" if normalized == "full_auto" else "require_user",
    }


def normalize_policy(value: dict[str, Any] | None) -> dict[str, Any]:
    incoming = value or {}
    mode = str(incoming.get("mode") or "collaborative")
    if mode not in MODES:
        raise ValueError("mode must be collaborative, supervised_auto, or full_auto")
    policy = default_policy(mode)
    for key in (
        "delegated_routes",
        "delegated_decisions",
        "release_policy",
        "literary_kernel",
        "scene_execution_mode",
    ):
        if key in incoming:
            policy[key] = incoming[key]
    limits = {**policy["limits"], **(incoming.get("limits") if isinstance(incoming.get("limits"), dict) else {})}
    policy["limits"] = {
        "max_failures_per_task": max(
            0, min(10, int(limits["max_failures_per_task"]))
        ),
        "stop_after_formal_units": max(
            0, min(100_000, int(limits.get("stop_after_formal_units") or 0))
        ),
    }
    policy["delegated_routes"] = sorted({str(item) for item in policy["delegated_routes"] if str(item) in ROUTE_ORDER})
    policy["delegated_decisions"] = sorted({str(item) for item in policy["delegated_decisions"]})
    if policy["release_policy"] not in {"require_user", "delegated"}:
        raise ValueError("release_policy must be require_user or delegated")
    if policy["literary_kernel"] not in LITERARY_KERNELS:
        raise ValueError("literary_kernel must be strict-v1 or lean-v2")
    if policy["scene_execution_mode"] not in SCENE_EXECUTION_MODES:
        raise ValueError("scene_execution_mode must be draft, standard, or publication")
    return policy


class DelegationPolicy:
    def __init__(self, payload: dict[str, Any]):
        self.payload = normalize_policy(payload)

    @property
    def mode(self) -> str:
        return str(self.payload["mode"])

    @property
    def literary_kernel(self) -> str:
        return str(self.payload["literary_kernel"])

    @property
    def scene_execution_mode(self) -> str:
        return str(self.payload["scene_execution_mode"])

    @property
    def stop_after_formal_units(self) -> int:
        return int(self.payload["limits"]["stop_after_formal_units"])

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
