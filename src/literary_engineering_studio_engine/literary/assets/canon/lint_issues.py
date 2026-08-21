"""Machine-readable Canon lint findings and report rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CanonLintIssue:
    check_id: str
    severity: str
    location: str
    message: str
    evidence: str = ""
    allowed_values: tuple[str, ...] = ()
    repair_hint: str = ""


def add_issue(
    issues: list[CanonLintIssue],
    check_id: str,
    severity: str,
    location: str,
    message: str,
    evidence: str = "",
    *,
    allowed_values: tuple[str, ...] = (),
    repair_hint: str = "",
) -> None:
    issues.append(
        CanonLintIssue(
            check_id=check_id,
            severity=severity,
            location=location,
            message=message,
            evidence=evidence,
            allowed_values=allowed_values,
            repair_hint=repair_hint,
        )
    )


def render_report(root: Path, payload: dict[str, object]) -> str:
    summary = payload["summary"]
    lines = [
        "# Canon Lint Report", "", f"- 项目：`{root}`", f"- 生成时间：{payload['generated_at']}",
        f"- 状态：`{payload['status']}`", f"- 问题总数：{summary['issue_count']}",
        f"- Blocking：{summary['blocking_count']}", f"- Warning：{summary['warning_count']}",
        f"- Info：{summary['info_count']}", "", "## Issues", "",
    ]
    issues = payload["issues"]
    if not issues:
        lines.append("- 未发现问题。")
        return "\n".join(lines) + "\n"
    lines.extend(["| Severity | Check | Location | Message | Evidence | Repair contract |", "| --- | --- | --- | --- | --- | --- |"])
    for issue in issues:
        lines.append(
            "| {severity} | `{check}` | `{location}` | {message} | {evidence} | {repair} |".format(
                severity=issue["severity"], check=issue["check_id"], location=issue["location"],
                message=issue["message"], evidence=str(issue.get("evidence", "")).replace("|", "\\|"),
                repair=_repair_contract_text(issue).replace("|", "\\|"),
            )
        )
    lines.extend([
        "", "## 使用边界", "", "- 本报告只检查项目状态，不自动修改 canon。",
        "- Blocking 应在正式导出或发布前解决。", "- Warning 可进入人工审查队列，但不能被忽略。",
        "- Info 用于提醒仍需维护的工程事实。",
    ])
    return "\n".join(lines) + "\n"


def _repair_contract_text(issue: dict[str, object]) -> str:
    allowed = issue.get("allowed_values") if isinstance(issue.get("allowed_values"), (list, tuple)) else []
    hint = str(issue.get("repair_hint") or "")
    values = f"allowed={','.join(str(item) for item in allowed)}" if allowed else ""
    return "; ".join(item for item in (values, hint) if item) or "-"


__all__ = ["CanonLintIssue", "add_issue", "render_report"]
