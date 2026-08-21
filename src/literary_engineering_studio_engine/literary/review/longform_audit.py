"""Long-form audit application service and stable public entry."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from ...word_budget import load_word_budget_summary
from ..planning.chapter_inventory import formal_chapter_files
from .longform_analysis import collect_expanded_evidence, extended_summary
from .longform_contract import LONGFORM_AUDIT_SCHEMA, longform_input_snapshot
from .longform_graph import build_graph
from .longform_inventory import (
    existing_rel,
    list_after,
    outgoing_hook_text,
    read_text,
    rel_str,
    review_conclusion,
    scalar,
    scan_characters,
    scan_foreshadowing,
    scan_scenes,
    string_list,
)
from .longform_issue_analysis import (
    RESOLVED_FORESHADOW_STATUSES,
    audit_issues,
    foreshadow_status,
    rhythm_curve_issues,
    to_int,
)
from .longform_models import LongformAuditResult, LongformIssue, LongformSceneRecord
from .longform_rendering import build_summary, render_markdown


def build_longform_audit(
    project_root: Path,
    target_length: int = 0,
    output: Path | None = None,
    json_output: Path | None = None,
    graph_output: Path | None = None,
) -> LongformAuditResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    scenes = scan_scenes(root)
    characters = scan_characters(root)
    foreshadowing = scan_foreshadowing(root)
    chapter_files = _chapter_files(root)
    word_budget = load_word_budget_summary(root, live=True)
    resolved_target_length = _resolved_target_length(root, target_length, word_budget)
    rhythm_plan, rhythm_curves, continuity, expanded = collect_expanded_evidence(root, scenes)
    issues = audit_issues(root, scenes, characters, foreshadowing, chapter_files, resolved_target_length, word_budget)
    issues.extend(rhythm_curve_issues(rhythm_curves))
    issues.extend(LongformIssue(**item) for item in expanded)
    paths = _output_paths(root, output, json_output, graph_output)
    summary = build_summary(scenes, characters, foreshadowing, chapter_files, issues, resolved_target_length, word_budget)
    summary.update(extended_summary(scenes, issues, rhythm_plan, continuity))
    payload = _audit_payload(
        root, summary, scenes, characters, foreshadowing, issues,
        word_budget, rhythm_plan, rhythm_curves, continuity, paths["graph"],
    )
    graph = build_graph(scenes, characters, foreshadowing)
    _write_outputs(root, paths, payload, graph)
    return LongformAuditResult(
        project_root=root,
        markdown_path=paths["markdown"],
        json_path=paths["json"],
        graph_path=paths["graph"],
        scene_count=len(scenes),
        chapter_count=int(summary["chapter_count"]),
        issue_count=len(issues),
        draft_chars=int(summary["draft_chars"]),
    )


def _resolved_target_length(root: Path, requested: int, word_budget: dict[str, object]) -> int:
    if requested > 0:
        return requested
    target = word_budget.get("target") if isinstance(word_budget.get("target"), dict) else {}
    totals = word_budget.get("totals") if isinstance(word_budget.get("totals"), dict) else {}
    budget_target = to_int(target.get("target_chinese_chars") or target.get("target_words"))
    if budget_target:
        return budget_target
    return to_int(scalar(read_text(root / "project.yaml"), "target_length"))


def _audit_payload(
    root: Path,
    summary: dict[str, object],
    scenes: list[LongformSceneRecord],
    characters: list[dict[str, object]],
    foreshadowing: list[dict[str, str]],
    issues: list[LongformIssue],
    word_budget: dict[str, object],
    rhythm_plan: dict[str, object],
    rhythm_curves: dict[str, object],
    continuity: dict[str, object],
    graph_path: Path,
) -> dict[str, object]:
    return {
        "schema": LONGFORM_AUDIT_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "summary": summary,
        "input_snapshot": longform_input_snapshot(root),
        "word_budget": word_budget,
        "rhythm_curves": rhythm_curves,
        "macro_rhythm": {
            "book_profile": rhythm_plan.get("book_profile", {}),
            "volumes": rhythm_plan.get("volumes", {}),
            "book": rhythm_plan.get("book", {}),
        },
        "continuity_ledgers": continuity,
        "scenes": [asdict(scene) for scene in scenes],
        "characters": characters,
        "foreshadowing": foreshadowing,
        "issues": [asdict(issue) for issue in issues],
        "graph_path": rel_str(graph_path, root),
    }


def _write_outputs(
    root: Path,
    paths: dict[str, Path],
    payload: dict[str, object],
    graph: dict[str, object],
) -> None:
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    paths["json"].write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["graph"].write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["markdown"].write_text(render_markdown(root, payload, paths["graph"]), encoding="utf-8")


def _chapter_files(root: Path) -> list[Path]:
    return list(formal_chapter_files(root))


def _output_paths(
    root: Path,
    output: Path | None,
    json_output: Path | None,
    graph_output: Path | None,
) -> dict[str, Path]:
    return {
        "markdown": _resolve_output(root, output, "reviews", "longform", "longform_audit.md"),
        "json": _resolve_output(root, json_output, "reviews", "longform", "longform_audit.json"),
        "graph": _resolve_output(root, graph_output, "plot", "longform_graph.json"),
    }


def _resolve_output(root: Path, output: Path | None, *default_parts: str) -> Path:
    if output is None:
        return root.joinpath(*default_parts)
    return output if output.is_absolute() else root / output


# Compatibility names remain available while ownership lives in focused modules.
_scan_scenes = scan_scenes
_scan_characters = scan_characters
_scan_foreshadowing = scan_foreshadowing
_audit_issues = audit_issues
_build_graph = build_graph
_render_markdown = render_markdown
_summary = build_summary
_rhythm_curve_issues = rhythm_curve_issues
_review_conclusion = review_conclusion
_foreshadow_status = foreshadow_status
_scalar = scalar
_list_after = list_after
_string_list = string_list
_outgoing_hook_text = outgoing_hook_text
_read = read_text
_to_int = to_int
_rel_str = rel_str
_existing_rel = existing_rel


__all__ = [
    "LongformAuditResult",
    "LongformIssue",
    "LongformSceneRecord",
    "build_longform_audit",
]
