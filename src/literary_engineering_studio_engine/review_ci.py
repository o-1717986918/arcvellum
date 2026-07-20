from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re

from .anti_ai_style import lint_ai_style
from .punctuation_standard import lint_punctuation
from .scene_draft import extract_draft_body


@dataclass(frozen=True)
class ReviewIssue:
    gate: str
    severity: str
    message: str


@dataclass(frozen=True)
class ReviewResult:
    project_root: Path
    draft_path: Path
    report_path: Path
    conclusion: str
    issue_count: int


REQUIRED_SECTIONS = [
    "## 正文草稿",
    "## 状态变化",
    "### 新增事实候选",
    "### 人物状态变化",
    "### 伏笔变化",
    "### 需要人工确认",
]

CLICHE_PATTERNS = [
    "他冷笑一声",
    "女人你成功引起了我的注意",
    "全场震惊",
    "打脸",
    "龙王",
    "逆袭",
]


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _has_nonempty_bullet(text: str, heading: str) -> bool:
    idx = text.find(heading)
    if idx < 0:
        return False
    next_idx = text.find("\n### ", idx + 1)
    if next_idx < 0:
        next_idx = text.find("\n## ", idx + 1)
    section = text[idx: next_idx if next_idx >= 0 else len(text)]
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("-") and stripped.strip("- ").strip():
            return True
    return False


def review_scene_draft(project_root: Path, draft: Path, output: Path | None = None) -> ReviewResult:
    root = project_root.resolve()
    draft_path = draft if draft.is_absolute() else root / draft
    if not draft_path.exists():
        raise FileNotFoundError(f"draft not found: {draft_path}")

    text = _read(draft_path)
    body = extract_draft_body(text)
    issues: list[ReviewIssue] = []

    for section in REQUIRED_SECTIONS:
        if section not in text:
            issues.append(ReviewIssue("Structure Test", "high", f"缺少区块：{section}"))

    if len(body) < 120:
        issues.append(ReviewIssue("Draft Completeness Test", "high", "正文草稿少于 120 字，无法进行有效审查。"))

    if "Canon、人物档案和时间线是硬约束" not in text and "硬 canon" not in text:
        issues.append(ReviewIssue("Canon Test", "medium", "草稿工作台缺少明确 canon 约束提示。"))

    if not _has_nonempty_bullet(text, "### 新增事实候选"):
        issues.append(ReviewIssue("Writeback Test", "medium", "新增事实候选为空，写回链路不可审计。"))

    if not _has_nonempty_bullet(text, "### 人物状态变化"):
        issues.append(ReviewIssue("Character Test", "medium", "人物状态变化为空，难以验证人物弧。"))

    if not _has_nonempty_bullet(text, "### 伏笔变化"):
        issues.append(ReviewIssue("Foreshadow Test", "low", "伏笔变化为空；如果本场景无伏笔，应显式写“无”。"))

    cliche_hits = [pattern for pattern in CLICHE_PATTERNS if pattern in text]
    if cliche_hits:
        issues.append(ReviewIssue("Anti-Cliche Test", "medium", "发现套路化表达：" + "、".join(cliche_hits)))

    if "style-profile" not in text and "风格" not in text:
        issues.append(ReviewIssue("Style Test", "low", "未发现风格约束引用。"))

    for punctuation_issue in lint_punctuation(body):
        message = f"{punctuation_issue.message}（rule: {punctuation_issue.rule}）"
        if punctuation_issue.sample:
            message += f" 示例：{punctuation_issue.sample}"
        issues.append(ReviewIssue("Punctuation Standard Test", punctuation_issue.severity, message))

    for ai_issue in lint_ai_style(body):
        message = ai_issue.message
        if ai_issue.sample:
            message += f" 示例：{ai_issue.sample}"
        issues.append(ReviewIssue("AI Trace Reduction Test", ai_issue.severity, message))

    high_count = sum(1 for issue in issues if issue.severity == "high")
    medium_count = sum(1 for issue in issues if issue.severity == "medium")
    if high_count:
        conclusion = "reject"
    elif medium_count:
        conclusion = "revise_required"
    elif issues:
        conclusion = "pass_with_notes"
    else:
        conclusion = "pass"

    report_path = output if output and output.is_absolute() else (
        root / output if output else root / "reviews" / f"{draft_path.stem}-review.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_review_report(draft_path, conclusion, issues, root), encoding="utf-8")

    return ReviewResult(
        project_root=root,
        draft_path=draft_path,
        report_path=report_path,
        conclusion=conclusion,
        issue_count=len(issues),
    )


def _issue_lines(issues: list[ReviewIssue], gate: str) -> str:
    selected = [issue for issue in issues if issue.gate == gate]
    if not selected:
        return "- 结果：pass\n- 问题：无\n- 建议：无"
    lines = ["- 结果：failed"]
    lines.append("- 问题：")
    for issue in selected:
        lines.append(f"  - [{issue.severity}] {issue.message}")
    lines.append("- 建议：按问题逐项修订后重新审查。")
    return "\n".join(lines)


def _review_report(draft_path: Path, conclusion: str, issues: list[ReviewIssue], root: Path) -> str:
    rel = draft_path.relative_to(root).as_posix() if draft_path.is_relative_to(root) else str(draft_path)
    gates = [
        "Canon Test",
        "Timeline Test",
        "Character Test",
        "Plot Test",
        "Foreshadow Test",
        "Style Test",
        "Punctuation Standard Test",
        "AI Trace Reduction Test",
        "Anti-Cliche Test",
        "Originality Test",
        "Structure Test",
        "Draft Completeness Test",
        "Writeback Test",
    ]
    sections = []
    for gate in gates:
        sections.append(f"## {gate}\n\n{_issue_lines(issues, gate)}")
    issue_summary = "\n".join(f"- [{i.severity}] {i.gate}: {i.message}" for i in issues) or "- 无"
    return f"""# 场景审查报告

## 基本信息

- 审查对象：`{rel}`
- 审查时间：{datetime.now(timezone.utc).isoformat()}
- 审查阶段：single_scene_draft
- 结论：{conclusion}

## 问题摘要

{issue_summary}

{chr(10).join(sections)}

## 写回建议

- 新 canon 候选：参考草稿中的“新增事实候选”。
- 人物状态变化：参考草稿中的“人物状态变化”。
- 伏笔变化：参考草稿中的“伏笔变化”。
- 需要人工确认：审查结论为 `pass` 后可进入下一门禁；若为 `pass_with_notes`，必须先处理 low 级 notes，或由平台 agent/用户逐条记录接受理由后再写回。
"""
