"""Materialize a small planning-derived asset set without legacy review tasks."""

from __future__ import annotations

import json
from pathlib import Path

from literary_engineering_studio_engine.public.literary import character_slug
from literary_engineering_studio_engine.public.projects import atomic_write_batch
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


def lean_asset_alignment(project_root: Path) -> dict[str, object]:
    root = project_root.expanduser().resolve()
    plan_path = root / "plot" / "lean_project_plan.json"
    if not plan_path.is_file():
        return {"schema": "arcvellum/lean-asset-alignment/v1", "available": False, "items": []}
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    characters = plan.get("characters") or []
    known_names = _existing_character_names(root)
    items: list[dict[str, object]] = []
    for character in characters:
        name = str(character["name"])
        slug = character_slug(name)
        if not slug:
            raise ValueError(f"invalid character name in lean plan: {name!r}")
        path = root / "characters" / f"{slug}.yaml"
        if path.is_file():
            actual = _character_identity(path)
            status = "matched" if actual == (slug, name) else "path_conflict"
        else:
            status = "identity_mismatch" if known_names.get(name) else "missing"
        items.append({
            "asset_id": f"character:{slug}", "name": name, "status": status,
            "matching_asset_ids": known_names.get(name, []),
        })
    world_facts = plan.get("world_facts") or []
    if world_facts:
        path = root / "canon" / "world_rules.yaml"
        items.append({
            "asset_id": "world-rule:world_rules", "status": "present" if path.is_file() else "missing",
            "matching_asset_ids": [],
        })
    return {"schema": "arcvellum/lean-asset-alignment/v1", "available": True, "items": items}


def _existing_character_names(root: Path) -> dict[str, list[str]]:
    names: dict[str, list[str]] = {}
    for path in sorted((root / "characters").glob("*.yaml")):
        identity = _character_identity(path)
        if identity is not None:
            names.setdefault(identity[1], []).append(f"character:{path.stem}")
    return names


def _character_identity(path: Path) -> tuple[str, str] | None:
    try:
        payload = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except (OSError, YAMLError):
        return None
    if not isinstance(payload, dict):
        return None
    return str(payload.get("character_id") or ""), str(payload.get("name") or "")


def ensure_lean_planning_assets(
    project_root: Path, *, target_asset_id: str | None = None,
) -> dict[str, int]:
    root = project_root.expanduser().resolve()
    plan_path = root / "plot" / "lean_project_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    characters = plan.get("characters") or []
    world_facts = plan.get("world_facts") or []
    _validate_planned_target(characters, target_asset_id)
    alignment = {item["asset_id"]: item for item in lean_asset_alignment(root)["items"]}
    writes = _planned_character_writes(root, characters, target_asset_id, alignment)
    world_path = root / "canon" / "world_rules.yaml"
    if world_facts and target_asset_id in (None, "world-rule:world_rules") and _world_needs_stub(world_path):
        writes[world_path] = _world_stub(world_facts)
    atomic_write_batch(writes)
    return {
        "characters_created": sum(path.parent == root / "characters" for path in writes),
        "world_rules_created": int(world_path in writes),
    }


def _validate_planned_target(characters: list[dict[str, object]], target_asset_id: str | None) -> None:
    planned_ids = {f"character:{character_slug(str(row['name']))}" for row in characters}
    if target_asset_id is not None and target_asset_id not in planned_ids | {"world-rule:world_rules"}:
        raise ValueError("asset is not in the lean plan; create it through the owner archive service")


def _planned_character_writes(
    root: Path, characters: list[dict[str, object]], target_asset_id: str | None,
    alignment: dict[str, dict[str, object]],
) -> dict[Path, str]:
    writes: dict[Path, str] = {}
    for character in characters:
        name = str(character["name"])
        slug = character_slug(name)
        if not slug:
            raise ValueError(f"invalid character name in lean plan: {name!r}")
        asset_id = f"character:{slug}"
        if target_asset_id is not None and target_asset_id != asset_id:
            continue
        if alignment[asset_id]["status"] == "missing":
            writes[root / "characters" / f"{slug}.yaml"] = _character_stub(slug, character)
    return writes


def _world_needs_stub(path: Path) -> bool:
    return not path.exists() or path.read_text(encoding="utf-8").strip() == (
        "rules: []\nconstraints: []\nopen_questions: []"
    )


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


__all__ = ["ensure_lean_planning_assets", "lean_asset_alignment"]
