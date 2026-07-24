"""Shared HTTP-boundary helpers with no project-domain decisions."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, TypeVar

try:
    from fastapi import HTTPException
    from fastapi.responses import Response
except ImportError:  # pragma: no cover - API creation fails before use
    HTTPException = None
    Response = None


T = TypeVar("T")


def call_handler(function: Callable[[], T]) -> T:
    """Map expected local-domain errors to the stable Studio HTTP contract."""

    try:
        return function()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def project_root(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir() or not (path / "project.yaml").exists():
        raise ValueError(f"not a Literary Engineering work project: {path}")
    return path


def frontend_file(relative: str, content_type: str):
    root = Path(__file__).resolve().parents[1] / "frontend"
    candidate = (root / "dist" / relative).resolve()
    if not candidate.is_file() or not candidate.is_relative_to(root.resolve()):
        raise HTTPException(status_code=404, detail=f"frontend asset not found: {relative}")
    data = candidate.read_bytes()
    if content_type.startswith("text/") or "javascript" in content_type:
        return Response(content=data.decode("utf-8"), media_type=content_type)
    return Response(content=data, media_type=content_type)


def friendly_error(exc: Exception) -> str:
    value = str(exc).strip()
    replacements = {
        "bundled OpenCode Runner is not installed": "创作顾问尚未准备好，请先在“设置”中完成 Agent 连接。",
        "select an OpenCode provider/model before using the advisor": "请先在“设置”中选择顾问使用的模型。",
        "advisor answer timed out": "这次思考时间有点久，请稍后重试。",
        "read-only advisor project integrity check failed": "作品在顾问思考期间发生了内容变化，请重新提问以读取最新版本。",
    }
    return replacements.get(value, value or "顾问暂时没有完成回答，请重试。")
