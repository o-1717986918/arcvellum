"""Content-safe reports for rendered prompt baselines."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from ..runtime.prompt_metrics import measure_prompt


REPORT_SCHEMA = "arcvellum/prompt-audit-report/v1"


def build_prompt_audit_report(cases: Mapping[str, Path]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for case_id, path in sorted(cases.items()):
        text = path.read_text(encoding="utf-8")
        rows.append({"case_id": case_id, **measure_prompt(text).safe_projection()})
    return {
        "schema": REPORT_SCHEMA,
        "case_count": len(rows),
        "privacy": "content-free; no prompt text, prose, reasoning, credentials, or absolute paths",
        "cases": rows,
    }


def render_prompt_audit_markdown(report: Mapping[str, object]) -> str:
    rows = report.get("cases")
    cases = rows if isinstance(rows, list) else []
    lines = [
        "# Prompt Audit",
        "",
        f"- schema: `{report.get('schema', '')}`",
        f"- cases: {len(cases)}",
        "- privacy: content-free; prompt and literary text are not stored.",
        "",
        "| case | characters | estimated tokens | evidence | sources | duplicate ratio | constraint repeat | on demand |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in cases:
        if not isinstance(item, dict):
            continue
        lines.append(
            "| {case} | {characters} | {tokens} | {evidence} | {sources} | {duplicate:.1%} | {constraints:.1%} | {on_demand} |".format(
                case=item.get("case_id", "unknown"),
                characters=item.get("total_characters", 0),
                tokens=item.get("estimated_input_tokens", 0),
                evidence=item.get("evidence_characters", 0),
                sources=item.get("unique_source_count", 0),
                duplicate=float(item.get("duplicate_character_ratio", 0.0)),
                constraints=float(item.get("constraint_repetition_ratio", 0.0)),
                on_demand=item.get("exact_on_demand_count", 0),
            )
        )
    return "\n".join(lines) + "\n"
