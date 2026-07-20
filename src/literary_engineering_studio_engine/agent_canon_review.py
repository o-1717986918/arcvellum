"""LLM/Agent-backed canon and continuity review."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .agent_provider import run_agent_task
from .agent_schema import validate_agent_run
from .canon_lint import build_canon_lint


@dataclass(frozen=True)
class AgentCanonReviewResult:
    project_root: Path
    run_dir: Path
    report_path: Path
    json_path: Path
    validation_path: Path
    conclusion: str


def review_canon_with_agent(
    project_root: Path,
    *,
    provider: str = "auto",
    output: Path | None = None,
    json_output: Path | None = None,
) -> AgentCanonReviewResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    lint = build_canon_lint(root)
    lint_payload = json.loads(lint.json_path.read_text(encoding="utf-8"))
    source_paths = [_rel_str(lint.report_path, root), _rel_str(lint.json_path, root), "canon/", "characters/", "scenes/", "plot/"]
    dry_payload = _dry_canon_review(lint_payload, source_paths)
    run_result = run_agent_task(
        root,
        agent_id="canon-reviewer",
        task="review-canon-continuity",
        system_prompt=_system_prompt(),
        user_prompt=_user_prompt(lint_payload, root),
        provider=provider,
        metadata={"schema_name": "canon_review.v1", "source_paths": source_paths},
        dry_run_output=dry_payload,
    )
    validation = validate_agent_run(root, run_dir=run_result.run_dir, schema_name="canon_review.v1")
    parsed = json.loads(run_result.parsed_output_path.read_text(encoding="utf-8"))
    parsed["agent_run_dir"] = _rel_str(run_result.run_dir, root)
    parsed["schema_validation"] = _rel_str(validation.validation_path, root)
    report_path = _resolve_output(root, output, "reviews", "agent", "canon_review.md")
    json_path = _resolve_output(root, json_output, "reviews", "agent", "canon_review.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_report(parsed, validation.status), encoding="utf-8")
    return AgentCanonReviewResult(
        project_root=root,
        run_dir=run_result.run_dir,
        report_path=report_path,
        json_path=json_path,
        validation_path=validation.validation_path,
        conclusion=str(parsed.get("conclusion", "")),
    )


def _system_prompt() -> str:
    return """You are a canon and long-form continuity review agent.

Use the lint output and project state as evidence. Identify confirmed conflicts, unconfirmed facts, timeline risks, and follow-up actions. Output JSON only using schema canon_review.v1."""


def _user_prompt(lint_payload: dict[str, object], root: Path) -> str:
    outline = _read(root / "plot" / "outline.md")
    facts = _read(root / "canon" / "facts.json")
    return f"""## Canon Lint

```json
{json.dumps(lint_payload, ensure_ascii=False, indent=2)[:9000]}
```

## Canon Facts

```json
{facts[:5000]}
```

## Outline

```markdown
{outline[:5000]}
```
"""


def _dry_canon_review(lint_payload: dict[str, object], source_paths: list[str]) -> dict[str, object]:
    summary = lint_payload.get("summary", {}) if isinstance(lint_payload.get("summary"), dict) else {}
    blocking = int(summary.get("blocking_count", 0) or 0)
    warnings = int(summary.get("warning_count", 0) or 0)
    conclusion = "revise_required" if blocking else "pass_with_notes" if warnings else "pass"
    issues = lint_payload.get("issues", []) if isinstance(lint_payload.get("issues"), list) else []
    blocking_issues = [item for item in issues if isinstance(item, dict) and item.get("severity") == "blocking"]
    warning_issues = [item for item in issues if isinstance(item, dict) and item.get("severity") == "warning"]
    return {
        "schema": "literary-engineering-workbench/canon-review-agent/v1",
        "conclusion": conclusion,
        "summary": f"dry-run canon reviewer summarized canon-lint: blocking={blocking}, warning={warnings}.",
        "blocking_issues": blocking_issues,
        "warnings": warning_issues,
        "unresolved_facts": [],
        "timeline_risks": [],
        "source_paths": source_paths,
        "recommendations": ["先解决 blocking，再允许发布或正稿合并。", "候选事实必须保留人工确认点。"],
        "next_gate": "schema_validation_then_human_review",
    }


def _render_report(payload: dict[str, object], validation_status: str) -> str:
    lines = [
        "# Agent Canon / Continuity Review",
        "",
        f"- 结论：`{payload.get('conclusion', '')}`",
        f"- Schema：`{validation_status}`",
        f"- Agent Run：`{payload.get('agent_run_dir', '')}`",
        "",
        "## 摘要",
        "",
        str(payload.get("summary", "")),
        "",
        "## 建议",
        "",
    ]
    for item in payload.get("recommendations", []) or []:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _resolve_output(root: Path, value: Path | None, *default_parts: str) -> Path:
    if value is None:
        return root.joinpath(*default_parts)
    return value if value.is_absolute() else root / value


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
