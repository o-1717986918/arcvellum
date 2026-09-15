"""Shared identity lookup for formal character assets."""

from __future__ import annotations

import json
from pathlib import Path
import re


def formal_character_aliases(project_root: Path) -> set[str]:
    aliases: set[str] = set()
    root = project_root.resolve()
    characters = root / "characters"
    for path in sorted([*characters.glob("*.yaml"), *characters.glob("*.yml")]):
        if path.name.startswith("_"):
            continue
        text = read_character_text(path)
        _add_alias(aliases, path.stem)
        character_id = character_field_value(text, "character_id")
        for key in ("character_id", "name"):
            value = character_field_value(text, key)
            if value:
                _add_alias(aliases, value)
        for value in _list_value(text, "aliases"):
            _add_alias(aliases, value)
        role = character_field_value(text, "role").lower()
        if _is_protagonist_identity(path.stem, character_id, role):
            _add_alias(aliases, "主角")
            _add_alias(aliases, "protagonist")
    _append_promoted_aliases(root, aliases)
    return aliases


def formal_character_promotion_manifests(project_root: Path) -> tuple[Path, ...]:
    """Return promotion receipts required to resolve formal character aliases."""

    root = project_root.resolve()
    promotions = root / "workflow" / "asset_promotions"
    if not promotions.is_dir():
        return ()
    paths: list[Path] = []
    for path in sorted(promotions.glob("*_promotion.json")):
        payload = _promotion_payload(path)
        asset_type = str(payload.get("asset_type") or "").strip().lower()
        candidate_id = str(payload.get("candidate_id") or "").strip()
        if asset_type:
            if asset_type != "character":
                continue
            if str(payload.get("status") or "").strip().lower() != "promoted":
                continue
            outputs = payload.get("outputs")
            if not isinstance(outputs, list) or not any(
                str(item).replace("\\", "/").startswith("characters/")
                for item in outputs
            ):
                continue
        elif not _legacy_character_candidate_id(candidate_id):
            continue
        paths.append(path)
    return tuple(paths)


def is_formal_character(project_root: Path, identity: str) -> bool:
    normalized = str(identity or "").strip()
    if not normalized:
        return False
    aliases = formal_character_aliases(project_root)
    return normalized in aliases or character_slug(normalized) in aliases


def character_field_value(text: str, key: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(.+?)\s*$", text)
    return match.group(1).strip().strip("'\"") if match else ""


def character_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")


def read_character_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _append_promoted_aliases(root: Path, aliases: set[str]) -> None:
    for path in formal_character_promotion_manifests(root):
        payload = _promotion_payload(path)
        candidate_id = str(payload.get("candidate_id") or "").strip()
        if not candidate_id:
            candidate_id = path.stem.removesuffix("_promotion")
        _add_alias(aliases, candidate_id)
        if "protagonist" in candidate_id.lower():
            _add_alias(aliases, "主角")
            _add_alias(aliases, "protagonist")
        match = re.match(r"scene-\d+-(.+)", candidate_id)
        if match:
            _add_alias(aliases, match.group(1))


def _promotion_payload(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _legacy_character_candidate_id(candidate_id: str) -> bool:
    normalized = candidate_id.strip().lower()
    return "protagonist" in normalized or bool(
        re.match(r"scene-\d+-.+", candidate_id.strip())
    )


def _list_value(text: str, key: str) -> list[str]:
    inline = re.search(rf"(?m)^\s*{re.escape(key)}:\s*\[(.*?)\]\s*$", text)
    if inline:
        return [
            item.strip().strip("'\"")
            for item in inline.group(1).split(",")
            if item.strip()
        ]
    values: list[str] = []
    in_block = False
    base_indent = 0
    for line in text.splitlines():
        if re.match(rf"^\s*{re.escape(key)}:\s*$", line):
            in_block = True
            base_indent = len(line) - len(line.lstrip())
            continue
        if not in_block or not line.strip():
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if indent <= base_indent and not stripped.startswith("-"):
            break
        if stripped.startswith("-"):
            value = stripped[1:].strip().strip("'\"")
            if value:
                values.append(value)
    return values


def _is_protagonist_identity(path_stem: str, character_id: str, role: str) -> bool:
    normalized_role = role.strip().lower()
    return (
        "protagonist" in path_stem.lower()
        or "protagonist" in character_id.lower()
        or normalized_role.startswith("protagonist")
        or normalized_role.startswith("主角")
    )


def _add_alias(aliases: set[str], value: str) -> None:
    normalized = str(value or "").strip()
    if not normalized:
        return
    aliases.add(normalized)
    slug = character_slug(normalized)
    if slug:
        aliases.add(slug)


__all__ = [
    "character_field_value",
    "character_slug",
    "formal_character_aliases",
    "formal_character_promotion_manifests",
    "is_formal_character",
    "read_character_text",
]
