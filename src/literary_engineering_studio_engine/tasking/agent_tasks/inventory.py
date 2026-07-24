"""Inventory scanning for platform-agent task sidecars."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from .writer import agent_task_completion_status, default_agent_completion_path
from ...route_audit_common import _path_exists, _rel


BACKTICK_RE = re.compile(r"`([^`]+)`")
EXPECTED_HINT_RE = re.compile(r"(完成后写入|创建或覆盖|expected_|写入候选|写入正式|输出到|输出至)")
IGNORED_PARTS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv"}


@dataclass(frozen=True)
class AgentTaskRecord:
    path: str
    route: str
    status: str
    expected_paths: tuple[str, ...]
    existing_expected_paths: tuple[str, ...]
    missing_expected_paths: tuple[str, ...]
    source_paths: tuple[str, ...]
    missing_source_paths: tuple[str, ...]


def scan_agent_tasks(root: Path) -> list[AgentTaskRecord]:
    records = []
    for path in sorted(root.rglob("*.agent_tasks.md")):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if _is_human_decision_task(path, text):
            continue
        expected = _unique(_extract_expected_paths(root, text))
        completion = _normalize_path(root, default_agent_completion_path(path))
        if completion not in expected:
            expected.append(completion)
        sources = _unique(_extract_source_paths(root, text))
        existing = tuple(item for item in expected if _path_exists(root, item))
        missing = tuple(item for item in expected if not _path_exists(root, item))
        missing_sources = tuple(item for item in sources if not _path_exists(root, item))
        completion_state = agent_task_completion_status(path, root=root)
        status = "complete" if expected and not missing and completion_state.get("complete") is True else "partial" if expected and existing else "pending" if expected else "unknown"
        records.append(AgentTaskRecord(
            path=_rel(path, root), route=_infer_route(path, text), status=status,
            expected_paths=tuple(expected), existing_expected_paths=existing, missing_expected_paths=missing,
            source_paths=tuple(sources), missing_source_paths=missing_sources,
        ))
    return records


def summarize_records(records: list[AgentTaskRecord]) -> dict[str, int]:
    return {
        "task_count": len(records),
        "pending_count": sum(record.status == "pending" for record in records),
        "partial_count": sum(record.status == "partial" for record in records),
        "complete_count": sum(record.status == "complete" for record in records),
        "unknown_count": sum(record.status == "unknown" for record in records),
        "missing_expected_count": sum(len(record.missing_expected_paths) for record in records),
        "missing_source_count": sum(len(record.missing_source_paths) for record in records),
    }


def _is_human_decision_task(path: Path, text: str) -> bool:
    if "execution_policy: `human-required`" in text:
        return True
    payload = _registered_task_payload(path)
    return str(payload.get("execution_policy") or "") == "human-required"


def _registered_task_payload(path: Path) -> dict[str, object]:
    task_json = path.with_name(path.name.removesuffix(".agent_tasks.md") + ".task.json")
    if not task_json.is_file():
        return {}
    try:
        payload = json.loads(task_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_expected_paths(root: Path, text: str) -> list[str]:
    return [
        _normalize_path(root, item)
        for line in text.splitlines() if EXPECTED_HINT_RE.search(line)
        for item in BACKTICK_RE.findall(line) if _looks_like_project_path(item)
    ]


def _extract_source_paths(root: Path, text: str) -> list[str]:
    results: list[str] = []
    in_sources = False
    for line in text.splitlines():
        if line.strip() == "## Source Artifacts":
            in_sources = True
            continue
        if in_sources and line.startswith("## "):
            break
        if in_sources:
            results.extend(_normalize_path(root, item) for item in BACKTICK_RE.findall(line) if _looks_like_project_path(item))
    return results


def _looks_like_project_path(value: str) -> bool:
    text = value.strip()
    if not text or text.startswith("literary-engineering-workbench/") or re.search(r"\s", text):
        return False
    return "/" in text or "\\" in text or text.lower().endswith((".md", ".json", ".yaml", ".yml", ".csv", ".txt", ".docx"))


def _normalize_path(root: Path, value: str | Path) -> str:
    path = value if isinstance(value, Path) else Path(value.strip())
    return _rel(path, root) if path.is_absolute() else path.as_posix()


def _infer_route(path: Path, text: str) -> str:
    registered_route = str(_registered_task_payload(path).get("route") or "").strip()
    if registered_route:
        return registered_route
    route_line = re.search(r"(?m)^- route: `([^`]+)`\s*$", text)
    if route_line:
        return route_line.group(1).strip()
    joined = (path.as_posix() + "\n" + text[:1000]).lower()
    if "word_budget" in joined or "longform word budget" in joined:
        return "longform-planning"
    if "source_ingest" in joined or "extract_project_files" in joined or "sources/imports" in joined:
        return "source-ingest"
    if "style" in joined:
        return "style-engineering"
    if "asset" in joined or "candidate asset" in joined or "platform asset" in joined:
        return "character-and-world-assets"
    if "scene_review" in joined or "canon_review" in joined or "committee" in joined:
        return "review-and-audit"
    if "branch" in joined or "composition" in joined or "candidate" in joined or "state_patch" in joined or "revision" in joined:
        return "scene-development"
    if "export" in joined or "publish" in joined or "release" in joined:
        return "export-and-release"
    return "optional-cli"


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))
