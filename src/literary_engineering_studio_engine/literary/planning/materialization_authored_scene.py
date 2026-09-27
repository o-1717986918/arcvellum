"""Check scene facts before adopting a scene authored ahead of lean planning."""

from __future__ import annotations

from pathlib import Path

from ..scene.facts import load_scene_facts


def authored_scene_conflicts(path: Path, scene: dict[str, object]) -> list[str]:
    facts = load_scene_facts(path)
    expected = {
        "scene_id": str(scene["scene_id"]),
        "chapter_id": str(scene["chapter_id"]),
    }
    conflicts = [
        f"{path.name} {key} differs ({getattr(facts, key)!r} != {value!r})"
        for key, value in expected.items()
        if getattr(facts, key) != value
    ]
    for key, value in (("volume_id", scene["volume_id"]), ("title", scene["name"])):
        actual = getattr(facts, key)
        if actual and actual != value:
            conflicts.append(f"{path.name} {key} differs ({actual!r} != {value!r})")
    if facts.word_count_target and facts.word_count_target != int(scene["target_chars"]):
        conflicts.append(f"{path.name} word_count_target differs from the planned scene")
    if facts.participants and set(facts.participants) != set(scene["participants"]):
        conflicts.append(f"{path.name} participants differ from the planned scene")
    return conflicts


__all__ = ["authored_scene_conflicts"]
