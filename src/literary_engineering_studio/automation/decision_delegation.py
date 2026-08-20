"""Bounded delegated-decision transaction for automated creation runs."""
from __future__ import annotations

from pathlib import Path
import threading
from typing import Any, Callable

from ..advisor.creative_steward import CreativeSteward, CreativeStewardCancelled
from ..application.project_manager import record_direction
from ..application.persistence_ports import AutopilotRepositoryPort
from ..application.style.mount_service import StyleMountApplicationService
from ..projections.core_read_models import record_choice
from .policy import DelegationPolicy
from .support import (
    _choice_fingerprint,
    _delegated_direction_message,
    _project_direction,
    _run_steward_decision,
)


MATERIALIZED_DECISIONS = {
    "branch_selection",
    "style_mount",
    "asset_approval",
    "release_approval",
    "canon_patch_approval",
    "state_patch_confirmation",
    "revision_direction",
}
DIRECTION_DECISIONS = {"word_budget_direction"}


class DecisionDelegator:
    """Execute and durably record one policy-authorized Steward decision."""

    def __init__(
        self,
        config: dict[str, Any],
        store: AutopilotRepositoryPort,
        style_mount_service: StyleMountApplicationService,
        pause_for: Callable[[str, str, str], None],
    ) -> None:
        self.config = config
        self.runs = store
        self.style_mount_service = style_mount_service
        self.pause_for = pause_for

    def execute(
        self,
        run_id: str,
        project: Path,
        route: str,
        policy: DelegationPolicy,
        steward: CreativeSteward,
        choice: dict[str, Any],
        *,
        task_id: str = "",
        stop: threading.Event | None = None,
    ) -> bool:
        decision_type = str(choice.get("decision_type") or "")
        if not policy.permits(route, decision_type):
            self.pause_for(run_id, "human-decision-required", "当前决定不在自动授权范围内。")
            return False
        if _stopped(stop):
            return False
        self._started(run_id, route, task_id, decision_type, choice)
        decision = self._decide(run_id, project, steward, choice, decision_type, stop)
        if decision is None:
            return False
        if decision["requires_human"]:
            self.pause_for(run_id, "steward-escalation", decision["human_reason"] or "创作代理认为需要你来决定。")
            return True
        evidence = self._materialize(project, choice, decision, decision_type, task_id)
        self.runs.record_delegated_decision(
            run_id,
            _decision_record(run_id, project, route, task_id, policy, choice, decision, evidence),
        )
        return True

    def _started(
        self,
        run_id: str,
        route: str,
        task_id: str,
        decision_type: str,
        choice: dict[str, Any],
    ) -> None:
        self.runs.append_autopilot_event(
            run_id,
            "decision.started",
            {
                "route": route,
                "task_id": task_id or str(choice.get("task_id") or ""),
                "decision_type": decision_type,
                "choice_id": str(choice.get("choice_id") or ""),
            },
        )

    def _decide(
        self,
        run_id: str,
        project: Path,
        steward: CreativeSteward,
        choice: dict[str, Any],
        decision_type: str,
        stop: threading.Event | None,
    ) -> dict[str, Any] | None:
        try:
            decision = _run_steward_decision(steward, project, choice, _project_direction(project), stop)
        except CreativeStewardCancelled:
            self._cancelled(run_id, decision_type)
            return None
        if _stopped(stop):
            self._cancelled(run_id, decision_type)
            return None
        return decision

    def _cancelled(self, run_id: str, decision_type: str) -> None:
        self.runs.append_autopilot_event(run_id, "decision.cancelled", {"decision_type": decision_type})

    def _materialize(
        self,
        project: Path,
        choice: dict[str, Any],
        decision: dict[str, Any],
        decision_type: str,
        task_id: str,
    ) -> list[str]:
        recorded = record_choice(
            self.config,
            project,
            {
                **choice,
                "task_id": task_id or str(choice.get("task_id") or ""),
                "selected": decision["selected_option"],
                "rationale": decision["rationale"],
                "actor": "delegated-agent:creative-steward",
                "materialize": decision_type in MATERIALIZED_DECISIONS,
            },
            style_mount_service=self.style_mount_service,
        )
        evidence = _choice_evidence(recorded)
        if decision_type in DIRECTION_DECISIONS:
            direction = record_direction(
                project,
                _delegated_direction_message(choice, decision),
                actor="delegated-agent:creative-steward",
            )
            evidence.append(str(direction.get("digest") or ""))
        return [item for item in evidence if item]


def _stopped(stop: threading.Event | None) -> bool:
    return stop is not None and stop.is_set()


def _choice_evidence(recorded: dict[str, Any]) -> list[str]:
    evidence = [str(recorded.get("choice_path") or "")]
    if recorded.get("materialized"):
        evidence.append(str(recorded["materialized"]))
    style_mount = recorded.get("style_mount") if isinstance(recorded.get("style_mount"), dict) else {}
    if style_mount.get("receipt"):
        evidence.append(str(style_mount["receipt"]))
    return evidence


def _decision_record(
    run_id: str,
    project: Path,
    route: str,
    task_id: str,
    policy: DelegationPolicy,
    choice: dict[str, Any],
    decision: dict[str, Any],
    evidence: list[str],
) -> dict[str, Any]:
    return {
        **decision,
        "project_root": str(project),
        "delegation_id": run_id,
        "policy_version": policy.payload["version"],
        "route": route,
        "task_id": task_id,
        "selected_option": decision["selected_option"],
        "choice_fingerprint": _choice_fingerprint(choice),
        "choice_evidence": evidence,
    }
