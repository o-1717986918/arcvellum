"""Resolve and render the exact style context used by prose prompts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from ..literary.style.snapshot import (
    active_style_mount_snapshot_payload,
    active_style_prompt_path,
)


@dataclass(frozen=True)
class StylePromptContext:
    path: Path | None
    snapshot: dict[str, str]
    constraint: str


def resolve_style_prompt_context(root: Path, *, text_limit: int) -> StylePromptContext:
    path = active_style_prompt_path(root) or _fallback_style_asset(root)
    snapshot = active_style_mount_snapshot_payload(root)
    return StylePromptContext(
        path=path,
        snapshot=snapshot,
        constraint=_render_constraint(root, path, snapshot, text_limit),
    )


def _fallback_style_asset(root: Path) -> Path | None:
    style_root = root / "style"
    candidates = [style_root / "style_prompt.md"]
    if style_root.exists():
        candidates.extend(
            sorted(
                style_root.glob("*/style_prompt.md"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        )
    candidates.append(style_root / "style-profile.md")
    if style_root.exists():
        candidates.extend(
            sorted(
                style_root.glob("*/style-profile.md"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        )
    return next((path for path in candidates if path.exists()), None)


def _render_constraint(
    root: Path,
    style_path: Path | None,
    snapshot: dict[str, str],
    text_limit: int,
) -> str:
    if style_path is None:
        return "未找到挂载的 style skill 或 style/style-profile.md。若项目要求文风门禁，应先在文风学习页挂载 active style skill。"
    text = style_path.read_text(encoding="utf-8")[:text_limit]
    active = root / "style" / "active_style_skill.json"
    if not active.exists():
        return text
    payload = snapshot or _read_json(active)
    return f"""# 已挂载文风 Style Skill（最高优先级）

- Style ID: `{payload.get("style_id", "")}`
- Version ID: `{payload.get("version_id", "")}`
- Content Hash: `{payload.get("content_hash", "")}`
- Prompt SHA-256: `{payload.get("prompt_sha256", "")}`
- Snapshot Digest: `{payload.get("digest", "")}`
- Priority: `{payload.get("priority", "highest")}`

硬规则：

- 本 Style Skill 在表达层拥有最高优先级：叙述距离、句法节奏、意象系统、心理呈现、对白密度和段落推进必须先服从它。
- 它不覆盖 canon、人物事实、剧情因果、用户明确约束和安全边界。
- 如文风要求与 canon/人物逻辑冲突，保留 canon/人物逻辑，并在“需要人工确认”中说明文风冲突。

## Style Skill Prompt

{text}
"""


def _read_json(path: Path) -> dict[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


__all__ = ["StylePromptContext", "resolve_style_prompt_context"]
