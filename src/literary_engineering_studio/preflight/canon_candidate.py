"""Canon patch candidate validation inside the Worker repair loop."""

from __future__ import annotations

import json

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .common import PreflightIssue
from literary_engineering_studio_engine.public.literary import canon_patch_candidate_issues


def validate_canon_patch_candidate(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    """Reject malformed nested Canon facts before formal project writeback."""

    if str(task.current_state or task.payload.get("current_state") or "") != "canon-patch-json":
        return
    scene_id = str(task.payload.get("scene_id") or "").strip()
    relative = next(
        (path for path in task.expected_outputs if path.endswith("_canon_patch.json")),
        "",
    )
    if not relative:
        return
    path = sandbox.workspace / relative
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return

    for violation in canon_patch_candidate_issues(payload, expected_scene_id=scene_id):
        issues.append(
            PreflightIssue(
                "canon-patch-contract",
                f"{relative}#{violation.path}",
                violation.message,
                (
                    f"只修复 `{relative}` 中 `{violation.path}` 对应的 Canon 候选字段；"
                    "每条 items 记录必须把 type、summary、source_evidence、target_files、risk_level 和 "
                    "requires_user_approval 放在同一个对象内。不要把条目字段写到 JSON 根对象，不要修改 "
                    "Studio-owned 机器字段，也不要自行创建 completion marker。"
                ),
            )
        )


__all__ = ["validate_canon_patch_candidate"]
