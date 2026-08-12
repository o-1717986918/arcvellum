"""Shared deterministic facts for scene candidate promotion gates."""

from __future__ import annotations

import json
from pathlib import Path
import re

from ....foundation.draft_text import final_body_from_workbench_text


def candidate_body(text: str) -> str:
    """Extract promotable prose through the shared delivery-body contract.

    Pi Worker may return a prose-only artifact, while host agents often keep
    the workbench section headings.  Review, counting, revision, promotion,
    and export must interpret both forms identically.
    """

    return final_body_from_workbench_text(text)


def canon_change_value(value: object) -> bool | str | None:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "yes", "1", "changed", "change"}:
        return True
    if text in {"false", "no", "0", "none", "no_change", "not_required"}:
        return False
    if text in {"unknown", "pending", "todo", "needs_review"}:
        return "unknown"
    return None


def canon_writeback_declaration(root: Path, candidate_path: Path) -> dict[str, object]:
    payload = read_json(candidate_path.with_suffix(".json"))
    nested = payload.get("canon_writeback") if isinstance(payload.get("canon_writeback"), dict) else {}
    canon_change = nested.get("canon_change") if isinstance(nested, dict) and "canon_change" in nested else payload.get("canon_change")
    no_change_reason = (
        str(nested.get("no_canon_change_reason") or "").strip()
        if isinstance(nested, dict)
        else ""
    ) or str(payload.get("no_canon_change_reason") or "").strip()
    return {
        "canon_change": canon_change,
        "no_canon_change_reason": no_change_reason,
        "candidate_patch": str(nested.get("candidate_patch") or "") if isinstance(nested, dict) else "",
        "source": relative_path(candidate_path.with_suffix(".json"), root),
        "note": "promotion carries declaration only; canon-evolve creates/applies no canon automatically.",
    }


def empty_unresolved(value: object) -> bool:
    if isinstance(value, bool):
        return not value
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, str):
        return value.strip().lower() in {"", "false", "none", "no", "[]", "无"}
    return value in (None, 0)


def is_revision_candidate_path(root: Path, candidate_path: Path) -> bool:
    try:
        rel = candidate_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = str(candidate_path)
    return rel.startswith("drafts/revisions/") or candidate_path.name.endswith("_revision.md")


def mounted_style_exists(root: Path) -> bool:
    active = root / "style" / "active_style_skill.json"
    if active.exists():
        return True
    mounted = root / "style" / "mounted"
    return mounted.exists() and any(mounted.iterdir())


def normalize_review_path(value: str) -> str:
    return value.replace("\\", "/").strip().strip("`").lstrip("./")


def read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def section(text: str, heading: str, level: int = 2, stop_heading: str = "") -> str:
    marks = "#" * level
    if stop_heading:
        pattern = rf"(?ms)^{marks}\s*{re.escape(heading)}\s*\n(.*?)(?=^{marks}\s*{re.escape(stop_heading)}\s*$|\Z)"
    else:
        pattern = rf"(?ms)^{marks}\s*{re.escape(heading)}\s*\n(.*?)(?=^###\s+|^##\s+|\Z)"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""
