"""User-facing comparison for two safe style-version detail projections."""

from __future__ import annotations

from typing import Any


def project_style_version_comparison(
    current: dict[str, object],
    target: dict[str, object],
) -> dict[str, object]:
    rows = [
        _row(
            "source_count",
            "来源证据",
            len(current.get("source_evidence", [])),
            len(target.get("source_evidence", [])),
        ),
        _row(
            "prompt_detail_chars",
            "约束汉字",
            _nested(current, "prompt_quality", "detail_chars"),
            _nested(target, "prompt_quality", "detail_chars"),
        ),
        _row(
            "overall_score",
            "隔离评测",
            _nested(current, "evaluation", "overall_score"),
            _nested(target, "evaluation", "overall_score"),
        ),
        _row(
            "risk_level",
            "泄漏风险",
            _nested(current, "evaluation", "risk_level"),
            _nested(target, "evaluation", "risk_level"),
        ),
        _row(
            "review_status",
            "独立审查",
            _nested(current, "review", "status"),
            _nested(target, "review", "status"),
        ),
        _row(
            "compiler_version",
            "编译器",
            current.get("compiler_version", ""),
            target.get("compiler_version", ""),
        ),
    ]
    return {
        "status": "initial-mount" if not current else "version-change",
        "changes": [row for row in rows if row["changed"]],
        "evidence": rows,
    }


def _row(
    field: str,
    label: str,
    before: object,
    after: object,
) -> dict[str, object]:
    return {
        "field": field,
        "label": label,
        "before": before if before not in (None, "") else "未建立",
        "after": after if after not in (None, "") else "未建立",
        "changed": before != after,
    }


def _nested(payload: dict[str, object], key: str, field: str) -> object:
    return _object(payload.get(key)).get(field, "")


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
