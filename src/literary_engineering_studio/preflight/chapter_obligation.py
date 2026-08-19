"""Studio-owned normalization for chapter-obligation Agent output."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..contracts import TaskPackage
from ..sandbox import SandboxManifest


ReadObject = Callable[[Path], dict[str, Any] | None]
WriteMachineFields = Callable[
    [Path, str, dict[str, Any], dict[str, Any], str],
    list[dict[str, str]],
]


def canonicalize_chapter_obligation_metadata(
    task: TaskPackage,
    sandbox: SandboxManifest,
    *,
    read_object: ReadObject,
    write_machine_fields: WriteMachineFields,
) -> list[dict[str, str]]:
    """Restore immutable identity and derive the user-facing Markdown mirror."""

    if task.current_state != "reader-experience-contract":
        return []
    contract = _contract(task)
    relative = str(contract.get("path") or "").replace("\\", "/")
    fields = contract.get("fields") if isinstance(contract.get("fields"), dict) else {}
    if not relative or not fields:
        return []
    path = sandbox.workspace / Path(relative)
    payload = read_object(path)
    if payload is None:
        return []
    changes = write_machine_fields(
        path,
        relative,
        payload,
        fields,
        "chapter-obligation",
    )
    markdown_rel = str(contract.get("markdown_path") or "").replace("\\", "/")
    if markdown_rel:
        changes.extend(_render_markdown(sandbox.workspace, payload, relative, markdown_rel))
    return changes


def _contract(task: TaskPackage) -> dict[str, Any]:
    owned = task.payload.get("system_owned_fields")
    owned = owned if isinstance(owned, dict) else {}
    value = owned.get("chapter_obligation")
    return value if isinstance(value, dict) else {}


def _render_markdown(
    workspace: Path,
    payload: dict[str, Any],
    json_relative: str,
    markdown_relative: str,
) -> list[dict[str, str]]:
    path = workspace / Path(markdown_relative)
    rendered = _markdown_body(payload, json_relative)
    if path.is_file() and path.read_text(encoding="utf-8", errors="replace") == rendered:
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    return [
        {
            "path": markdown_relative,
            "field": "rendered_markdown",
            "reason": "rendered Studio-owned Markdown from authoritative chapter JSON",
        }
    ]


def _markdown_body(payload: dict[str, Any], json_relative: str) -> str:
    lines = [
        f"# 章节义务与读者体验契约：{payload.get('chapter_id', '')}",
        "",
        f"- JSON：`{json_relative}`",
        f"- 状态：`{payload.get('status', '')}`",
        f"- 目标中文内容字符：{payload.get('target_chinese_chars', 0)}",
        f"- 目标场景数：{payload.get('scene_count_target', 0)}",
        "",
        f"## 章节功能\n\n{payload.get('chapter_function') or '待填写'}",
        "",
        "## 场景读者契约",
        "",
        "| 场景 | 目标字符 | 读者问题 | 兑现或延迟 |",
        "| --- | ---: | --- | --- |",
    ]
    for row in payload.get("reader_experience_by_scene") or []:
        if isinstance(row, dict):
            lines.append(
                "| {scene} | {target} | {question} | {payoff} |".format(
                    scene=row.get("scene_id", ""),
                    target=row.get("word_count_target", 0),
                    question=str(row.get("reader_question") or "").replace("|", "\\|"),
                    payoff=str(row.get("payoff_or_delay") or "").replace("|", "\\|"),
                )
            )
    return "\n".join(lines).rstrip() + "\n"


__all__ = ["canonicalize_chapter_obligation_metadata"]
