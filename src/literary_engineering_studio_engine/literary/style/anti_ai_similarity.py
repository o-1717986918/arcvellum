"""Focused similarity-language finding used by the anti-AI style linter."""

from __future__ import annotations

import re

from literary_engineering_studio_engine.literary.review.creative_quality import quality_threshold


def simile_dependency_finding(text, profile, density_verdict):
    count = len(re.findall(r"(?:好像|仿佛|如同|像是|像[^。！？\n]{1,18}(?:一样|似的))", text))
    minimum = max(1, int(quality_threshold(profile, "simile_minimum_hits", 2)))
    if count < minimum:
        return None
    severity, density_note = density_verdict(
        count, text, profile, threshold_key="simile_per_100_units",
    )
    return (
        "simile-dependency",
        severity,
        "比喻依赖偏高。"
        f"此类表达按约 2% 密度门禁处理，{density_note}；朴素叙述优先使用准确事实和动作，不靠“好像/仿佛/像……一样”撑情绪。",
    )


__all__ = ["simile_dependency_finding"]
