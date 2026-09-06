"""Style prompt contracts enforced before formal project writeback."""

from __future__ import annotations

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest
from .common import PreflightIssue
from literary_engineering_studio_engine.public.literary import (
    style_prompt_quality_report,
)


_STYLE_PROMPT_WRITE_STATES = {
    "style-prompt-agent-task",
    "style-prompt-quality",
    "style-eval-revision",
    "style-review-revision",
}


def validate_style_prompt_contract(
    task: TaskPackage,
    sandbox: SandboxManifest,
    issues: list[PreflightIssue],
) -> None:
    """Keep invalid prompt revisions inside the Worker repair loop."""

    state = str(task.current_state or task.payload.get("current_state") or "")
    if task.route != "style-engineering" or state not in _STYLE_PROMPT_WRITE_STATES:
        return
    relative = next(
        (item for item in task.expected_outputs if item.endswith("/style_prompt.md")),
        "",
    )
    if not relative:
        return
    path = sandbox.workspace / relative
    if not path.is_file():
        return
    report = style_prompt_quality_report(
        path.read_text(encoding="utf-8", errors="replace")
    )
    issues.extend(_style_prompt_issues(relative, report))


def _style_prompt_issues(relative: str, report: dict[str, object]) -> list[PreflightIssue]:
    detail_chars = int(report.get("detail_chars") or 0)
    length_range = report.get("length_range") or [500, 2500]
    minimum, maximum = int(length_range[0]), int(length_range[1])
    issues: list[PreflightIssue] = []
    if not report.get("length_ok"):
        issues.append(
            PreflightIssue(
                "style-prompt-length",
                relative,
                (
                    "文风提示词正文必须在 "
                    f"{minimum}-{maximum} 个中文内容字符内，当前为 {detail_chars}。"
                ),
                (
                    f"只修订 `{relative}`；将正文控制到 {minimum}-{maximum} 个中文内容字符，"
                    "优先压缩重复解释、近义规则和空泛说明，保留每项可执行约束、例外边界与自检。"
                    "不得机械截断句子，也不得删除必备文风模块。"
                ),
            )
        )
    missing = [str(item) for item in report.get("missing_blocks") or [] if str(item)]
    if missing:
        issues.append(
            PreflightIssue(
                "style-prompt-structure",
                relative,
                "文风提示词缺少必备模块：" + "、".join(missing),
                (
                    f"在 `{relative}` 中补齐上述模块，并把规则写成可执行的生成约束；"
                    f"修订后仍须满足 {minimum}-{maximum} 个中文内容字符的长度合同。"
                ),
            )
        )
    return issues


__all__ = ["validate_style_prompt_contract"]
