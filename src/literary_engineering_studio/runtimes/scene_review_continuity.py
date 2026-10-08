"""Ordered, source-bound review history and issue progress for scene transactions."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping


LEDGER_NAME = "review_issue_ledger_v1.json"
LEDGER_SCHEMA = "arcvellum/scene-review-issue-ledger/v1"
_ISSUE_STATUSES = {"new", "resolved", "persists", "changed", "uncertain"}


def review_continuity(root: Path, prose: str) -> dict[str, Any]:
    current_digest = sha256(prose.encode("utf-8")).hexdigest()
    ledger = _read_ledger(root)
    if ledger is None:
        return _legacy_continuity(root, current_digest)
    entries = sorted(ledger["entries"], key=lambda item: int(item["sequence"]))
    current = next((item for item in reversed(entries)
                    if item.get("prose_sha256") == current_digest), None)
    earlier = [item for item in entries if item.get("prose_sha256") != current_digest]
    previous = earlier[-1] if earlier else None
    focus = current or previous
    return {
        "completed_reviews": len(entries),
        "completed_revisions": _revision_count(root),
        "current": _entry_projection(current) if current else None,
        "previous": _entry_projection(previous) if previous else None,
        "open_issues": _open_issues(focus),
    }


def record_review(
    root: Path, prose: str, extracted: Mapping[str, Any], formal: Mapping[str, Any], source: str,
) -> dict[str, Any]:
    ledger = _read_ledger(root) or {"schema": LEDGER_SCHEMA, "entries": []}
    entries = sorted(ledger["entries"], key=lambda item: int(item["sequence"]))
    digest = sha256(prose.encode("utf-8")).hexdigest()
    existing = next((item for item in entries if item.get("prose_sha256") == digest), None)
    if existing is not None:
        return existing
    previous = entries[-1] if entries else None
    issue_snapshot = _updated_issues(previous, extracted)
    entry = {
        "sequence": (int(previous["sequence"]) + 1) if previous else 1,
        "prose_sha256": digest,
        "source": Path(source).name if source else "",
        "review": dict(formal),
        "strengths": _rows(extracted.get("strengths")),
        "issues": issue_snapshot,
        "optional_explorations": _rows(extracted.get("optional_explorations")),
        "issue_progress": _rows(extracted.get("issue_progress")),
    }
    entries.append(entry)
    ledger["entries"] = entries[-120:]
    _write_ledger(root, ledger)
    return entry


def formal_review_payload(extracted: Mapping[str, Any]) -> dict[str, Any]:
    strengths = _rows(extracted.get("strengths"))
    issues = _rows(extracted.get("major_issues"))
    explorations = _rows(extracted.get("optional_explorations"))
    progress = _rows(extracted.get("issue_progress"))
    sections = [str(extracted.get("summary") or "").strip()]
    sections.extend(_render_findings("正文已经成立", strengths, "claim"))
    sections.extend(_render_findings("主要修订问题", issues, "title"))
    sections.extend(_render_findings("可选审美探索", explorations, "question"))
    sections.extend(_render_progress(progress))
    instructions = _strings(extracted.get("revision_instructions"))
    if not instructions:
        instructions = [str(row.get("direction") or "").strip() for row in issues
                        if str(row.get("direction") or "").strip()]
    evidence = _unique([
        *_strings(extracted.get("evidence")),
        *(str(row.get("evidence") or "").strip()
          for group in (strengths, issues, explorations, progress) for row in group),
    ])
    return {
        "decision": str(extracted.get("decision") or ""),
        "summary": "\n".join(section for section in sections if section),
        "revision_instructions": instructions,
        "evidence": evidence,
    }


def _updated_issues(previous: Mapping[str, Any] | None, extracted: Mapping[str, Any]) -> list[dict[str, Any]]:
    old_issues = {str(item.get("issue_id")): item for item in _open_issues(previous)}
    progress = {str(item.get("issue_id")): item for item in _rows(extracted.get("issue_progress"))}
    sequence = _next_sequence(previous)
    current = {identifier: _carried_issue(identifier, prior, progress.get(identifier), sequence)
               for identifier, prior in old_issues.items()}
    for row in _rows(extracted.get("major_issues")):
        issue = _major_issue(row, old_issues, progress, sequence)
        current[issue["issue_id"]] = issue
    return sorted(current.values(), key=lambda item: (int(item.get("first_seen_sequence") or 0), item["issue_id"]))


def _carried_issue(identifier, prior, update, sequence):
    update = update or {}
    status = _valid_status(update.get("status"), "uncertain")
    return {**prior, "status": status,
            "latest_evidence": str(update.get("evidence") or ""),
            "last_review_sequence": sequence}


def _major_issue(row, old_issues, progress, sequence):
    title = str(row.get("title") or "").strip()
    evidence = str(row.get("evidence") or "").strip()
    linked = str(row.get("prior_issue_id") or "").strip()
    identifier = linked if linked in old_issues else _issue_id(title, evidence)
    prior = old_issues.get(identifier)
    update = progress.get(identifier) or {}
    default = "persists" if prior else "new"
    status = _valid_status(update.get("status"), default)
    return {
        "issue_id": identifier,
        "title": title,
        "evidence": evidence,
        "reader_effect": str(row.get("reader_effect") or ""),
        "direction": str(row.get("direction") or ""),
        "first_seen_sequence": int(prior.get("first_seen_sequence") or 1) if prior else sequence,
        "last_review_sequence": sequence,
        "status": status,
        "latest_evidence": str(update.get("evidence") or evidence),
    }


def _valid_status(value, default):
    status = str(value or default)
    return status if status in _ISSUE_STATUSES else "uncertain"


def _issue_id(title: str, evidence: str) -> str:
    normalized = re.sub(r"\s+", " ", title + "\n" + evidence).strip().casefold()
    return "issue-" + sha256(normalized.encode("utf-8")).hexdigest()[:14]


def _entry_projection(entry: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if entry is None:
        return None
    return {key: entry.get(key) for key in (
        "sequence", "source", "prose_sha256", "review", "strengths", "issues",
        "optional_explorations", "issue_progress",
    )}


def _open_issues(entry: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if entry is None:
        return []
    return [dict(item) for item in entry.get("issues") or []
            if item.get("status") != "resolved"]


def _legacy_continuity(root: Path, current_digest: str) -> dict[str, Any]:
    prefix = current_digest[:16]
    reviews = sorted(path for path in root.glob("review_result_v2_*.json")
                     if path.name != f"review_result_v2_{prefix}.json")
    previous = None
    ambiguous = []
    if len(reviews) == 1:
        path = reviews[0]
        previous = {"source": path.name,
                    "prose_sha256_prefix": path.stem.removeprefix("review_result_v2_"),
                    "review": json.loads(path.read_text(encoding="utf-8"))}
    elif len(reviews) > 1:
        ambiguous = [path.name for path in reviews]
    result = {"completed_reviews": len(reviews), "completed_revisions": _revision_count(root),
              "previous": previous, "open_issues": []}
    if ambiguous:
        result["ambiguous_legacy_reviews"] = ambiguous
    return result


def _read_ledger(root: Path) -> dict[str, Any] | None:
    path = root / LEDGER_NAME
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(payload, dict) or payload.get("schema") != LEDGER_SCHEMA
            or not isinstance(payload.get("entries"), list)):
        raise ValueError("scene review issue ledger has an unsupported format")
    return payload


def _write_ledger(root: Path, ledger: Mapping[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = root / LEDGER_NAME
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _revision_count(root: Path) -> int:
    return len(list(root.glob("revision_result_v2_*.json")))


def _next_sequence(previous: Mapping[str, Any] | None) -> int:
    return int(previous.get("sequence") or 0) + 1 if previous else 1


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value[:40] if isinstance(item, Mapping)]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value[:40] if isinstance(item, str) and item.strip()]


def _render_findings(label: str, rows: list[dict[str, Any]], key: str) -> list[str]:
    return [label + "：" + "；".join(
        part for part in (str(row.get(key) or "").strip(), str(row.get("reader_effect") or "").strip(),
                          str(row.get("direction") or "").strip()) if part)
        for row in rows if any(str(row.get(field) or "").strip() for field in (key, "reader_effect", "direction"))]


def _render_progress(rows: list[dict[str, Any]]) -> list[str]:
    return ["前轮问题进展：" + "；".join(
        f"{row.get('issue_id')}—{row.get('status')}"
        for row in rows if row.get("issue_id"))] if rows else []


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if isinstance(item, str) and item.strip()))


__all__ = ["formal_review_payload", "record_review", "review_continuity"]
