"""Candidate asset review and revision contracts."""

from __future__ import annotations

import json
from pathlib import Path

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .asset_evidence import review_digest_issues
from .common import PreflightIssue


def validate_asset_review_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    task_type = str(task.payload.get("task_type") or "")
    if task_type not in {"platform-agent-asset-review", "platform-agent-revision"}:
        return
    review_rel = _review_relative_path(task)
    payload = _read_review(sandbox, review_rel)
    if payload is None:
        return
    _validate_review_header(task, sandbox, payload, review_rel, issues)
    if task.current_state in {"asset-review-pass", "asset-approval-revision"}:
        _validate_revision_review(payload, review_rel, issues)
        return
    _validate_initial_review(task, payload, review_rel, issues)


def _review_relative_path(task: TaskPackage) -> str:
    return next(
        (
            relative
            for relative in task.expected_outputs
            if relative.replace("\\", "/").startswith("reviews/assets/")
            and relative.endswith("_review.json")
        ),
        "",
    )


def _read_review(sandbox: SandboxManifest, relative: str) -> dict[str, object] | None:
    if not relative:
        return None
    path = sandbox.workspace / Path(relative)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _add_issue(
    issues: list[PreflightIssue],
    review_rel: str,
    field: str,
    message: str,
    repair: str,
) -> None:
    issues.append(PreflightIssue("asset-review-invalid", f"{review_rel}#{field}", message, repair))


def _validate_review_header(
    task: TaskPackage,
    sandbox: SandboxManifest,
    payload: dict[str, object],
    review_rel: str,
    issues: list[PreflightIssue],
) -> None:
    expected_schema = "literary-engineering-workbench/candidate-asset-review/v0.1"
    if payload.get("schema") != expected_schema:
        _add_issue(issues, review_rel, "schema", f"schema 必须精确为 `{expected_schema}`。", "改正 schema 固定值，不要自造版本。")
    for field in ("candidate", "candidate_id", "asset_type"):
        if not isinstance(payload.get(field), str) or not str(payload.get(field) or "").strip():
            _add_issue(issues, review_rel, field, f"字段 `{field}` 必须是非空字符串。", f"从任务包与候选文件中填写精确的 `{field}`。")
    issues.extend(review_digest_issues(task, sandbox, payload, review_rel))
    for field in ("blocking_issues", "warnings", "revision_actions", "promotion_risks"):
        if not isinstance(payload.get(field), list):
            _add_issue(issues, review_rel, field, f"字段 `{field}` 必须是数组。", f"将 `{field}` 写为数组；没有内容时使用 []。")


def _validate_revision_review(
    payload: dict[str, object],
    review_rel: str,
    issues: list[PreflightIssue],
) -> None:
    status = str(payload.get("status") or "").strip().lower()
    if status != "recheck_required":
        _add_issue(
            issues,
            review_rel,
            "status",
            "修订任务不得自行把旧审查改成 pass；status 必须是 recheck_required。",
            "把 status 改为 recheck_required，并让下一轮独立审查重新裁决。",
        )
    applied = payload.get("applied_revision_actions")
    if not isinstance(applied, list) or not applied:
        _add_issue(
            issues,
            review_rel,
            "applied_revision_actions",
            "必须逐项记录已经落实的修订动作。",
            "把原 review 的每条阻塞项和 revision_action 对应到具体修改证据。",
        )
    revision_round = payload.get("revision_round")
    if not isinstance(revision_round, int) or isinstance(revision_round, bool) or revision_round < 1:
        _add_issue(issues, review_rel, "revision_round", "revision_round 必须是 >= 1 的整数。", "记录当前正式修订轮次。")


def _validate_initial_review(
    task: TaskPackage,
    payload: dict[str, object],
    review_rel: str,
    issues: list[PreflightIssue],
) -> None:
    status = str(payload.get("status") or "").strip().lower()
    allowed = {"pass", "failed", "revise_required"}
    if status not in allowed:
        _add_issue(issues, review_rel, "status", f"审查 status 必须是 {sorted(allowed)} 之一。", "按真实审查结论选择状态，不要伪造 pass。")
        return
    blocking = payload.get("blocking_issues") if isinstance(payload.get("blocking_issues"), list) else []
    revisions = payload.get("revision_actions") if isinstance(payload.get("revision_actions"), list) else []
    candidate = str(payload.get("candidate") or task.payload.get("candidate") or "").replace("\\", "/").strip()
    _validate_revision_targets(revisions, candidate, review_rel, issues)
    if status == "pass" and (blocking or revisions):
        _add_issue(issues, review_rel, "status", "pass 不能同时保留 blocking_issues 或 revision_actions。", "保留问题并改为 revise_required，或真实解决后由新一轮审查裁决。")
    if status in {"failed", "revise_required"} and not blocking and not revisions:
        _add_issue(issues, review_rel, "revision_actions", "非通过结论必须给出至少一条可执行问题或修订动作。", "写出具体、可验证、可复审的修改要求。")


def _validate_revision_targets(
    revisions: list[object],
    candidate: str,
    review_rel: str,
    issues: list[PreflightIssue],
) -> None:
    for index, action in enumerate(revisions):
        if not isinstance(action, dict):
            _add_issue(issues, review_rel, f"revision_actions[{index}]", "修订动作必须是对象。", "写出 target、action/description 和可验证条件。")
            continue
        target = str(action.get("target") or candidate).replace("\\", "/").strip()
        target_file = target.split("#", 1)[0]
        if candidate and target_file != candidate:
            _add_issue(
                issues,
                review_rel,
                f"revision_actions[{index}].target",
                f"资产审查不得用跨任务目标 `{target}` 阻塞当前候选 `{candidate}`。",
                "把跨任务依赖移入 warnings 或 promotion_risks；revision_actions 只保留能在当前候选文件内完成的修改。",
            )
