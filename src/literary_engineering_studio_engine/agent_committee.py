"""Multi-agent review committee for literary engineering artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .agent_provider import run_agent_task
from .agent_schema import validate_agent_run


DEFAULT_REVIEWERS = (
    "chief-editor",
    "character-psychology",
    "canon-auditor",
    "style-auditor",
    "market-readability",
    "anti-homogeneity",
)


@dataclass(frozen=True)
class AgentCommitteeResult:
    project_root: Path
    committee_dir: Path
    report_path: Path
    json_path: Path
    validation_path: Path
    subject: str
    final_recommendation: str
    reviewer_count: int


def run_agent_committee(
    project_root: Path,
    *,
    subject: str,
    source: Path | None = None,
    provider: str = "auto",
    reviewers: tuple[str, ...] = DEFAULT_REVIEWERS,
    output: Path | None = None,
    json_output: Path | None = None,
) -> AgentCommitteeResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    source_path = _resolve_source(root, source)
    source_text = _read(source_path) if source_path else ""
    source_paths = [_rel_str(source_path, root)] if source_path else []
    committee_id = f"{_slug(subject)}-{_stamp()}"
    committee_dir = root / "agents" / "committee" / committee_id
    opinions = []
    for reviewer_id in reviewers:
        opinion = _run_reviewer(root, committee_dir, reviewer_id, subject, source_text, source_paths, provider)
        opinions.append(opinion)
    summary = _run_summary(root, committee_dir, subject, opinions, source_paths, provider)
    validation = validate_agent_run(root, run_dir=summary.run_dir, schema_name="committee_review.v1")
    parsed = json.loads(summary.parsed_output_path.read_text(encoding="utf-8"))
    parsed["committee_dir"] = _rel_str(committee_dir, root)
    parsed["schema_validation"] = _rel_str(validation.validation_path, root)
    report_path = _resolve_output(root, output, "reviews", "agent", f"committee_{_slug(subject)}.md")
    json_path = _resolve_output(root, json_output, "reviews", "agent", f"committee_{_slug(subject)}.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_report(parsed, len(opinions), validation.status), encoding="utf-8")
    return AgentCommitteeResult(
        project_root=root,
        committee_dir=committee_dir,
        report_path=report_path,
        json_path=json_path,
        validation_path=validation.validation_path,
        subject=subject,
        final_recommendation=str(parsed.get("final_recommendation", "")),
        reviewer_count=len(opinions),
    )


def _run_reviewer(root: Path, committee_dir: Path, reviewer_id: str, subject: str, source_text: str, source_paths: list[str], provider: str) -> dict[str, object]:
    dry_payload = {
        "schema": "literary-engineering-workbench/reviewer-opinion-agent/v1",
        "reviewer_id": reviewer_id,
        "stance": "approve_with_notes",
        "findings": [f"{reviewer_id} dry-run opinion preserved independent review evidence."],
        "recommendations": ["Keep schema validation and human decision as final gates."],
        "source_paths": source_paths,
    }
    result = run_agent_task(
        root,
        agent_id=reviewer_id,
        task=f"committee-opinion:{subject}",
        system_prompt=f"You are the {reviewer_id} reviewer in a literary engineering committee. Output reviewer_opinion.v1 JSON only.",
        user_prompt=f"Subject: {subject}\n\nSource:\n```text\n{source_text[:8000] or 'No source text provided.'}\n```",
        provider=provider,
        output_dir=committee_dir / reviewer_id,
        metadata={"schema_name": "reviewer_opinion.v1", "subject": subject},
        dry_run_output=dry_payload,
    )
    validate_agent_run(root, run_dir=result.run_dir, schema_name="reviewer_opinion.v1")
    opinion = json.loads(result.parsed_output_path.read_text(encoding="utf-8"))
    opinion["agent_run_dir"] = _rel_str(result.run_dir, root)
    return opinion


def _run_summary(root: Path, committee_dir: Path, subject: str, opinions: list[dict[str, object]], source_paths: list[str], provider: str):
    dry_payload = {
        "schema": "literary-engineering-workbench/committee-review-agent/v1",
        "subject": subject,
        "final_recommendation": "approve_with_notes",
        "reviewers": opinions,
        "disagreements": [],
        "action_items": ["Review minority opinions before promotion or publication.", "Keep canon and character writebacks behind approval."],
        "source_paths": source_paths,
        "minority_opinions": [],
    }
    return run_agent_task(
        root,
        agent_id="committee-summarizer",
        task=f"committee-summary:{subject}",
        system_prompt="You summarize independent reviewer opinions into committee_review.v1 JSON. Preserve disagreements and minority opinions.",
        user_prompt="Reviewer opinions:\n```json\n" + json.dumps(opinions, ensure_ascii=False, indent=2)[:12000] + "\n```",
        provider=provider,
        output_dir=committee_dir / "summary",
        metadata={"schema_name": "committee_review.v1", "subject": subject},
        dry_run_output=dry_payload,
    )


def _render_report(payload: dict[str, object], reviewer_count: int, validation_status: str) -> str:
    lines = [
        f"# Agent 审稿委员会：{payload.get('subject', '')}",
        "",
        f"- Final Recommendation：`{payload.get('final_recommendation', '')}`",
        f"- Reviewers：{reviewer_count}",
        f"- Schema：`{validation_status}`",
        f"- Committee Dir：`{payload.get('committee_dir', '')}`",
        "",
        "## Action Items",
        "",
    ]
    for item in payload.get("action_items", []) or []:
        lines.append(f"- {item}")
    if payload.get("disagreements"):
        lines.extend(["", "## Disagreements", ""])
        for item in payload.get("disagreements", []) or []:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _resolve_source(root: Path, source: Path | None) -> Path | None:
    if source is None:
        return None
    path = source if source.is_absolute() else root / source
    if not path.exists():
        raise FileNotFoundError(f"source not found: {path}")
    return path.resolve()


def _resolve_output(root: Path, value: Path | None, *default_parts: str) -> Path:
    if value is None:
        return root.joinpath(*default_parts)
    return value if value.is_absolute() else root / value


def _read(path: Path | None) -> str:
    return path.read_text(encoding="utf-8") if path and path.exists() else ""


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")[:80] or "committee"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _rel_str(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
