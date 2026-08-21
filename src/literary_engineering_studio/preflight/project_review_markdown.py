"""Render project-review Markdown machine verdicts from their JSON contract."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest


_MACHINE_LINE_VARIANT = re.compile(
    r"(?i)^\s*(?:#{1,6}\s*)?[-*]?\s*"
    r"(?:(?:审查)?结论|conclusion)\s*[：:]\s*"
    r"(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$"
)

_CONTRACTS = {
    "canon-review-agent-task": (
        "reviews/agent/canon_review.json",
        "reviews/agent/canon_review.md",
        "literary-engineering-workbench/canon-review-agent/v1",
        "conclusion",
        frozenset({"pass", "pass_with_notes", "revise_required", "reject"}),
    ),
    "committee-agent-task": (
        "reviews/agent/committee_project-final-audit.json",
        "reviews/agent/committee_project-final-audit.md",
        "literary-engineering-workbench/committee-review-agent/v1",
        "final_recommendation",
        frozenset({"approve", "approve_with_notes", "revise", "reject"}),
    ),
}


def canonicalize_project_review_markdown(
    task: TaskPackage,
    sandbox: SandboxManifest,
    *,
    read_object: Callable[[Path], dict[str, Any] | None],
) -> list[dict[str, str]]:
    """Make Markdown's machine line an exact projection of Agent-owned JSON.

    The function never infers a verdict.  It only projects a valid verdict from
    the matching project-review JSON contract, so malformed or absent semantic
    output continues to fail deterministic preflight.
    """

    contract = _CONTRACTS.get(str(task.current_state or ""))
    if contract is None:
        return []
    json_relative, markdown_relative, schema, verdict_field, allowed = contract
    if json_relative not in task.expected_outputs or markdown_relative not in task.expected_outputs:
        return []

    payload = read_object(sandbox.workspace / Path(json_relative))
    if payload is None or str(payload.get("schema") or "") != schema:
        return []
    verdict = str(payload.get(verdict_field) or "").strip().lower()
    if verdict not in allowed:
        return []

    markdown_path = sandbox.workspace / Path(markdown_relative)
    if not markdown_path.is_file():
        return []
    original = markdown_path.read_text(encoding="utf-8", errors="replace")
    normalized = _render_machine_line(original, verdict)
    if normalized == original:
        return []
    markdown_path.write_text(normalized, encoding="utf-8")
    return [
        {
            "path": markdown_relative,
            "field": "machine_conclusion",
            "verdict": verdict,
            "reason": "projected the Agent-owned JSON verdict into the Markdown machine line",
        }
    ]


def _render_machine_line(text: str, verdict: str) -> str:
    machine_line = f"- 结论： {verdict}"
    lines = text.splitlines()
    rendered: list[str] = []
    found = False
    for line in lines:
        if _MACHINE_LINE_VARIANT.fullmatch(line):
            if not found:
                rendered.append(machine_line)
                found = True
            continue
        rendered.append(line)

    if not found:
        heading_index = next(
            (index for index, line in enumerate(rendered) if line.lstrip().startswith("#")),
            None,
        )
        if heading_index is None:
            rendered = [machine_line, "", *rendered]
        else:
            insert_at = heading_index + 1
            while insert_at < len(rendered) and not rendered[insert_at].strip():
                insert_at += 1
            rendered[insert_at:insert_at] = [machine_line, ""]

    return "\n".join(rendered).rstrip() + "\n"


__all__ = ["canonicalize_project_review_markdown"]
