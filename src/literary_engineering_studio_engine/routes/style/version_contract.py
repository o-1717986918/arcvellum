"""Formal route contract for deterministic immutable style-version builds."""

from __future__ import annotations

from pathlib import Path

from ...literary.style.session import load_style_session
from ...literary.style.version import (
    inspect_style_profile_version,
    plan_style_profile_version,
    style_version_source_paths,
)
from ...task_paths import relative_path


def style_version_blueprints(
    root: Path,
    profile_id: str,
    profile_dir: str,
) -> dict[str, dict[str, object]]:
    profile = root / profile_dir
    if not load_style_session(profile):
        return {}
    plan = plan_style_profile_version(root, profile, target_id=profile_id)
    outputs = [relative_path(path, root) for path in plan.paths.all_files()]
    sources = [relative_path(path, root) for path in style_version_source_paths(plan)]
    return {
        "style-version-build": {
            "task_type": "deterministic-cli",
            "prompt_asset_id": "route.style-engineering.version.build.v1",
            "command": (
                f'python -m literary_engineering_studio_engine build-style-version "<project>" '
                f'--profile-dir "{profile_dir}" --target-id "{profile_id}"'
            ),
            "source_paths": sources,
            "expected_outputs": outputs,
            "hard_constraints": [
                "Build the exact content-addressed style version from current accepted evidence.",
                "Version identity, path, content hash, and compatibility manifest are machine-owned.",
                "Do not mount or mutate an existing immutable version.",
            ],
            "style_constraints": [],
            "validation_gates": [
                "independent style semantic review passes current evidence",
                "immutable style_version.json matches every packaged artifact digest",
                "compatible style_skill.json is ready and content-bound",
            ],
            "next_allowed_states": ["ready", "style-version-conflict"],
        },
        "style-version-conflict": {
            "task_type": "human-approval-boundary",
            "prompt_asset_id": "route.style-engineering.version.conflict.v1",
            "command": "Inspect and restore or quarantine the conflicting immutable style version.",
            "source_paths": [
                relative_path(plan.paths.manifest, root)
                if plan.paths.manifest.is_file()
                else profile_dir
            ],
            "expected_outputs": [],
            "hard_constraints": [
                "Do not overwrite, patch, or silently reuse a conflicting immutable version directory.",
                "A new version must be derived from current evidence or the damaged artifact restored explicitly.",
            ],
            "style_constraints": [],
            "validation_gates": ["immutable version conflict is explicitly resolved"],
            "next_allowed_states": ["style-version-build", "ready"],
        },
    }


def validate_style_version_task(
    root: Path,
    task: dict[str, object],
    profile_dir: Path,
) -> tuple[list[str], list[str]]:
    state = str(task.get("current_state") or "")
    if state not in {"style-version-build", "style-version-conflict"}:
        return [], []
    target_id = str(task.get("profile_id") or task.get("target_id") or "")
    plan = plan_style_profile_version(root, profile_dir, target_id=target_id)
    stage, errors = inspect_style_profile_version(plan)
    if state == "style-version-conflict":
        if stage == "ready":
            return [], ["immutable style version conflict has been resolved"]
        detail = list(errors) or ["immutable style version conflict is unresolved"]
        return detail, []
    if stage != "ready":
        detail = list(errors) or [f"style version build did not reach ready state: {stage}"]
        return detail, []
    return [], [f"immutable style version {plan.version_id} passes integrity gates"]
