"""Persistence and migration service for Autopilot delegation policy."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .policy import default_policy, normalize_policy
from ..compatibility.literary_kernel import (
    initial_kernel_selection,
    kernel_compatibility_manifest,
)


class AutopilotPolicyService:
    def __init__(self, runs: Any, sessions: Any):
        self._runs = runs
        self._sessions = sessions

    def read(self, project_root: Path) -> dict[str, Any]:
        root = str(project_root.expanduser().resolve())
        stored = self._sessions.read_delegation_policy(root)
        if stored is not None:
            return {**stored, "policy": normalize_policy(stored.get("policy"))}
        selection = initial_kernel_selection(project_root)
        return self._sessions.save_delegation_policy(
            root,
            default_policy(
                literary_kernel=selection.kernel,
                scene_execution_mode=selection.scene_execution_mode,
            ),
        )

    def compatibility(self, project_root: Path) -> dict[str, Any]:
        policy = self.read(project_root)["policy"]
        return {
            "manifest": kernel_compatibility_manifest(),
            "current_kernel": policy["literary_kernel"],
            "scene_execution_mode": policy["scene_execution_mode"],
            "rollback_target": "strict-v1",
        }

    def migrate(
        self,
        project_root: Path,
        *,
        target_kernel: str,
        scene_execution_mode: str = "",
    ) -> dict[str, Any]:
        current = self.read(project_root)["policy"]
        previous = str(current["literary_kernel"])
        saved = self.save(
            project_root,
            {
                **current,
                "literary_kernel": target_kernel,
                "scene_execution_mode": scene_execution_mode or current["scene_execution_mode"],
            },
        )
        manifest = kernel_compatibility_manifest()
        selected = saved["policy"]["literary_kernel"]
        return {
            **saved,
            "previous_kernel": previous,
            "current_kernel": selected,
            "compatibility_status": manifest["kernels"][selected]["status"],
            "selection_source": "explicit-user-migration",
            "rollback_target": "strict-v1",
        }

    def save(self, project_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
        root = str(project_root.expanduser().resolve())
        active = self._runs.latest_autopilot_run(root)
        if active and active["status"] == "running":
            raise ValueError("请先暂停自动创作，再修改创作模式。")
        policy = normalize_policy(payload)
        saved = self._sessions.save_delegation_policy(root, policy)
        if active and active["status"] in {"paused", "blocked", "failed"}:
            saved["run"] = self._update_paused_run(active, policy)
        return saved

    def _update_paused_run(self, active: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
        run_id = active["run_id"]
        renewed = self._runs.update_autopilot_run_policy(run_id, policy)
        self._runs.append_autopilot_event(
            run_id,
            "autopilot.policy_updated",
            {"mode": policy["mode"], "limits": policy["limits"]},
        )
        return renewed


__all__ = ["AutopilotPolicyService"]
