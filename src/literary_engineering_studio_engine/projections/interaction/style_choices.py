"""Human-choice projection for immutable project-local style versions."""

from __future__ import annotations

from pathlib import Path

from ...display_cleaner import truncate_text
from ...literary.style.mount import inspect_active_style_mount
from ...literary.style.session import formal_style_profile_dirs
from ...literary.style.version_inspection import (
    inspect_style_version_directory,
)
from .common import _make_id, _rel


def build_style_mount_choice(root: Path) -> dict[str, object] | None:
    if _has_usable_active_mount(root):
        return None
    options, source_paths = _mountable_options(root)
    if not options:
        return None
    return {
        "choice_id": _make_id("choice", "style_mount", "project-style"),
        "route": "style-engineering",
        "decision_type": "style_mount",
        "title": "需要选择创作使用的文风",
        "summary": (
            "只列出已构建、完整且通过正式审查的不可变文风版本。"
            "选择后系统会重新验真并完成原子挂载。"
        ),
        "target": {"target_id": "project-style"},
        "source_paths": source_paths[:16],
        "options": options[:8],
        "actions": ["挂载明确文风版本"],
    }


def _has_usable_active_mount(root: Path) -> bool:
    active = inspect_active_style_mount(root)
    integrity = (
        active.get("integrity")
        if isinstance(active.get("integrity"), dict)
        else {}
    )
    return integrity.get("status") in {"pass", "legacy-unverified"}


def _mountable_options(
    root: Path,
) -> tuple[list[dict[str, str]], list[str]]:
    options: list[dict[str, str]] = []
    source_paths: list[str] = []
    for profile in formal_style_profile_dirs(root):
        for version_dir in sorted((profile / "versions").glob("v1-*")):
            option = _version_option(version_dir)
            if option is None:
                continue
            options.append(option)
            source_paths.extend(
                [
                    _rel(version_dir / "style_version.json", root),
                    _rel(version_dir / "prompt.md", root),
                ]
            )
    return options, list(dict.fromkeys(source_paths))


def _version_option(version_dir: Path) -> dict[str, str] | None:
    if not version_dir.is_dir():
        return None
    payload, errors = inspect_style_version_directory(version_dir)
    identity = {
        field: str(payload.get(field) or "").strip()
        for field in ("style_id", "version_id", "content_hash")
    }
    if errors or not all(identity.values()):
        return None
    return {
        "id": identity["version_id"],
        **identity,
        "label": truncate_text(
            str(payload.get("author_id") or identity["style_id"]),
            80,
        ),
        "summary": truncate_text(
            f"{payload.get('profile_id') or 'default'} · "
            f"已通过正式审查 · {identity['version_id']}",
            180,
        ),
    }


__all__ = ["build_style_mount_choice"]

