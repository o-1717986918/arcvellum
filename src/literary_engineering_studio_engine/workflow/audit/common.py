"""Route-audit primitives shared by evidence-only audit modules."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re


DEBUG_WAIVER_KEYS = {
    "allow_unreviewed", "allow_review_notes", "allow_unapproved", "allow_unresolved",
    "allow_missing_composition", "allow_unselected_composition", "allow_missing_branch",
    "allow_recommended_branch", "include_blocked",
}
DEBUG_WAIVER_DECISIONS = {
    "allow_unreviewed", "allow_review_notes", "allow_unapproved", "allow_unresolved", "include_blocked",
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
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


def _path_exists(root: Path, value: str) -> bool:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    # Historical task packages may reference an expired packaged runtime.
    try:
        return path.exists()
    except OSError:
        return False


def _normalize_route(route: str) -> str:
    return route.strip().lower().replace("_", "-")


def _resolve_output(root: Path, output: Path | None, *default_parts: str) -> Path:
    return root.joinpath(*default_parts) if output is None else output if output.is_absolute() else root / output


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _add_gate(gates: list[dict[str, str]], key: str, passed: bool, severity: str, passed_message: str, failed_message: str) -> None:
    gates.append({
        "key": key,
        "status": "pass" if passed else "fail",
        "severity": "info" if passed else severity,
        "message": passed_message if passed else failed_message,
    })


def _project_target_words(root: Path) -> int:
    text = _read_text(root / "project.yaml")
    values: list[int] = []
    for key in ("target_length", "target_words"):
        for match in re.finditer(rf"(?m)^\s*{re.escape(key)}:\s*([0-9][0-9_,]*)\s*$", text):
            try:
                values.append(int(match.group(1).replace("_", "").replace(",", "")))
            except ValueError:
                continue
    return max(values) if values else 0


def _approval_record(root: Path, run_id: str) -> dict[str, object]:
    """Return the latest durable approval record for a formal run."""

    index = root / "workflow" / "approvals" / "index.jsonl"
    if not index.exists():
        return {}
    latest: dict[str, object] = {}
    for line in _read_text(index).splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("run_id") == run_id:
            latest = payload
    return latest


def _debug_waiver_hits(root: Path) -> list[str]:
    hits: list[str] = []
    for path in sorted(root.rglob("*.json")):
        if any(part in {".git", "node_modules", "__pycache__"} for part in path.parts):
            continue
        payload = _read_json(path)
        if payload:
            hits.extend(_scan_debug_waivers(payload, _rel(path, root), ()))
    return list(dict.fromkeys(hits))


def _scan_debug_waivers(value: object, source: str, trail: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            current = trail + (key_text,)
            if key_text in DEBUG_WAIVER_KEYS and _truthy_debug_flag(item):
                hits.append(f"{source}:{'.'.join(current)}={item}")
            if key_text == "decision" and str(item).strip().lower() in DEBUG_WAIVER_DECISIONS:
                hits.append(f"{source}:{'.'.join(current)}={item}")
            hits.extend(_scan_debug_waivers(item, source, current))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_scan_debug_waivers(item, source, trail + (str(index),)))
    return hits


def _truthy_debug_flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"true", "yes", "1", "allow", "allowed", "enabled"}
