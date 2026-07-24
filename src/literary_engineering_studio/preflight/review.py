"""Project-wide review and declared-repair preflight gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..contracts import TaskPackage
from .common import PreflightIssue
from ..sandbox import SandboxManifest


def _validate_project_review_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    state = task.current_state
    if state not in {"canon-review-agent-task", "canon-review-pass", "committee-agent-task", "committee-pass"}:
        return
    committee = state.startswith("committee")
    relative = (
        "reviews/agent/committee_project-final-audit.json"
        if committee
        else "reviews/agent/canon_review.json"
    )
    path = sandbox.workspace / relative
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(payload, dict):
        return

    def add(field: str, message: str, repair: str) -> None:
        issues.append(PreflightIssue("project-review-invalid", f"{relative}#{field}", message, repair))

    if state in {"canon-review-pass", "committee-pass"}:
        verdict_field = "final_recommendation" if committee else "conclusion"
        if str(payload.get(verdict_field) or "").strip().lower() != "recheck_required":
            add(verdict_field, "修订任务不能自行判定通过，必须重置为 recheck_required。", "修复正式目标后等待新的独立审查。")
        if not isinstance(payload.get("applied_repair_actions"), list) or not payload.get("applied_repair_actions"):
            add("applied_repair_actions", "必须记录已落实的项目修复动作。", "逐项写明 target_path、修改内容和验证证据。")
        targets = [str(item) for item in task.payload.get("repair_targets") or [] if str(item).strip()]
        if not targets:
            add("repair_targets", "修订任务没有可写的精确目标。", "让上一轮审查为每个行动项补充合法 target_path 后重新领取任务。")
        before = task.payload.get("repair_target_sha256_before_revision")
        hashes = before if isinstance(before, dict) else {}
        changed = False
        for target in targets:
            target_path = sandbox.workspace / Path(target)
            if not target_path.is_file():
                add("repair_targets", f"修复目标 `{target}` 未生成。", "创建或修改该精确目标文件，不能只改审查报告。")
                continue
            previous = str(hashes.get(target) or "")
            current = hashlib.sha256(target_path.read_bytes()).hexdigest()
            if not previous or current != previous:
                changed = True
        if targets and not changed:
            add("repair_targets", "没有任何声明的项目目标发生实质变化。", "落实至少一项真实修复；修改审查标签不能代替项目修改。")
        return

    verdict_field = "final_recommendation" if committee else "conclusion"
    verdict = str(payload.get(verdict_field) or "").strip().lower()
    allowed = {"approve", "approve_with_notes", "revise", "reject"} if committee else {"pass", "pass_with_notes", "revise_required", "reject"}
    if verdict not in allowed:
        add(verdict_field, f"审查结论必须是 {sorted(allowed)} 之一。", "如实记录结论；非通过结论本身可以完成本轮审查。")
        return
    if (committee and verdict == "approve") or (not committee and verdict == "pass"):
        return
    action_fields = ("action_items", "disagreements") if committee else ("recommendations",)
    actionable: list[dict[str, object]] = []
    for field in action_fields:
        values = payload.get(field) if isinstance(payload.get(field), list) else []
        actionable.extend(item for item in values if isinstance(item, dict))
    if not actionable:
        add(action_fields[0], "非通过结论必须提供至少一个结构化修复动作。", "为修复动作写出 target_path、action 和 verification。")
        return
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
            add(
                f"{action_fields[0]}[{index}].target_path",
                f"修复目标 `{target or 'missing'}` 不是允许的精确项目文件。",
                "使用 canon/、characters/、plot/、scenes/ 或 drafts/candidates/ 下的单个文本文件路径；不能写目录或 review/workflow 路径。",
            )


def _validate_source_extraction_revision(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    supported = (
        task.route == "source-ingest" and task.current_state == "extraction-review"
    ) or (
        task.route == "longform-planning"
        and task.current_state in {"budget-review", "scene-inventory-review", "chapter-obligation-review"}
    ) or (
        task.route == "review-and-audit" and task.current_state == "canon-patch-revision"
    ) or (
        task.route == "style-engineering" and task.current_state == "style-eval-revision"
    )
    if not supported:
        return
    targets = [str(item) for item in task.payload.get("repair_targets") or [] if str(item).strip()]
    before = task.payload.get("repair_target_sha256_before_revision")
    hashes = before if isinstance(before, dict) else {}
    changed = False
    for target in targets:
        path = sandbox.workspace / Path(target)
        if not path.is_file():
            continue
        previous = str(hashes.get(target) or "")
        if previous and hashlib.sha256(path.read_bytes()).hexdigest() != previous:
            changed = True
            break
    if not targets or not changed:
        issues.append(
            PreflightIssue(
                "declared-repair-target-unchanged",
                "repair_targets",
                "返工没有修改任何声明的候选文件。",
                "按 review 修订至少一个候选文件；不能只把审查结论改成 pass。",
            )
        )
