"""Scene candidate, review, and revision preflight gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..contracts import TaskPackage
from .common import PreflightIssue
from .scene_review_contract import (
    validate_scene_review_contract as _validate_scene_review_contract,
)
from ..sandbox import SandboxManifest


def _validate_scene_candidate_generation_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    """Run candidate-specific quality gates before a worker can request writeback.

    Candidate generation is an Agent-authored task.  Its provenance, new
    character declaration, punctuation/style lint, word budget, and reader
    contract must therefore be visible to the runner's repair loop instead of
    first failing after temporary files have been imported into the project.
    """
    supported_states = {"candidate-generation-provenance", "generation-agent-task", "candidate-revision", "static-revision"}
    if task.current_state not in supported_states:
        return
    if task.current_state in {"candidate-revision", "static-revision"} and not any(
        relative.endswith(".prompt.json") for relative in task.core_managed_outputs
    ):
        return
    candidate_rel = str(task.payload.get("candidate") or "").replace("\\", "/").strip()
    if not candidate_rel:
        candidate_rel = next(
            (
                relative
                for relative in task.expected_outputs
                if relative.endswith(".md") and "agent_tasks" not in relative and "prompt" not in relative
            ),
            "",
        )
    candidate = sandbox.workspace / Path(candidate_rel)
    if not candidate_rel or not candidate.is_file():
        return

    from literary_engineering_studio_engine.literary.style.anti_ai import (
        style_lint_gate,
    )
    from literary_engineering_studio_engine.literary.planning.contracts import (
        word_budget_adherence_for_body,
    )
    from literary_engineering_studio_engine.foundation.draft_text import final_body_from_draft_path
    from literary_engineering_studio_engine.literary.review.creative_quality import (
        load_creative_quality_profile,
    )
    from literary_engineering_studio_engine.literary.review.reader_experience import (
        reader_experience_adherence_for_body,
    )
    from literary_engineering_studio_engine.literary.scene.promotion.generation_gate import (
        candidate_generation_gate,
    )

    _validate_scene_character_candidates(task, sandbox, issues)

    scene_id = str(task.payload.get("scene_id") or task.scene_id or Path(candidate_rel).stem.split("-")[0])
    provenance = candidate_generation_gate(sandbox.workspace, scene_id, candidate)
    if provenance.get("status") != "pass":
        detail = str(provenance.get("message") or "candidate generation provenance is invalid")
        invalid = provenance.get("invalid")
        if isinstance(invalid, list) and invalid:
            detail += ": " + "; ".join(str(item) for item in invalid)
        issues.append(
            PreflightIssue(
                "candidate-provenance-invalid",
                candidate_rel,
                detail,
                "修正候选 manifest 的 provenance、canon 声明和 new_character_register；不能把 blocking_issues 留为非空，也不能伪造已有角色。",
            )
        )

    body = final_body_from_draft_path(candidate)
    if not body:
        return
    lint = style_lint_gate(body, profile=load_creative_quality_profile(sandbox.workspace), scope=scene_id)
    if lint.get("status") == "blocking":
        _append_style_lint_issues(lint, candidate_rel, issues)
    scene_path = sandbox.workspace / "scenes" / f"{scene_id}.yaml"
    budget = word_budget_adherence_for_body(
        sandbox.workspace,
        scene_path,
        body,
        materialization_scope="scene",
    )
    if budget.get("status") not in {"pass", "not_required"}:
        issues.append(
            PreflightIssue(
                "candidate-word-budget-invalid",
                candidate_rel,
                str(budget.get("message") or "candidate failed the scene word budget"),
                _word_budget_repair_instruction(budget),
            )
        )
    reader = reader_experience_adherence_for_body(sandbox.workspace, scene_path, body)
    if reader.get("status") not in {"pass", "not_required"}:
        issues.append(
            PreflightIssue(
                "candidate-reader-contract-invalid",
                candidate_rel,
                str(reader.get("message") or "candidate failed the reader-experience contract"),
                "重写正文以兑现本场读者问题、承诺和场景桥接；不要只改 manifest 描述。",
            )
        )


def _append_style_lint_issues(
    lint: dict[str, object],
    candidate_rel: str,
    issues: list[PreflightIssue],
) -> None:
    blocking = lint.get("blocking")
    rows = blocking if isinstance(blocking, list) else []
    for item in rows[:12]:
        if not isinstance(item, dict):
            continue
        rule = str(item.get("rule") or "unknown")
        severity = str(item.get("severity") or "")
        sample = str(item.get("sample") or "").strip()
        detail = str(item.get("message") or "").strip()
        sample_text = f" 示例：{sample}" if sample else ""
        issues.append(
            PreflightIssue(
                "candidate-style-lint-blocking",
                candidate_rel,
                f"{rule}[{severity}]{sample_text}。{detail}".strip("。"),
                "只重写该条发现命中的句段，同时复核同类变体。不得只替换标点、把“不是……而是……”改成同义对照，"
                "或用另一种模板转折规避检测；修改后保持事件事实、人物意图和正文长度合同。",
            )
        )


def _word_budget_repair_instruction(budget: dict[str, object]) -> str:
    current = int(budget.get("clean_body_chinese_chars") or 0)
    minimum = int(budget.get("min_chinese_chars") or 0)
    maximum = int(budget.get("max_chinese_chars") or 0)
    target = int(budget.get("target_chinese_chars") or 0)
    if minimum and current < minimum:
        safe_target = target if target >= minimum and (not maximum or target <= maximum) else minimum
        deficit = max(0, minimum - current)
        return (
            f"当前清洁正文为 {current} 个中文内容字符，下限 {minimum}，"
            f"安全目标约 {safe_target}，至少仍缺 {deficit}。必须重写完整目标并做足量扩写，"
            "不能只改命中句或保持原长度。扩写必须来自已有场景功能与事件链：展开可观察动作、"
            "对话阻力、程序性过程、信息核验和选择代价；不得重复心理解释、堆叠景物、引入未经授权的 canon，"
            "也不得用同义复述灌水。完成时应留出小幅计数余量，同时不得超过上限"
            f" {maximum or '未设置'}。"
        )
    if maximum and current > maximum:
        excess = current - maximum
        safe_target = target if target and target <= maximum else maximum
        return (
            f"当前清洁正文为 {current} 个中文内容字符，上限 {maximum}，"
            f"安全目标约 {safe_target}，至少需压缩 {excess}。删除重复解释、重复景物和不承担场景功能的段落，"
            "保留事件因果、人物选择、场景转向、衔接钩子与必要的文学节奏；不得用摘要替代正文。"
        )
    return (
        "在不灌水、不重复情绪描写的前提下扩写或压缩正文，使清洁正文达到当前场景的中文内容字符预算。"
    )


def _validate_scene_character_candidates(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    from literary_engineering_studio_engine.literary.assets.registry import (
        ASSET_SCHEMA_NAMES,
    )
    from literary_engineering_studio_engine.prompting.agents.schema import validate_payload

    scene_assets = task.payload.get("scene_character_assets")
    if not isinstance(scene_assets, list):
        return
    for item in scene_assets:
        if not isinstance(item, dict):
            continue
        asset_rel = str(item.get("candidate_path") or "").replace("\\", "/").strip()
        asset_path = sandbox.workspace / Path(asset_rel)
        if not asset_rel or not asset_path.is_file():
            continue
        try:
            payload = json.loads(asset_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        errors, _warnings = validate_payload(payload, ASSET_SCHEMA_NAMES["character"])
        if errors:
            issues.append(
                PreflightIssue(
                    "scene-character-candidate-invalid",
                    asset_rel,
                    "角色候选未通过 character_profile.v1 schema："
                    + "; ".join(str(error) for error in errors[:5]),
                    "按该角色候选 sidecar 的 schema 合同补齐候选 JSON；不得把角色档案写入正式 characters/。",
                )
            )


def _validate_scene_revision_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    if task.current_state not in {"candidate-revision", "static-revision"}:
        return

    candidate_rel = str(task.payload.get("candidate") or "").replace("\\", "/").strip()
    if not candidate_rel:
        candidate_rel = next((item for item in task.expected_outputs if item.endswith("_revision.md") and "report" not in item), "")
    candidate = sandbox.workspace / Path(candidate_rel)
    manifest_rel = next((item for item in task.expected_outputs if item.endswith("_revision.json")), "")
    if not manifest_rel:
        return
    manifest_path = sandbox.workspace / Path(manifest_rel)
    if not manifest_path.is_file():
        return
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(payload, dict):
        return
    for path, message, repair in _revision_preflight_errors(task, sandbox, candidate_rel, candidate, payload):
        issues.append(PreflightIssue("scene-revision-invalid", path, message, repair))


def _revision_preflight_errors(
    task: TaskPackage,
    sandbox: SandboxManifest,
    candidate_rel: str,
    candidate: Path,
    payload: dict[str, object],
) -> list[tuple[str, str, str]]:
    from literary_engineering_studio_engine.foundation.draft_text import final_body_from_draft_path
    from literary_engineering_studio_engine.literary.review.creative_quality import (
        load_creative_quality_profile,
    )
    from literary_engineering_studio_engine.literary.scene.promotion.revision_contract import (
        revision_manifest_errors,
        revision_source_requires_anti_evasion_rows,
    )

    previous = str(task.payload.get("candidate_sha256_before_revision") or "").strip().lower()
    source_rel = str(task.payload.get("revision_source") or "").replace("\\", "/").strip()
    source = sandbox.workspace / Path(source_rel)
    if not (source.is_file() and candidate.is_file()):
        return []
    errors = _revision_file_errors(source_rel, source, candidate_rel, candidate, previous)
    contract_errors = revision_manifest_errors(
        payload,
        scene_id=str(task.payload.get("scene_id") or task.scene_id or candidate.stem.replace("_revision", "")),
        source_rel=source_rel,
        source_sha256=previous,
        source_body=final_body_from_draft_path(source),
        candidate_rel=candidate_rel,
        candidate_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
        candidate_body=final_body_from_draft_path(candidate),
        anti_evasion_rows_required=revision_source_requires_anti_evasion_rows(source,
            quality_profile=load_creative_quality_profile(sandbox.workspace),
            scene_id=str(task.payload.get("scene_id") or task.scene_id or ""),
        ),
    )
    manifest_rel = next((item for item in task.expected_outputs if item.endswith("_revision.json")), "")
    errors.extend(
        (manifest_rel, message, "按 revision prompt 的 exact-source 与 anti_evasion_rows 契约修正 manifest；不得伪造摘要或换皮修订。")
        for message in contract_errors
    )
    return errors


def _revision_file_errors(
    source_rel: str,
    source: Path,
    candidate_rel: str,
    candidate: Path,
    previous: str,
) -> list[tuple[str, str, str]]:
    errors: list[tuple[str, str, str]] = []
    if previous and hashlib.sha256(source.read_bytes()).hexdigest() != previous:
        errors.append((source_rel, "修订源文件已变化，当前任务包的源摘要已过期。", "重新领取 candidate-revision 任务，不能修订旧版本。"))
    if previous and hashlib.sha256(candidate.read_bytes()).hexdigest() == previous:
        errors.append((candidate_rel, "修订正文与被审查候选完全相同。", "对正文落实真实语义修改；不能只更新报告和 manifest。"))
    return errors


def _validate_continuity_ledger_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    """Reject pending continuity records before formal writeback."""

    from literary_engineering_studio_engine.literary.assets.continuity.ledger import (
        continuity_ledger_status,
    )

    state = str(task.current_state or task.payload.get("current_state") or "")
    if state not in {"continuity-ledger-agent-task", "continuity-ledger-review"}:
        return
    scene_id = str(task.payload.get("scene_id") or "").strip()
    if not scene_id:
        return
    review = state == "continuity-ledger-review"
    passed, message, _payload = continuity_ledger_status(
        sandbox.workspace,
        scene_id,
        require_review=review,
    )
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
    """Validate the machine handoff of a creative branch decision."""

    from literary_engineering_studio_engine.tasking.gates import branch_selection_status

    state = str(task.current_state or task.payload.get("current_state") or "")
    if state not in {"branch-agent-task", "branch-selection"}:
        return
    scene_id = str(task.payload.get("scene_id") or "").strip()
    if not scene_id:
        return
    relative = f"branches/{scene_id}/branch_selection.md"
    status = branch_selection_status(sandbox.workspace / relative)
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
    _validate_selected_branch_membership(
        sandbox,
        scene_id,
        relative,
        str(status.get("selected_branch") or "").strip(),
        issues,
    )


def _validate_selected_branch_membership(
    sandbox: SandboxManifest,
    scene_id: str,
    selection_relative: str,
    selected: str,
    issues: list[PreflightIssue],
) -> None:
    manifest_relative = f"branches/{scene_id}/branch_manifest.json"
    try:
        payload = json.loads(
            (sandbox.workspace / manifest_relative).read_text(encoding="utf-8")
        )
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
    if not branch_ids or selected not in branch_ids:
        issues.append(
            PreflightIssue(
                "branch-selection-membership",
                selection_relative,
                f"selected_branch `{selected}` is not an id in validated Agent proposals or {manifest_relative}",
                "使用 branch_proposals.json 或 branch_manifest.json 中的一个精确 branch_id，并保留选择理由与被拒绝分支说明。",
            )
        )


def _selectable_branch_ids(
    root: Path,
    scene_id: str,
    manifest: dict[str, object],
) -> set[str]:
    from literary_engineering_studio_engine.semantic_task_contracts import (
        validated_branch_proposal_ids,
    )

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
