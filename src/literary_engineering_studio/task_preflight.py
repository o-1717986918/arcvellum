"""Stable facade for deterministic sandbox checks before formal writeback."""

from __future__ import annotations

import json
from pathlib import Path

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
    _validate_scene_candidate_generation_contract,
    _validate_scene_review_contract,
    _validate_scene_revision_contract,
)
from .sandbox import SandboxManifest, sandbox_change_issues
from literary_engineering_studio_engine.semantic_task_contracts import (
    semantic_artifact_definition,
    semantic_artifact_errors,
    semantic_artifact_relative_path,
    validated_branch_proposal_ids,
)
from literary_engineering_studio_engine.continuity_ledger import continuity_ledger_status
from literary_engineering_studio_engine.flow_gates import branch_selection_status


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


def _validate_continuity_ledger_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    """Run the core ledger contract before any Agent output can be imported.

    Continuity ledgers predate the generic semantic-artifact registry, so they
    need their own bridge here. Without it a pending scaffold can pass Studio
    preflight and fail only after formal writeback, leaving the user with a
    misleading core-CLI error instead of an in-session repair turn.
    """

    current_state = str(task.current_state or task.payload.get("current_state") or "")
    if current_state not in {"continuity-ledger-agent-task", "continuity-ledger-review"}:
        return
    scene_id = str(task.payload.get("scene_id") or "").strip()
    if not scene_id:
        return
    review = current_state == "continuity-ledger-review"
    passed, message, _payload = continuity_ledger_status(sandbox.workspace, scene_id, require_review=review)
    if passed:
        return
    relative = (
        f"reviews/continuity/{scene_id}_ledger_review.json"
        if review
        else f"plot/ledger_deltas/{scene_id}.json"
    )
    issues.append(
        PreflightIssue(
            "continuity-ledger-contract",
            relative,
            message,
            _continuity_ledger_repair_instruction(scene_id, review=review),
        )
    )


def _continuity_ledger_repair_instruction(scene_id: str, *, review: bool) -> str:
    """Describe the missing editorial record without inviting a bypass."""

    if review:
        return (
            f"重写 `reviews/continuity/{scene_id}_ledger_review.json` 的 pending 模板。保留 schema、scene_id、"
            "delta_path 和精确 delta_sha256；以独立审查会话写入 `status=complete`、`verdict=pass`、非空 "
            "findings、`required_changes=[]`。若 delta 有实质缺陷，不得伪造 pass，应写入可执行的 "
            "required_changes；不要创建 completion receipt。"
        )
    return (
        f"重写 `plot/ledger_deltas/{scene_id}.json`，不能保留 pending 初始化模板。保留 schema、scene_id 和 "
        "source_draft；以已晋升正文为唯一证据。若新增/更新读者问题或承诺，写入非空 evidence_paths 与具体 "
        "changes；若确实无变化，两个 changes 列表可为空，但必须写出具体 no_change_reason。完成后设置 "
        "`status=complete`；不要编辑正式账本或创建 completion receipt。"
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
    branch_ids = _selectable_branch_ids(sandbox.workspace, scene_id, payload)
    selected = str(status.get("selected_branch") or "").strip()
    if not branch_ids or selected not in branch_ids:
        issues.append(
            PreflightIssue(
                "branch-selection-membership",
                relative,
                f"selected_branch `{selected}` is not an id in validated Agent proposals or {manifest_relative}",
                "使用 branch_proposals.json 或 branch_manifest.json 中的一个精确 branch_id，并保留选择理由与被拒绝分支说明。",
            )
        )


def _selectable_branch_ids(root: Path, scene_id: str, manifest: dict[str, object]) -> set[str]:
    branches = manifest.get("branches") if isinstance(manifest, dict) else None
    ids = {
        str(item.get("branch_id") or item.get("id") or "").strip()
        for item in branches
        if isinstance(item, dict)
    } if isinstance(branches, list) else set()
    try:
        ids.update(validated_branch_proposal_ids(root, scene_id, manifest))
    except ValueError:
        pass
    return ids
