"""Stable facade for deterministic sandbox checks before formal writeback."""

from __future__ import annotations

import json
from pathlib import Path
import re

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
from literary_engineering_studio_engine.literary.scene.branching.proposals import (
    branch_proposal_scaffold,
)
from literary_engineering_studio_engine.reader_experience import (
    chapter_obligation_contract_issues,
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
    _validate_chapter_obligation_contract(task, sandbox, issues)
    _validate_semantic_task_contract(task, sandbox, issues)
    _validate_continuity_ledger_contract(task, sandbox, issues)
    _validate_branch_selection_contract(task, sandbox, issues)
    return PreflightResult(not issues, tuple(issues))


def _validate_chapter_obligation_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    current_state = str(task.current_state or task.payload.get("current_state") or "")
    if current_state != "reader-experience-contract":
        return
    chapter_id = _chapter_id_for_reader_contract(task, sandbox.workspace)
    relative = f"plot/chapter_obligations/{chapter_id}.json"
    path = sandbox.workspace / relative
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return
    messages = chapter_obligation_contract_issues(payload)
    if not messages:
        return
    issues.append(
        PreflightIssue(
            "chapter-obligation-contract",
            relative,
            "; ".join(messages),
            (
                f"只修复 `{relative}` 的章节义务机械合同并保留已经成立的创意内容。"
                "must_payoff、must_setup、must_change、must_not_resolve、inherited_hooks 和 "
                "expansion_needed 必须是 JSON 字符串数组；不需扩写时写 "
                "expansion_needed=[]，不得写 false、null 或说明字符串。"
                "reader_experience_by_scene 必须是非空数组。不要自行创建 completion marker。"
            ),
        )
    )


def _chapter_id_for_reader_contract(task: TaskPackage, workspace: Path) -> str:
    scene_id = str(task.payload.get("scene_id") or "").strip()
    scene_rel = str(task.payload.get("scene") or f"scenes/{scene_id}.yaml").strip()
    scene_path = workspace / scene_rel
    if scene_path.is_file():
        match = re.search(
            r"(?m)^\s*chapter_id:\s*['\"]?([^'\"\s#]+)",
            scene_path.read_text(encoding="utf-8", errors="ignore"),
        )
        if match:
            return match.group(1).strip()
    for relative in task.expected_outputs:
        match = re.fullmatch(
            r"plot/chapter_obligations/([^/]+)\.json",
            relative,
        )
        if match:
            return match.group(1)
    return "chapter_0001"


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
    messages = semantic_artifact_errors(sandbox.workspace, current_state, scene_id)
    if current_state == "branch-agent-task" and messages:
        issues.append(
            PreflightIssue(
                "semantic-contract",
                relative,
                _compact_semantic_errors(messages),
                _semantic_artifact_repair_instruction(
                    current_state,
                    relative,
                    branch_count=_branch_count(sandbox.workspace, scene_id),
                ),
            )
        )
        return
    for message in messages:
        issues.append(
            PreflightIssue(
                "semantic-contract",
                relative,
                message,
                _semantic_artifact_repair_instruction(current_state, relative),
            )
        )


def _semantic_artifact_repair_instruction(
    current_state: str,
    relative: str,
    *,
    branch_count: int = 0,
) -> str:
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
    if current_state == "branch-agent-task":
        count_rule = f"恰好 {branch_count} 条" if branch_count else "2-5 条"
        shape = json.dumps(branch_proposal_scaffold(), ensure_ascii=False, indent=2)
        return (
            f"只修复 `{relative}` 的机械合同并保留已经成立的创意内容。`proposals` 必须有{count_rule}，"
            "每条严格使用下列字段形状，不得使用 id/rationale/irreversible_cost/next_scene_pressure 等近义字段：\n"
            f"{shape}\n"
            "将示例中的所有 <replace: ...> 和 agent_branch_replace_* 替换为本场真实内容；"
            "state_writeback 五项保持字符串列表且至少一项非空；每条含 2-8 个 beat，serves 是义务名列表，"
            "所有 beat 合计覆盖 incoming_bridge、goal、turn、cost、reader_effect、outgoing_hook。"
            "顶层 status=complete，evidence_paths/findings 非空。不要自行创建 completion marker。"
        )
    return "完成任务要求的 Agent 判断；保留已有有效内容，并修正 semantic artifact 的 schema、scene_id、列表字段、证据和完成状态。"


def _branch_count(workspace: Path, scene_id: str) -> int:
    path = workspace / "branches" / scene_id / "branch_manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return max(0, int(payload.get("branch_count") or 0)) if isinstance(payload, dict) else 0
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return 0


def _compact_semantic_errors(messages: list[str]) -> str:
    unique: list[str] = []
    for message in messages:
        normalized = str(message).strip()
        if normalized and normalized not in unique:
            unique.append(normalized)
    sample = "; ".join(unique[:8])
    suffix = f"; 另有 {len(unique) - 8} 项同类问题" if len(unique) > 8 else ""
    return f"branch proposal semantic artifact has {len(unique)} contract violation(s): {sample}{suffix}"
