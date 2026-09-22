"""Materialize a small planning-derived asset set without legacy review tasks."""

from __future__ import annotations

import json
from pathlib import Path

from literary_engineering_studio_engine.public.literary import character_slug
from literary_engineering_studio_engine.public.projects import atomic_write_batch


def ensure_lean_planning_assets(project_root: Path) -> dict[str, int]:
    root = project_root.expanduser().resolve()
    plan_path = root / "plot" / "lean_project_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    characters = plan.get("characters") or []
    world_facts = plan.get("world_facts") or []
    writes: dict[Path, str] = {}
    for character in characters:
        name = str(character["name"])
        slug = character_slug(name)
        if not slug:
            raise ValueError(f"invalid character name in lean plan: {name!r}")
        path = root / "characters" / f"{slug}.yaml"
        if path.exists():
            continue
        writes[path] = _character_stub(slug, character)
    world_path = root / "canon" / "world_rules.yaml"
    if world_facts and (
        not world_path.exists()
        or world_path.read_text(encoding="utf-8").strip()
        == "rules: []\nconstraints: []\nopen_questions: []"
    ):
        writes[world_path] = _world_stub(world_facts)
    atomic_write_batch(writes)
    return {
        "characters_created": sum(path.parent == root / "characters" for path in writes),
        "world_rules_created": int(world_path in writes),
    }


def _character_stub(slug: str, character: dict[str, object]) -> str:
    return "\n".join([
            f"character_id: {_scalar(slug)}",
            f"name: {_scalar(character['name'])}",
            f"role: {_scalar(character['role'])}",
            f"importance: {character['importance']}",
            "identity:",
            f"  background: {_scalar(character['background'])}",
            "bdi:",
            f"  desire: {_scalar([character['desire']])}",
            "state:",
            "  known_facts: []",
            "",
        ])


def _world_stub(world_facts: list[object]) -> str:
    return "\n".join([
            f"rules: {_scalar(world_facts)}",
            "constraints: []",
            "open_questions: []",
            "",
        ])


def _scalar(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


__all__ = ["ensure_lean_planning_assets"]
