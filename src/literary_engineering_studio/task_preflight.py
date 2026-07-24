"""Stable facade for deterministic sandbox checks before formal writeback."""

from __future__ import annotations

import json

from .contracts import TaskPackage
from .preflight.assets import _validate_asset_candidate, _validate_asset_review_contract
from .preflight.canonicalization import canonicalize_task_outputs
from .preflight.common import (
    COMPLETION_SCHEMA,
    PreflightIssue,
    PreflightResult,
    _validate_completion_markers,
    _validate_json,
    _validate_review_conclusions,
)
from .preflight.review import _validate_project_review_contract, _validate_source_extraction_revision
from .preflight.scene import (
    _validate_scene_candidate_generation_contract,
    _validate_scene_review_contract,
    _validate_scene_revision_contract,
)
from .sandbox import SandboxManifest, sandbox_change_issues
from literary_engineering_studio_engine.semantic_task_contracts import (
    semantic_artifact_definition,
    semantic_artifact_errors,
    semantic_artifact_relative_path,
)
from literary_engineering_studio_engine.flow_gates import branch_selection_status


def validate_task_outputs(task: TaskPackage, sandbox: SandboxManifest) -> PreflightResult:
    """Run every deterministic Gate in its established order without short-circuiting."""

    issues: list[PreflightIssue] = []
    for message in sandbox_change_issues(sandbox):
        issues.append(PreflightIssue("unexpected-change", "workspace", message, "撤销所有不属于 Allowed Outputs 的修改。"))

    for relative in task.expected_outputs:
        path = sandbox.workspace / relative
        if not path.exists():
            issues.append(PreflightIssue("missing-output", relative, "预期产物不存在。", "创建该产物并按 Output Contract 填写完整内容。"))
            continue
        if path.is_file() and path.stat().st_size == 0:
            issues.append(PreflightIssue("empty-output", relative, "预期产物为空。", "写入任务要求的完整内容。"))
            continue
        if path.is_file() and path.suffix.lower() == ".json":
            _validate_json(relative, path, issues)

    _validate_completion_markers(task, sandbox, issues)
    _validate_review_conclusions(task, sandbox, issues)
    _validate_asset_candidate(task, sandbox, issues)
    _validate_asset_review_contract(task, sandbox, issues)
    _validate_project_review_contract(task, sandbox, issues)
    _validate_scene_review_contract(task, sandbox, issues)
    _validate_scene_candidate_generation_contract(task, sandbox, issues)
    _validate_scene_revision_contract(task, sandbox, issues)
    _validate_source_extraction_revision(task, sandbox, issues)
    _validate_semantic_task_contract(task, sandbox, issues)
    _validate_branch_selection_contract(task, sandbox, issues)
    return PreflightResult(not issues, tuple(issues))


def _validate_semantic_task_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    """Run the same typed contract before writeback that the CLI gate enforces.

    This deliberately runs inside the Worker repair loop. A model can correct
    a pending lifecycle field or a list/object mismatch in the same session,
    rather than importing a placeholder and failing only in the core gate.
    """

    current_state = str(task.current_state or task.payload.get("current_state") or "")
    scene_id = str(task.payload.get("scene_id") or "").strip()
    if not scene_id or semantic_artifact_definition(current_state) is None:
        return
    relative = semantic_artifact_relative_path(current_state, scene_id)
    if not relative:
        return
    for message in semantic_artifact_errors(sandbox.workspace, current_state, scene_id):
        issues.append(
            PreflightIssue(
                "semantic-contract",
                relative,
                message,
                "完成任务要求的 Agent 判断；保留已有有效内容，并修正 semantic artifact 的 schema、scene_id、列表字段与完成状态。",
            )
        )


def _validate_branch_selection_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    """Reject reader-friendly but machine-incomplete branch decisions pre-writeback.

    A branch decision is creative judgment, but its two routing fields are not:
    ``decision`` and ``selected_branch`` are the state machine's handoff.  The
    Worker must catch Markdown prose such as ``**Selected**: ...`` before it is
    imported, otherwise the core CLI has to roll back a completed Agent run.
    """

    state = str(task.current_state or task.payload.get("current_state") or "")
    if state not in {"branch-agent-task", "branch-selection"}:
        return
    scene_id = str(task.payload.get("scene_id") or "").strip()
    if not scene_id:
        return
    relative = f"branches/{scene_id}/branch_selection.md"
    selection_path = sandbox.workspace / relative
    status = branch_selection_status(selection_path)
    if status.get("status") != "selected":
        issues.append(
            PreflightIssue(
                "branch-selection-contract",
                relative,
                str(status.get("message") or "branch selection is incomplete"),
                "在 branch_selection.md 的独立行写入 `decision: selected` 和 "
                "`selected_branch: <branch_id>`；不要只在标题、表格或自然语言中声明选择。",
            )
        )
        return

    manifest_relative = f"branches/{scene_id}/branch_manifest.json"
    manifest_path = sandbox.workspace / manifest_relative
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        issues.append(
            PreflightIssue(
                "branch-manifest-invalid",
                manifest_relative,
                f"cannot validate selected branch against manifest: {exc}",
                "保留当前选择，读取正式 branch_manifest.json 后使用其中存在的 branch_id。",
            )
        )
        return
    branches = payload.get("branches") if isinstance(payload, dict) else None
    branch_ids = {
        str(item.get("branch_id") or item.get("id") or "").strip()
        for item in branches
        if isinstance(item, dict)
    } if isinstance(branches, list) else set()
    selected = str(status.get("selected_branch") or "").strip()
    if not branch_ids or selected not in branch_ids:
        issues.append(
            PreflightIssue(
                "branch-selection-membership",
                relative,
                f"selected_branch `{selected}` is not an id in {manifest_relative}",
                "使用 branch_manifest.json 的一个精确 branch_id，并保留选择理由与被拒绝分支说明。",
            )
        )
