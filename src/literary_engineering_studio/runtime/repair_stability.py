"""Cross-turn stability contracts for prose repair convergence."""

from __future__ import annotations

from ..contracts import TaskPackage


def regression_guard(
    task: TaskPackage,
    issue_codes: set[str],
) -> dict[str, object]:
    prose_codes = {
        "candidate-style-lint-blocking",
        "candidate-word-budget-invalid",
    }
    active = bool(prose_codes & issue_codes)
    payload = task.payload
    return {
        "active": active,
        "seen_issue_codes": sorted(issue_codes),
        "word_count_target": _safe_int(payload.get("word_count_target")),
        "word_count_min": _safe_int(payload.get("word_count_min")),
        "word_count_max": _safe_int(payload.get("word_count_max")),
        "style_rules": [
            "逗号按语义层级使用；修订逗号链时重组句法，不按数量机械拆句",
            "中等长度句承担主要叙述；连续短句只用于有意的压力、落点或转向",
            "不用破折号或生硬对照句式承接转折",
            "避免抽象总结词堆积，以动作、信息和选择承载新增篇幅",
        ] if active else [],
    }


def _safe_int(value: object) -> int:
    try:
        return int(str(value or 0).replace(",", "").replace("_", ""))
    except (TypeError, ValueError):
        return 0


__all__ = ["regression_guard"]
