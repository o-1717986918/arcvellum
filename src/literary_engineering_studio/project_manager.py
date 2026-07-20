"""Studio-owned project lifecycle and user-direction persistence."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

from literary_engineering_studio_engine.init_project import InitOptions, init_work_project

from .config import default_config_path


REGISTRY_SCHEMA = "literary-engineering-studio/project-registry/v0.1"
DIRECTION_SCHEMA = "literary-engineering-studio/user-direction/v0.1"


def validate_project_location(
    *,
    mode: str,
    project_root: str = "",
    parent_directory: str = "",
    folder_name: str = "",
) -> dict[str, Any]:
    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"open", "create"}:
        raise ValueError("目录验证模式必须是 open 或 create。")
    conflicts: list[str] = []
    warnings: list[str] = []
    if normalized_mode == "open":
        path = Path(project_root).expanduser().resolve()
        exists = path.is_dir()
        has_project = exists and (path / "project.yaml").is_file()
        if exists and not has_project:
            conflicts.append("这里没有找到 ArcVellum 作品。")
        if not exists:
            conflicts.append("选择的文件夹不存在。")
        return {
            "valid": has_project,
            "mode": normalized_mode,
            "resolved_path": str(path),
            "writable": bool(exists and os.access(path, os.W_OK)),
            "exists": exists,
            "conflicts": conflicts,
            "warnings": warnings,
        }

    parent = Path(parent_directory).expanduser().resolve()
    folder = _safe_folder_name(folder_name or "untitled-work")
    target = parent / folder
    parent_exists = parent.is_dir()
    writable = bool(parent_exists and os.access(parent, os.W_OK))
    if not parent_exists:
        conflicts.append("选择的保存位置不存在。")
    elif not writable:
        conflicts.append("ArcVellum 无法在这个位置建立作品。")
    if target.exists():
        conflicts.append("这个位置已经有同名文件夹。")
    if len(str(target)) > 220:
        warnings.append("目录较长，某些导出工具可能无法处理。")
    return {
        "valid": not conflicts,
        "mode": normalized_mode,
        "resolved_path": str(target),
        "writable": writable,
        "exists": target.exists(),
        "conflicts": conflicts,
        "warnings": warnings,
    }


def project_registry_path() -> Path:
    return default_config_path().with_name("projects.json")


def list_projects() -> dict[str, Any]:
    registry = _load_registry()
    projects: list[dict[str, Any]] = []
    for item in registry.get("recent", []):
        path = Path(str(item.get("path") or "")).expanduser()
        if not path.is_dir() or not (path / "project.yaml").is_file():
            continue
        projects.append({**project_summary(path), "last_opened": str(item.get("last_opened") or "")})
    return {
        "schema": REGISTRY_SCHEMA,
        "current_project": str(registry.get("current_project") or ""),
        "projects": projects,
    }


def create_project(
    *,
    parent_directory: str,
    title: str,
    folder_name: str = "",
    work_type: str = "novel",
    target_length: int = 30000,
    premise: str = "",
    genre: str = "",
) -> dict[str, Any]:
    clean_title = title.strip()
    if not clean_title:
        raise ValueError("作品名称不能为空。")
    parent = Path(parent_directory).expanduser().resolve()
    if not parent.is_dir():
        raise FileNotFoundError(f"项目保存位置不存在：{parent}")
    folder = _safe_folder_name(folder_name or clean_title)
    target = parent / folder
    init_work_project(
        InitOptions(
            target=target,
            title=clean_title,
            work_type=work_type.strip() or "novel",
            target_length=max(1000, int(target_length)),
            premise=premise.strip(),
            genre=genre.strip(),
        )
    )
    return register_project(target)


def register_project(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir() or not (root / "project.yaml").is_file():
        raise FileNotFoundError(f"这不是有效的文学工程项目：{root}")
    registry = _load_registry()
    now = _now()
    recent = [
        item
        for item in registry.get("recent", [])
        if Path(str(item.get("path") or "")).expanduser().resolve() != root
    ]
    recent.insert(0, {"path": str(root), "last_opened": now})
    registry["current_project"] = str(root)
    registry["recent"] = recent[:24]
    _save_registry(registry)
    return project_summary(root)


def current_project() -> dict[str, Any]:
    registry = _load_registry()
    value = str(registry.get("current_project") or "")
    if not value:
        return {"ok": True, "project": None}
    root = Path(value).expanduser()
    if not root.is_dir() or not (root / "project.yaml").is_file():
        return {"ok": True, "project": None}
    return {"ok": True, "project": project_summary(root)}


def project_summary(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    values = _read_project_yaml(root / "project.yaml")
    return {
        "path": str(root),
        "title": str(values.get("title") or root.name),
        "work_type": str(values.get("type") or "novel"),
        "target_length": int(values.get("target_length") or 0),
        "status": str(values.get("status") or "planning"),
        "genre": str(values.get("genre") or ""),
        "premise": str(values.get("premise") or ""),
        "direction_count": len(read_directions(root, limit=200)),
    }


def record_direction(project_root: Path | str, message: str, *, actor: str = "user") -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    if not (root / "project.yaml").is_file():
        raise FileNotFoundError(f"项目不存在：{root}")
    clean = message.strip()
    if not clean:
        raise ValueError("创作方向不能为空。")
    if len(clean) > 6000:
        raise ValueError("单条创作方向不能超过 6000 个字符。")
    record = {
        "schema": DIRECTION_SCHEMA,
        "recorded_at": _now(),
        "actor": actor.strip() or "user",
        "message": clean,
    }
    directory = root / "workflow" / "studio"
    directory.mkdir(parents=True, exist_ok=True)
    index = directory / "user_directions.jsonl"
    with index.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    records = read_directions(root, limit=20)
    digest = directory / "user_directions.md"
    digest.write_text(_render_direction_digest(records), encoding="utf-8")
    return {"ok": True, "record": record, "digest": "workflow/studio/user_directions.md"}


def read_directions(project_root: Path | str, *, limit: int = 20) -> list[dict[str, Any]]:
    root = Path(project_root).expanduser().resolve()
    path = root / "workflow" / "studio" / "user_directions.jsonl"
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("message"):
            records.append(payload)
    return records[-max(1, min(200, int(limit))):]


def _load_registry() -> dict[str, Any]:
    path = project_registry_path()
    if not path.is_file():
        return {"schema": REGISTRY_SCHEMA, "current_project": "", "recent": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"schema": REGISTRY_SCHEMA, "current_project": "", "recent": []}
    if not isinstance(payload, dict):
        return {"schema": REGISTRY_SCHEMA, "current_project": "", "recent": []}
    payload["schema"] = REGISTRY_SCHEMA
    payload.setdefault("current_project", "")
    payload.setdefault("recent", [])
    return payload


def _save_registry(payload: dict[str, Any]) -> None:
    path = project_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["schema"] = REGISTRY_SCHEMA
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_project_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    values: dict[str, Any] = {}
    section = ""
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        stripped = raw.strip()
        if indent == 0 and stripped.endswith(":"):
            section = stripped[:-1]
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        if section not in {"project", "creative_brief"}:
            continue
        parsed = _parse_scalar(value.strip())
        if key in {"title", "type", "target_length", "status", "genre", "premise"}:
            values[key] = parsed
    return values


def _parse_scalar(value: str) -> Any:
    if not value:
        return ""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        if value.isdigit():
            return int(value)
        return value.strip("'\"")


def _safe_folder_name(value: str) -> str:
    text = re.sub(r"[<>:\"/\\|?*\x00-\x1f]+", "-", value.strip())
    text = re.sub(r"\s+", "-", text).strip(" .-")
    return text[:80] or "literary-project"


def _render_direction_digest(records: list[dict[str, Any]]) -> str:
    lines = ["# 当前用户创作方向", "", "以下内容由 Studio 客户端记录。执行任务时应把较新的方向视为更高优先级，但不得借此绕过 Canon、审查或人工审批门禁。", ""]
    if not records:
        lines.append("暂无用户创作方向。")
    for item in reversed(records):
        lines.extend([f"## {item.get('recorded_at', '')}", "", str(item.get("message") or "").strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
