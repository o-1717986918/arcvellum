"""Read-only evidence helpers for the project review route."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from ...task_paths import read_json as _read_json
from ...task_paths import relative_path as _rel
from ...task_paths import resolve_project_path as _resolve_project_path


def project_review_repair_targets(
    root: Path,
    review_path: Path,
    fields: tuple[str, ...],
) -> list[str]:
    if not review_path.is_file():
        return []
    payload = _read_json(review_path)
    allowed_prefixes = ("canon/", "characters/", "plot/", "scenes/", "drafts/candidates/")
    targets: list[str] = []
    for field in fields:
        items = payload.get(field) if isinstance(payload.get(field), list) else []
        targets.extend(_safe_repair_targets(items, allowed_prefixes))
    return unique(targets)


def _safe_repair_targets(items: list[object], allowed_prefixes: tuple[str, ...]) -> list[str]:
    targets: list[str] = []
    allowed_suffixes = {".md", ".json", ".yaml", ".yml", ".csv"}
    for item in items:
        if not isinstance(item, dict):
            continue
        target = str(item.get("target_path") or item.get("target") or "").replace("\\", "/").strip()
        target = target.split("#", 1)[0]
        path = Path(target)
        if (
            target
            and not path.is_absolute()
            and ".." not in path.parts
            and target.startswith(allowed_prefixes)
            and path.suffix.lower() in allowed_suffixes
        ):
            targets.append(target)
    return targets


def declared_repair_targets_changed(root: Path, task: dict[str, object], label: str) -> list[str]:
    targets = [str(item) for item in task.get("repair_targets") or [] if str(item).strip()]
    before = task.get("repair_target_sha256_before_revision")
    hashes = before if isinstance(before, dict) else {}
    if not targets or not hashes:
        return [f"{label} is missing declared repair target hash provenance"]
    for target in targets:
        path = _resolve_project_path(root, target)
        previous = str(hashes.get(target) or "").strip().lower()
        if path.is_file() and previous and file_sha256(path) != previous:
            return []
    return [f"{label} did not change any declared planning candidate; review-only edits cannot complete revision"]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_optional_json(path: Path) -> tuple[dict[str, object], str]:
    if not path.exists():
        return {}, f"JSON file missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON: {_rel(path, path.parent)} ({exc.msg})"
    except OSError as exc:
        return {}, str(exc)
    if not isinstance(payload, dict):
        return {}, f"JSON root is not an object: {path}"
    return payload, ""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""


def static_review_conclusion(path: Path) -> str:
    text = read_text(path)
    match = re.search(r"(?m)^-\s*(?:审查)?结论：\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$", text, re.IGNORECASE)
    return match.group(1).strip().lower() if match else ""


def approval_record_for_run(root: Path, run_id: str) -> dict[str, object]:
    index = root / "workflow" / "approvals" / "index.jsonl"
    if not index.exists():
        return {}
    latest: dict[str, object] = {}
    for line in index.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("run_id") == run_id:
            latest = payload
    return latest


def approval_matches_file(approval: dict[str, object], subject: Path) -> bool:
    if not approval or not subject.is_file():
        return False
    recorded = str(approval.get("subject_sha256") or "").strip().lower()
    if recorded:
        return recorded == file_sha256(subject)
    recorded_at = parse_datetime(str(approval.get("recorded_at") or ""))
    if recorded_at is None:
        return False
    subject_time = datetime.fromtimestamp(subject.stat().st_mtime, tz=timezone.utc)
    return subject_time <= recorded_at


def parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def to_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).replace(",", "").replace("_", "").strip())
    except (TypeError, ValueError):
        return 0


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result
