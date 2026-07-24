"""Project bootstrap helpers owned by the creative director domain."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..init_project import InitOptions, InitResult, init_work_project
from .contracts import DirectorBootstrapResult
from .helpers import _now, _rel_str

def bootstrap_project_from_direction(
    target: Path,
    direction: str,
    *,
    title: str = "",
    work_type: str = "novel",
    target_length: int = 1000000,
    language: str = "zh-CN",
) -> DirectorBootstrapResult:
    """Create a complete work-project shell from one high-level creative direction."""

    resolved_title = title.strip() or _title_from_direction(direction)
    result = init_work_project(
        InitOptions(
            target=target,
            title=resolved_title,
            work_type=work_type,
            target_length=target_length,
            language=language,
            premise=direction.strip(),
            genre=_genre_from_direction(direction),
        )
    )
    bootstrap_path = _write_bootstrap_record(result.root, direction, resolved_title, result)
    return DirectorBootstrapResult(root=result.root, title=resolved_title, files=result.files, bootstrap_path=bootstrap_path)


def _director_run_id(seed: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", seed.strip()).strip("-").lower()[:24] or "direction"
    return f"director-{stamp}-{slug}-{uuid4().hex[:6]}"


def director_project_slug(direction: str) -> str:
    text = re.sub(r"\s+", "-", direction.strip().lower())
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "", text).strip("-")
    if not text:
        return "literary-project"
    return text[:32].strip("-") or "literary-project"


def _title_from_direction(direction: str) -> str:
    text = direction.strip()
    text = re.sub(r"^(请|帮我|我要|我想|新建|创建|生成|写一个|做一个|启动)\s*", "", text)
    text = re.split(r"[。！？!?；;\n]", text)[0].strip(" ：:，,")
    if not text:
        return "未命名文学项目"
    return text[:28]


def _genre_from_direction(direction: str) -> str:
    mapping = [
        ("悬疑", "悬疑"),
        ("推理", "推理"),
        ("科幻", "科幻"),
        ("奇幻", "奇幻"),
        ("玄幻", "玄幻"),
        ("历史", "历史"),
        ("都市", "都市"),
        ("现实", "现实主义"),
        ("短剧", "短剧"),
        ("剧本", "剧本"),
        ("伪纪录", "伪纪录"),
    ]
    return " / ".join(label for token, label in mapping if token in direction) or "长篇虚构"


def _write_bootstrap_record(root: Path, direction: str, title: str, result: InitResult) -> Path:
    record_path = root / "director" / "bootstrap.json"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "literary-engineering-workbench/director-bootstrap/v0.1",
        "created_at": _now(),
        "title": title,
        "user_direction": direction,
        "file_count": len(result.files),
        "files": [_rel_str(path, root) for path in result.files],
    }
    record_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record_path
