"""Formal candidate-asset requirements for named scene participants.

Scene prose may introduce a named participant before that person has a formal
character file.  This module keeps that fact inside the candidate-asset route
instead of letting the prose task silently bypass the new-character gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .platform_agent_tasks import write_platform_asset_creation_task


@dataclass(frozen=True)
class SceneCharacterAssetRequirement:
    """One stable candidate character asset required by a scene."""

    name: str
    candidate_id: str
    scene_path: Path
    candidate_path: Path
    report_path: Path
    task_path: Path
    completion_path: Path

    def as_dict(self, root: Path) -> dict[str, str]:
        return {
            "name": self.name,
            "candidate_id": self.candidate_id,
            "candidate_path": _rel(self.candidate_path, root),
            "report_path": _rel(self.report_path, root),
            "task_path": _rel(self.task_path, root),
            "completion_path": _rel(self.completion_path, root),
            "formal_character_path": f"characters/{self.candidate_id}.yaml",
        }


def scene_character_asset_requirements(project_root: Path, scene_path: Path) -> list[SceneCharacterAssetRequirement]:
    """Return candidate assets needed for declared, non-formal participants.

    ``participants`` is intentionally treated conservatively: an explicitly
    named participant may affect future causality, so it receives a candidate
    asset rather than being guessed as a disposable extra.  Truly incidental
    people should not be listed in that field and can use the existing
    ``ephemeral_only`` register path.
    """

    root = project_root.resolve()
    resolved_scene = scene_path if scene_path.is_absolute() else root / scene_path
    scene_text = _read(resolved_scene)
    aliases = _formal_character_aliases(root)
    scene_id = _scene_id(resolved_scene, scene_text)
    requirements: list[SceneCharacterAssetRequirement] = []
    used_ids: set[str] = set()
    for name in _list_value(scene_text, "participants"):
        normalized = name.strip()
        if not normalized or normalized in aliases:
            continue
        candidate_id = _stable_candidate_id(scene_id, normalized, used_ids)
        candidate = root / "characters" / "candidates" / f"{candidate_id}.json"
        requirements.append(
            SceneCharacterAssetRequirement(
                name=normalized,
                candidate_id=candidate_id,
                scene_path=resolved_scene,
                candidate_path=candidate,
                report_path=candidate.with_suffix(".md"),
                task_path=candidate.with_suffix(".agent_tasks.md"),
                completion_path=candidate.with_suffix(".agent_completion.json"),
            )
        )
    return requirements


def ensure_scene_character_asset_tasks(project_root: Path, scene_path: Path) -> list[SceneCharacterAssetRequirement]:
    """Emit creation sidecars for missing named participants, without promotion."""

    root = project_root.resolve()
    requirements = scene_character_asset_requirements(root, scene_path)
    for requirement in requirements:
        if requirement.task_path.exists():
            continue
        write_platform_asset_creation_task(
            root,
            asset_type="character",
            target_id=requirement.candidate_id,
            source=requirement.scene_path,
            candidate_path=requirement.candidate_path,
            report_path=requirement.report_path,
            brief=(
                f"为场景 `{_rel(requirement.scene_path, root)}` 的命名参与者“{requirement.name}”建立候选角色档案。"
                "只依据该场景、现有 canon、人物和剧情材料；背景故事必须作为隐性行为因果，"
                "不得直接改写正式 characters 或 canon。"
            ),
        )
    return requirements


def _formal_character_aliases(root: Path) -> set[str]:
    aliases: set[str] = set()
    characters = root / "characters"
    for path in sorted([*characters.glob("*.yaml"), *characters.glob("*.yml")]):
        if path.name.startswith("_"):
            continue
        text = _read(path)
        aliases.add(path.stem)
        for key in ("character_id", "name"):
            value = _field_value(text, key)
            if value:
                aliases.add(value)
    return aliases


def _scene_id(path: Path, text: str) -> str:
    return _field_value(text, "scene_id") or path.stem


def _stable_candidate_id(scene_id: str, name: str, used_ids: set[str]) -> str:
    base = _slug(f"{scene_id}-{name}")[:72] or "scene-character"
    candidate_id = base
    index = 2
    while candidate_id in used_ids:
        candidate_id = f"{base}-{index}"
        index += 1
    used_ids.add(candidate_id)
    return candidate_id


def _list_value(text: str, key: str) -> list[str]:
    inline = re.search(rf"(?m)^\s*{re.escape(key)}:\s*\[(.*?)\]\s*$", text)
    if inline:
        return [item.strip().strip("'\"") for item in inline.group(1).split(",") if item.strip()]
    values: list[str] = []
    in_block = False
    base_indent = 0
    for line in text.splitlines():
        if re.match(rf"^\s*{re.escape(key)}:\s*$", line):
            in_block = True
            base_indent = len(line) - len(line.lstrip())
            continue
        if not in_block:
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped and indent <= base_indent and not stripped.startswith("-"):
            break
        if stripped.startswith("-"):
            value = stripped[1:].strip().strip("'\"")
            if value:
                values.append(value)
    return values


def _field_value(text: str, key: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(.+?)\s*$", text)
    return match.group(1).strip().strip("'\"") if match else ""


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
