"""Project-level canon and committee review contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .common import PreflightIssue


PROJECT_REVIEW_STATES = {
    "canon-review-agent-task",
    "canon-review-pass",
    "committee-agent-task",
    "committee-pass",
}


def validate_project_review_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    state = task.current_state
    if state not in PROJECT_REVIEW_STATES:
        return
    committee = state.startswith("committee")
    relative = "reviews/agent/committee_project-final-audit.json" if committee else "reviews/agent/canon_review.json"
    payload = _read_review(sandbox, relative)
    if payload is None:
        return
    if state in {"canon-review-pass", "committee-pass"}:
        _validate_revision(task, sandbox, payload, relative, committee, issues)
        return
    _validate_initial(payload, relative, committee, issues)


def _read_review(sandbox: SandboxManifest, relative: str) -> dict[str, object] | None:
    path = sandbox.workspace / relative
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _add_issue(
    issues: list[PreflightIssue],
    relative: str,
    field: str,
    message: str,
    repair: str,
) -> None:
    issues.append(PreflightIssue("project-review-invalid", f"{relative}#{field}", message, repair))


def _validate_revision(
    task: TaskPackage,
    sandbox: SandboxManifest,
    payload: dict[str, object],
    relative: str,
    committee: bool,
    issues: list[PreflightIssue],
) -> None:
    verdict_field = "final_recommendation" if committee else "conclusion"
    if str(payload.get(verdict_field) or "").strip().lower() != "recheck_required":
        _add_issue(issues, relative, verdict_field, "修订任务不能自行判定通过，必须重置为 recheck_required。", "修复正式目标后等待新的独立审查。")
    if not isinstance(payload.get("applied_repair_actions"), list) or not payload.get("applied_repair_actions"):
        _add_issue(issues, relative, "applied_repair_actions", "必须记录已落实的项目修复动作。", "逐项写明 target_path、修改内容和验证证据。")
    targets = [str(item) for item in task.payload.get("repair_targets") or [] if str(item).strip()]
    if not targets:
        _add_issue(issues, relative, "repair_targets", "修订任务没有可写的精确目标。", "让上一轮审查为每个行动项补充合法 target_path 后重新领取任务。")
    changed = _validate_revision_targets(task, sandbox, targets, relative, issues)
    if targets and not changed:
        _add_issue(issues, relative, "repair_targets", "没有任何声明的项目目标发生实质变化。", "落实至少一项真实修复；修改审查标签不能代替项目修改。")


def _validate_revision_targets(
    task: TaskPackage,
    sandbox: SandboxManifest,
    targets: list[str],
    relative: str,
    issues: list[PreflightIssue],
) -> bool:
    before = task.payload.get("repair_target_sha256_before_revision")
    hashes = before if isinstance(before, dict) else {}
    changed = False
    for target in targets:
        target_path = sandbox.workspace / Path(target)
        if not target_path.is_file():
            _add_issue(issues, relative, "repair_targets", f"修复目标 `{target}` 未生成。", "创建或修改该精确目标文件，不能只改审查报告。")
            continue
        previous = str(hashes.get(target) or "")
        current = hashlib.sha256(target_path.read_bytes()).hexdigest()
        if not previous or current != previous:
            changed = True
    return changed


def _validate_initial(
    payload: dict[str, object],
    relative: str,
    committee: bool,
    issues: list[PreflightIssue],
) -> None:
    verdict_field = "final_recommendation" if committee else "conclusion"
    verdict = str(payload.get(verdict_field) or "").strip().lower()
    allowed = {"approve", "approve_with_notes", "revise", "reject"} if committee else {"pass", "pass_with_notes", "revise_required", "reject"}
    if verdict not in allowed:
        _add_issue(issues, relative, verdict_field, f"审查结论必须是 {sorted(allowed)} 之一。", "如实记录结论；非通过结论本身可以完成本轮审查。")
        return
    if (committee and verdict == "approve") or (not committee and verdict == "pass"):
        return
    action_fields = ("action_items", "disagreements") if committee else ("recommendations",)
    actionable = _actionable_items(payload, action_fields)
    if not actionable:
        _add_issue(issues, relative, action_fields[0], "非通过结论必须提供至少一个结构化修复动作。", "为修复动作写出 target_path、action 和 verification。")
        return
    _validate_action_targets(actionable, action_fields[0], relative, issues)


def _actionable_items(payload: dict[str, object], fields: tuple[str, ...]) -> list[dict[str, object]]:
    actionable: list[dict[str, object]] = []
    for field in fields:
        values = payload.get(field) if isinstance(payload.get(field), list) else []
        actionable.extend(item for item in values if isinstance(item, dict))
    return actionable


def _validate_action_targets(
    actionable: list[dict[str, object]],
    field: str,
    relative: str,
    issues: list[PreflightIssue],
) -> None:
    allowed_prefixes = ("canon/", "characters/", "plot/", "scenes/", "drafts/candidates/")
    for index, item in enumerate(actionable):
        target = str(item.get("target_path") or item.get("target") or "").replace("\\", "/").strip()
        target_file = target.split("#", 1)[0]
        valid = (
            target_file.startswith(allowed_prefixes)
            and not Path(target_file).is_absolute()
            and ".." not in Path(target_file).parts
            and Path(target_file).suffix.lower() in {".md", ".json", ".yaml", ".yml", ".csv"}
        )
        if not valid:
            _add_issue(
                issues,
                relative,
                f"{field}[{index}].target_path",
                f"修复目标 `{target or 'missing'}` 不是允许的精确项目文件。",
                "使用 canon/、characters/、plot/、scenes/ 或 drafts/candidates/ 下的单个文本文件路径；不能写目录或 review/workflow 路径。",
            )
