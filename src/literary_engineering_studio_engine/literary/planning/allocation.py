"""Pure allocation formulas for long-form word budgets."""

from __future__ import annotations

import re

from .common import GENRE_PRESETS

def _preset_for(genre: str) -> tuple[str, dict[str, object]]:
    normalized = str(genre or "").strip().lower()
    for key, preset in GENRE_PRESETS.items():
        if normalized in preset["aliases"]:
            return key, preset
    return "general", GENRE_PRESETS["general"]

def _distribute_words(target_words: int, volumes: int) -> list[int]:
    if volumes <= 1:
        return [target_words]
    weights = [0.9 + 0.2 * (index / max(volumes - 1, 1)) for index in range(volumes)]
    total = sum(weights)
    values = [round(target_words * weight / total) for weight in weights]
    drift = target_words - sum(values)
    values[-1] += drift
    return values

def _infer_volumes(project_text: str, target_words: int) -> int:
    match = re.search(r"(?m)^[ \t]*volumes:[ \t]*(\d+)", project_text)
    if match:
        value = int(match.group(1))
        if value > 0:
            return value
    if target_words >= 400000:
        return 5
    if target_words >= 250000:
        return 3
    return 1

def _volume_budget(index: int, words: int, preset: dict[str, object]) -> dict[str, object]:
    chapter_count = max(round(words / int(preset["chapter_words"])), 1)
    scene_count = max(round(words / int(preset["scene_words"])), chapter_count * int(preset["scenes_per_chapter_min"]))
    min_scenes = chapter_count * int(preset["scenes_per_chapter_min"])
    max_scenes = chapter_count * int(preset["scenes_per_chapter_max"])
    scene_count = min(max(scene_count, min_scenes), max_scenes)
    ratios = {
        "mainline": float(preset["mainline_ratio"]),
        "relationship": float(preset["relationship_ratio"]),
        "world_or_information": float(preset["world_info_ratio"]),
        "consequence": float(preset["consequence_ratio"]),
        "breath_or_transition": float(preset["breath_ratio"]),
    }
    scene_load = {key: max(round(scene_count * ratio), 1) for key, ratio in ratios.items()}
    return {
        "volume_id": f"volume_{index:02d}",
        "target_words": words,
        "chapter_count": chapter_count,
        "scene_count": scene_count,
        "avg_chapter_words": round(words / chapter_count),
        "avg_scene_words": round(words / scene_count),
        "scene_load": scene_load,
        "required_turning_points": [
            "opening_hook",
            "first_commitment",
            "midpoint_reversal",
            "cost_or_failure",
            "volume_crisis",
            "payoff_and_next_hook",
        ],
    }

def _chapter_budgets(volume_budgets: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    chapter_index = 1
    for volume in volume_budgets:
        chapter_words = _distribute_words(int(volume["target_words"]), int(volume["chapter_count"]))
        scene_counts = _distribute_counts(int(volume["scene_count"]), int(volume["chapter_count"]))
        for offset, words in enumerate(chapter_words):
            scene_count = scene_counts[offset]
            rows.append(
                {
                    "chapter_id": f"chapter_{chapter_index:04d}",
                    "volume_id": volume["volume_id"],
                    "target_words": words,
                    "scene_count": scene_count,
                    "avg_scene_words": round(words / max(scene_count, 1)),
                    "scene_load": volume["scene_load"],
                    "required_functions": [
                        "mainline_action",
                        "relationship_pressure",
                        "information_release",
                        "consequence_chain",
                        "setup_or_payoff",
                    ],
                }
            )
            chapter_index += 1
    return rows

def _distribute_counts(total: int, count: int) -> list[int]:
    if count <= 0:
        return []
    base = total // count
    remainder = total % count
    return [base + (1 if index < remainder else 0) for index in range(count)]
