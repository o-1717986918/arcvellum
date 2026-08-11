"""Shared DTOs and generic deterministic checks for worker preflight."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest


COMPLETION_SCHEMA = "literary-engineering-workbench/agent-task-completion/v1"
REVIEW_CONCLUSION = re.compile(
    r"(?m)^-\s*(?:\u5ba1\u67e5)?\u7ed3\u8bba\uff1a\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$",
    re.IGNORECASE,
)
REVIEW_CONCLUSION_VARIANT = re.compile(
    r"(?mi)^(?:#{1,6}\s*)?-?\s*(?:\u5ba1\u67e5)?\u7ed3\u8bba[\uff1a:]\s*(?:\*\*)?`?"
    r"(pass|revise_required|reject)`?(?:\*\*)?\s*$"
)


@dataclass(frozen=True)
class PreflightIssue:
    code: str
    path: str
    message: str
    repair: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class PreflightResult:
    passed: bool
    issues: tuple[PreflightIssue, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "issue_count": len(self.issues), "issues": [item.as_dict() for item in self.issues]}

    def repair_prompt(self, attempt: int, maximum: int) -> str:
        rows = "\n".join(
            f"{index}. [{item.code}] `{item.path}`：{item.message}\n   修复要求：{item.repair}"
            for index, item in enumerate(self.issues, start=1)
        )
        return f"""# Studio Preflight Repair {attempt}/{maximum}

你刚完成的沙箱产物未通过确定性预检。只修复下列明确问题，不改变已经成立的创作判断，也不要为了显示 pass 而伪造审查结论。

{rows}

仍然只能修改 Allowed Outputs。修复后逐项重新读取目标文件并核对精确格式，然后结束；Studio 会再次运行预检。
"""


def _validate_json(relative: str, path: Path, issues: list[PreflightIssue]) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        issues.append(PreflightIssue("invalid-json", relative, f"JSON 无法解析：{exc}", "修正 JSON 语法；不要使用 Markdown 代码围栏。"))
        return
    if not isinstance(payload, (dict, list)):
        issues.append(PreflightIssue("invalid-json-root", relative, "JSON 根节点必须是对象或数组。", "按任务合同改为结构化 JSON。"))


def _validate_completion_markers(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    for relative in task.expected_outputs:
        if not relative.endswith(".agent_completion.json"):
            continue
        path = sandbox.workspace / Path(relative)
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        completion_base = relative[: -len(".agent_completion.json")]
        expected_task = completion_base + (".md" if completion_base.endswith(".agent_tasks") else ".agent_tasks.md")
        errors: list[str] = []
        revision_reset = task.current_state in {"asset-review-pass", "asset-approval-revision", "canon-review-pass", "committee-pass"}
        if not isinstance(payload, dict):
            errors.append("根节点不是对象")
        else:
            if payload.get("schema") != COMPLETION_SCHEMA:
                errors.append(f"schema 必须是 {COMPLETION_SCHEMA}")
            status = str(payload.get("status") or "").lower()
            if revision_reset:
                if status != "recheck_required":
                    errors.append("资产修订后的审查完成标记 status 必须为 recheck_required")
                if payload.get("expected_artifacts_checked") is not False:
                    errors.append("资产修订后的 expected_artifacts_checked 必须为 false，等待独立复审")
            else:
                if status not in {"complete", "completed", "done", "handled", "pass"}:
                    errors.append("status 必须表示 complete")
                if payload.get("expected_artifacts_checked") is not True:
                    errors.append("expected_artifacts_checked 必须为 true")
            if str(payload.get("source_task") or "").replace("\\", "/") != expected_task:
                errors.append(f"source_task 必须精确为 {expected_task}")
        if errors:
            issues.append(
                PreflightIssue(
                    "invalid-completion-evidence",
                    relative,
                    "；".join(errors),
                    (
                        "将旧审查完成证据重置为 recheck_required，并保持 expected_artifacts_checked=false，等待新的独立审查。"
                        if revision_reset
                        else "按完成标记 schema 修复字段；确认其他产物后再保留 complete 状态。"
                    ),
                )
            )


def _validate_review_conclusions(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    gates = " ".join(str(item) for item in task.payload.get("validation_gates") or []).lower()
    if (
        "conclusion is pass" not in gates
        and "conclusion is recorded" not in gates
        and "结论" not in gates
    ):
        return
    candidates = [
        relative
        for relative in task.expected_outputs
        if relative.endswith(".md") and "review" in relative.lower() and "agent_tasks" not in relative.lower()
    ]
    for relative in candidates:
        path = sandbox.workspace / Path(relative)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        match = REVIEW_CONCLUSION.search(text)
        if not match:
            issues.append(
                PreflightIssue(
                    "missing-machine-conclusion",
                    relative,
                    "没有找到以 `- 结论：` 开头的独占机器行；标题或普通段落不能替代。",
                    "在报告中加入独占一行，例如 `- 结论： pass`、`- 结论： revise_required` 或 `- 结论： reject`。",
                )
            )
        elif "conclusion is pass" in gates and match.group(1).lower() != "pass":
            issues.append(
                PreflightIssue(
                    "review-not-pass",
                    relative,
                    f"当前正式门禁要求 pass，报告结论为 {match.group(1)}。",
                    "批判性修订对应候选产物并重新审查；只有阻塞问题确实消失后才把机器行改为 pass。",
                )
            )
