"""Candidate identity and promotion evidence for the asset route."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from ...asset_workshop import ASSET_CANDIDATE_DIRS, PROMOTABLE_GROUPS
from ...literary.assets.promotion import file_sha256
from ...literary.assets.promotion import promotion_output_paths
from ...task_paths import read_json as _read_json
from ...task_paths import relative_path as _rel
from ...task_paths import resolve_project_path as _resolve_project_path


def candidate_digest(root: Path, candidate: str) -> str:
    path = _resolve_project_path(root, candidate) if candidate else None
    return file_sha256(path) if path is not None and path.is_file() else ""


def candidate_path_for_task(root: Path, task: dict[str, object]) -> Path:
    candidate = str(task.get("candidate") or "").strip()
    if candidate:
        return _resolve_project_path(root, candidate)
    found = _candidate_from_task_paths(root, task)
    if found is not None:
        return found
    candidate_id = str(task.get("candidate_id") or task.get("target_id") or "asset-intake")
    return root / "characters" / "candidates" / f"{candidate_id}.json"


def _candidate_from_task_paths(root: Path, task: dict[str, object]) -> Path | None:
    candidates = [
        *[str(item) for item in task.get("submitted_artifacts") or []],
        *[str(item) for item in task.get("expected_outputs") or []],
        *[str(item) for item in task.get("source_paths") or []],
    ]
    for item in candidates:
        normalized = item.replace("\\", "/")
        if not normalized.endswith(".json"):
            continue
        if ".agent_" in normalized or "/reviews/" in f"/{normalized}" or "/workflow/" in f"/{normalized}":
            continue
        if is_asset_candidate_rel(normalized):
            return _resolve_project_path(root, item)
    return None


def candidate_path_for_id(root: Path, candidate_id: str) -> Path:
    matches: list[Path] = []
    seen: set[Path] = set()
    for folder in ASSET_CANDIDATE_DIRS.values():
        candidate = root / folder / f"{candidate_id}.json"
        if candidate.is_file() and candidate not in seen:
            matches.append(candidate)
            seen.add(candidate)
    if len(matches) > 1:
        paths = ", ".join(_rel(path, root) for path in matches)
        raise ValueError(f"duplicate asset candidate id {candidate_id}: {paths}")
    if matches:
        return matches[0]
    return root / "characters" / "candidates" / f"{candidate_id}.json"


def is_asset_candidate_rel(value: str) -> bool:
    normalized = value.replace("\\", "/").lstrip("/")
    return any(normalized.startswith(folder.as_posix() + "/") for folder in ASSET_CANDIDATE_DIRS.values())


def asset_type_from_payload_or_path(root: Path, candidate: Path, payload: dict[str, object]) -> str:
    asset_type = str(payload.get("asset_type") or "").strip().lower().replace("_", "-")
    if asset_type:
        return asset_type
    relative = _rel(candidate, root)
    for item_type, folder in ASSET_CANDIDATE_DIRS.items():
        if relative.startswith(folder.as_posix() + "/"):
            return item_type
    return ""


def asset_promotion_sources(candidate: str, candidate_id: str) -> list[str]:
    review_base = f"reviews/assets/{candidate_id}_review"
    return [
        candidate,
        f"{review_base}.md",
        f"{review_base}.json",
        f"{review_base}.agent_tasks.md",
        f"{review_base}.agent_completion.json",
        "workflow/approvals/index.jsonl",
    ]


def asset_promotion_group(asset_type: str) -> str:
    normalized = asset_type.strip().lower().replace("_", "-")
    for group, members in PROMOTABLE_GROUPS.items():
        if normalized in members:
            return group
    return ""


def asset_promoted_output_rels(root: Path, candidate: Path, asset_type: str) -> list[str]:
    if not candidate.is_file():
        return []
    payload = _read_json(candidate)
    return [_rel(path, root) for path in promotion_output_paths(root, asset_type, payload)]


def pending_revision_action_ids(review_path: Path) -> list[str]:
    payload, error = read_optional_json(review_path)
    if error:
        return []
    actions = payload.get("revision_actions") if isinstance(payload.get("revision_actions"), list) else []
    identifiers: list[str] = []
    for index, action in enumerate(actions, start=1):
        identifier = str(action.get("id") or "").strip() if isinstance(action, dict) else ""
        identifiers.append(identifier or f"revision-action-{index}")
    return identifiers


def revision_evidence_requirement(action_ids: list[str]) -> str:
    listed = ", ".join(f"`{item}`" for item in action_ids) if action_ids else "每一项原始 revision_action"
    return (
        "先完成候选资产修改，再重写 review JSON 的复审字段："
        "`status` 必须为 `recheck_required`，`revision_round` 必须是 >= 1 的整数，"
        "`applied_revision_actions` 必须是非空数组；数组内每项至少写 `id`、`action` 和 `evidence`。"
        f"本轮必须逐项覆盖：{listed}。不得只保留旧 `revision_actions` 来代替落实证据。"
    )


def worker_managed_revision_evidence_requirement(action_ids: list[str]) -> str:
    listed = ", ".join(f"`{item}`" for item in action_ids) if action_ids else "当前审批理由"
    return (
        "先完成候选资产和候选报告的实质性修改。不要改写 review JSON、review Markdown 或 completion receipt；"
        "Studio Worker 会在检测到候选摘要变化后，将审批理由写入 applied_revision_actions、"
        "设置 review status 为 recheck_required，并重置独立复审回执。"
        f"本轮候选修改必须可追溯地回应：{listed}。"
    )


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


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def parse_datetime(value: str) -> datetime | None:
    normalized = value.strip().replace("Z", "+00:00")
    if not normalized:
        return None
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


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
