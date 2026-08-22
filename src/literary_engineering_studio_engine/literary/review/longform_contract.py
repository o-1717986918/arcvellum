"""Deterministic freshness and quality contract for long-form audits."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from ..assets.continuity.ledger import normalize_ledger_rows
from ..scene.promotion.historical import historical_promotion_archive_paths


LONGFORM_AUDIT_SCHEMA = "literary-engineering-workbench/longform-audit/v0.1"
LONGFORM_AUDIT_SOURCE_PATHS = (
    "project.yaml",
    "canon",
    "characters",
    "style",
    "scenes",
    "branches",
    "drafts/candidates",
    "drafts/revisions",
    "drafts/scenes",
    "drafts/compositions",
    "drafts/promotions",
    "memory/context_packets",
    "plot/chapters",
    "plot/chapter_obligations",
    "plot/outline.md",
    "plot/conflict_matrix.md",
    "plot/foreshadowing.csv",
    "plot/promises",
    "plot/reader_questions",
    "plot/rhythm_plan.json",
    "plot/word_budget",
    "reviews",
)
STRUCTURAL_BLOCKING_CATEGORIES = frozenset(
    {
        "chapter_structure",
        "character_inventory",
        "continuity_ledger",
        "foreshadowing_debt",
        "macro_rhythm",
        "narrative_rhythm",
        "narrative_rhythm_curve",
        "scene_inventory",
        "scene_schema",
        "target_length_shortfall",
        "viewpoint_continuity",
        "word_budget",
    }
)
_INPUT_GLOBS = (
    "project.yaml",
    "canon/*.json",
    "canon/*.yaml",
    "canon/*.yml",
    "characters/*.yaml",
    "characters/*.yml",
    "style/*.json",
    "style/*.md",
    "style/*.yaml",
    "style/*.yml",
    "style/mounted/**/*",
    "scenes/*.yaml",
    "branches/*/roleplay_simulation.md",
    "branches/*/branch_manifest.json",
    "branches/*/branch_selection.md",
    "drafts/candidates/*.md",
    "drafts/candidates/*.json",
    "drafts/revisions/*.md",
    "drafts/revisions/*.json",
    "drafts/scenes/*.md",
    "drafts/compositions/*.json",
    "drafts/promotions/*.json",
    "memory/context_packets/*.md",
    "memory/context_packets/*.trace.json",
    "plot/chapters/*.json",
    "plot/chapter_obligations/*.json",
    "plot/chapter_obligations/*.agent_tasks.md",
    "plot/chapter_obligations/*.agent_completion.json",
    "plot/outline.md",
    "plot/conflict_matrix.md",
    "plot/foreshadowing.csv",
    "plot/promises/ledger.json",
    "plot/reader_questions/ledger.json",
    "plot/rhythm_plan.json",
    "plot/word_budget/word_budget.json",
    "plot/word_budget/word_budget.md",
    "reviews/*-review.md",
    "reviews/agent/*_scene_review.json",
    "reviews/schema_validation/*.json",
    "reviews/assets/*.json",
)
_OPEN_STATUSES = frozenset({"active", "delayed", "open", "opened", "pending", "postponed"})
_CLOSED_STATUSES = frozenset({"closed", "complete", "completed", "paid", "resolved"})


def longform_input_snapshot(root: Path) -> dict[str, Any]:
    """Hash every canonical input consumed by the long-form audit."""

    project = root.resolve()
    paths = {
        path.resolve()
        for pattern in _INPUT_GLOBS
        for path in project.glob(pattern)
        if path.is_file()
    }
    paths.update(
        (project / relative).resolve()
        for relative in _historical_input_paths(project)
        if (project / relative).is_file()
    )
    files: list[dict[str, str]] = []
    aggregate = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(project).as_posix()):
        relative = path.relative_to(project).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        aggregate.update(relative.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(digest.encode("ascii"))
        aggregate.update(b"\0")
        files.append({"path": relative, "sha256": digest})
    return {"digest": aggregate.hexdigest(), "file_count": len(files), "files": files}


def longform_audit_source_paths(root: Path) -> tuple[str, ...]:
    """Return deterministic audit inputs plus exact sealed scene archives."""

    return tuple(dict.fromkeys((*LONGFORM_AUDIT_SOURCE_PATHS, *_historical_input_paths(root.resolve()))))


def _historical_input_paths(root: Path) -> tuple[str, ...]:
    paths: list[str] = []
    for scene in sorted((root / "scenes").glob("*.yaml")):
        if scene.name.startswith("_"):
            continue
        paths.extend(historical_promotion_archive_paths(root, scene.stem))
    return tuple(dict.fromkeys(paths))


def longform_audit_gate_errors(
    root: Path,
    payload: dict[str, Any],
    *,
    require_clean: bool,
) -> list[str]:
    """Validate one audit without trusting its self-reported freshness or counts."""

    if payload.get("schema") != LONGFORM_AUDIT_SCHEMA:
        return ["longform_audit.json has wrong or missing schema"]
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else None
    if summary is None:
        return ["longform_audit.json must contain summary"]
    errors = _freshness_errors(root, payload)
    blocking = _blocking_issues(payload)
    if int(summary.get("blocking_issue_count") or 0) != len(blocking):
        errors.append("longform audit blocking_issue_count does not match its issue evidence")
    if require_clean and blocking:
        categories = sorted({str(item.get("category") or "unknown") for item in blocking})
        errors.append(
            f"longform audit has {len(blocking)} deterministic blocking issue(s): {', '.join(categories)}"
        )
    return errors


def longform_issue_is_blocking(issue: dict[str, Any]) -> bool:
    severity = str(issue.get("severity") or "").strip().lower()
    category = str(issue.get("category") or "").strip().lower()
    return severity == "high" or (severity == "medium" and category in STRUCTURAL_BLOCKING_CATEGORIES)


def audit_continuity_ledgers(root: Path, completed_scene_ids: Iterable[str]) -> dict[str, Any]:
    """Audit durable question/promise ledgers against formal scene progress."""

    latest_scene = max((_ordinal(item) for item in completed_scene_ids), default=-1)
    collections = (
        ("reader_questions", root / "plot" / "reader_questions" / "ledger.json", "target_window"),
        ("promises", root / "plot" / "promises" / "ledger.json", "due_window"),
    )
    issues: list[dict[str, str]] = []
    summaries: dict[str, dict[str, int | str]] = {}
    for collection, path, window_key in collections:
        summary, findings = _audit_ledger_collection(root, collection, path, window_key, latest_scene)
        summaries[collection] = summary
        issues.extend(findings)
    return {"collections": summaries, "issues": issues}


def _freshness_errors(root: Path, payload: dict[str, Any]) -> list[str]:
    expected = longform_input_snapshot(root)
    recorded = payload.get("input_snapshot") if isinstance(payload.get("input_snapshot"), dict) else {}
    if str(recorded.get("digest") or "") == expected["digest"]:
        return []
    return ["longform audit is stale for the current project inputs; rerun longform-audit"]


def _blocking_issues(payload: dict[str, Any]) -> list[dict[str, Any]]:
    issues = payload.get("issues") if isinstance(payload.get("issues"), list) else []
    return [item for item in issues if isinstance(item, dict) and longform_issue_is_blocking(item)]


def _audit_ledger_collection(
    root: Path,
    collection: str,
    path: Path,
    window_key: str,
    latest_scene: int,
) -> tuple[dict[str, int | str], list[dict[str, str]]]:
    payload = _read_json(path)
    source_rows = payload.get(collection) if isinstance(payload.get(collection), list) else []
    rows = normalize_ledger_rows(collection, source_rows)
    issues = _ledger_schema_issues(root, collection, path, payload)
    counters = {"open_count": 0, "closed_count": 0, "overdue_count": 0}
    for index, row in enumerate(rows, start=1):
        row_issues, row_counts = _audit_ledger_row(collection, row, index, window_key, latest_scene)
        issues.extend(row_issues)
        for key, value in row_counts.items():
            counters[key] += value
    return {"path": _rel(path, root), "count": len(rows), **counters}, issues


def _ledger_schema_issues(root: Path, collection: str, path: Path, payload: dict[str, Any]) -> list[dict[str, str]]:
    if not path.exists() or payload.get("schema") == "literary-engineering-workbench/continuity-ledger/v1":
        return []
    return [_ledger_issue("high", collection, _rel(path, root), "账本 schema 无效。", "重新执行 continuity-ledger apply，禁止手写替代正式账本。")]


def _audit_ledger_row(
    collection: str,
    row: object,
    index: int,
    window_key: str,
    latest_scene: int,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    counters = {"open_count": 0, "closed_count": 0, "overdue_count": 0}
    if not isinstance(row, dict):
        return [_ledger_issue("high", collection, f"row-{index}", "账本条目不是对象。", "修复账本来源 delta 后重新 apply。")], counters
    item_id = str(row.get("id") or row.get("question_id") or row.get("promise_id") or f"row-{index}")
    status = str(row.get("status") or "").strip().lower()
    window = str(row.get(window_key) or row.get("target_window") or row.get("due_window") or "").strip()
    if status in _OPEN_STATUSES:
        return _open_row_result(collection, item_id, window, window_key, latest_scene, row)
    if status in _CLOSED_STATUSES:
        counters["closed_count"] = 1
        issue = [] if _closure_evidence(row) else [_ledger_issue("medium", collection, item_id, "关闭条目缺少正文兑现证据。", "记录 payoff/evidence 与实际场景，或恢复为开放状态。")]
        return issue, counters
    return [_ledger_issue("medium", collection, item_id, f"账本状态 `{status or 'missing'}` 不可判定。", "使用 open/pending/delayed 或 resolved/closed/paid 等正式状态。")], counters


def _open_row_result(
    collection: str,
    item_id: str,
    window: str,
    window_key: str,
    latest_scene: int,
    row: dict[str, Any],
) -> tuple[list[dict[str, str]], dict[str, int]]:
    counters = {"open_count": 1, "closed_count": 0, "overdue_count": 0}
    if not window:
        if str(row.get("responsibility") or "").strip():
            return [_ledger_issue(
                "low",
                collection,
                item_id,
                "开放条目保留了后续责任，但尚未设置精确目标窗口。",
                f"在下一次推进时补齐 {window_key}；责任说明不能无限替代时间窗口。",
            )], counters
        return [_ledger_issue("medium", collection, item_id, "开放条目缺少目标窗口。", f"补齐 {window_key}，避免问题或承诺无限延期。")], counters
    if latest_scene >= 0 and _window_is_due(window, latest_scene):
        counters["overdue_count"] = 1
        return [_ledger_issue("high", collection, item_id, f"开放条目已越过目标窗口 `{window}`。", "兑现、合理延期或形成有证据的反转，不得静默关闭。")], counters
    return [], counters


def _window_is_due(window: str, latest_scene: int) -> bool:
    normalized = window.strip().lower()
    if not normalized.startswith("scene"):
        return False
    value = _ordinal(normalized)
    return value >= 0 and value <= latest_scene


def _closure_evidence(row: dict[str, Any]) -> bool:
    return any(
        str(row.get(key) or "").strip()
        for key in ("actual_payoff_scene", "evidence", "payoff_scene", "resolution_evidence")
    )


def _ordinal(value: object) -> int:
    numbers = re.findall(r"\d+", str(value or ""))
    return int(numbers[-1]) if numbers else -1


def _ledger_issue(severity: str, collection: str, subject: str, message: str, recommendation: str) -> dict[str, str]:
    return {
        "severity": severity,
        "category": "continuity_ledger",
        "subject": f"{collection}:{subject}",
        "message": message,
        "recommendation": recommendation,
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


__all__ = [
    "LONGFORM_AUDIT_SCHEMA",
    "LONGFORM_AUDIT_SOURCE_PATHS",
    "audit_continuity_ledgers",
    "longform_audit_source_paths",
    "longform_audit_gate_errors",
    "longform_input_snapshot",
    "longform_issue_is_blocking",
]
