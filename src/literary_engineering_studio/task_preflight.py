"""Stable facade for deterministic sandbox checks before formal writeback."""

from __future__ import annotations

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
from .preflight.review import (
    _validate_project_review_contract,
    _validate_source_extraction_revision,
    validate_archaeology_chunk_output,
    validate_archaeology_reconstruction_output,
)
from .preflight.scene import (
    _validate_branch_selection_contract,
    _validate_continuity_ledger_contract,
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


def validate_task_outputs(task: TaskPackage, sandbox: SandboxManifest) -> PreflightResult:
    """Run every deterministic Gate in its established order without short-circuiting."""

    issues: list[PreflightIssue] = []
    for message in sandbox_change_issues(sandbox):
        issues.append(PreflightIssue("unexpected-change", "workspace", message, "撤销所有不属于 Allowed Outputs 的修改。"))

    completion_outputs = {
        contract.path
        for contract in task.execution_contract.outputs
        if contract.kind == "completion-evidence"
    }
    for relative in task.expected_outputs:
        # Lifecycle receipts are created by canonicalize_task_outputs after
        # substantive Agent output exists.  They must never be presented as a
        # missing file the Agent should repair by hand.
        if relative in completion_outputs:
            continue
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
    validate_archaeology_chunk_output(task, sandbox, issues)
    validate_archaeology_reconstruction_output(task, sandbox, issues)
    _validate_source_extraction_revision(task, sandbox, issues)
    _validate_semantic_task_contract(task, sandbox, issues)
    _validate_continuity_ledger_contract(task, sandbox, issues)
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
                _semantic_artifact_repair_instruction(current_state, relative),
            )
        )


def _semantic_artifact_repair_instruction(current_state: str, relative: str) -> str:
    """Give the repair turn an executable contract, not a schema-name hint."""

    if current_state == "composition-agent-task":
        return (
            f"打开 `{relative}` 并替换 pending 模板。若编排确实合格，必须写入 "
            '`status="complete"`、`verdict="pass"`、`ready_for_generation=true`、非空 `evidence_paths`、'
            "非空 `findings`、`required_changes=[]`；保留既有 schema、scene_id、source_artifact 和 "
            "composition_sha256。若不合格，不得伪造 pass，改为 needs_revision/revise_required 并列出具体修订项。"
        )
    if current_state == "state-agent-task":
        return (
            f"打开 `{relative}` 并替换 pending 模板。若状态补丁有充分正文/构图依据，必须写入 "
            '`status="complete"`、`verdict="pass"`、`approval_recommendation="approve"`、非空 '
            '`evidence_paths`、非空 `findings`、`required_changes=[]`；保留既有 schema、scene_id、'
            "source_artifact 和 state_patch_sha256。不要自行创建 completion marker。若证据不足，使用 "
            "needs_revision/revise_required/hold，并列出可执行的 required_changes。"
        )
    if current_state == "canon-agent-task":
        return (
            f"打开 `{relative}` 并替换 pending 模板。若 Canon 候选或无变化理由有充分证据，必须写入 "
            '`status="complete"`、`verdict="pass"`、`approval_recommendation="approve"`、非空 '
            '`evidence_paths`、非空 `findings`、`required_changes=[]`；保留既有 schema、scene_id、'
            "source_artifact 和 canon_patch_sha256。不要自行创建 completion marker。若证据不足，使用 "
            "needs_revision/revise_required/hold，并列出可执行的 required_changes。"
        )
    return "完成任务要求的 Agent 判断；保留已有有效内容，并修正 semantic artifact 的 schema、scene_id、列表字段、证据和完成状态。"
