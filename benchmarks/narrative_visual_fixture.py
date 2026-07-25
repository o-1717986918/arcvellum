"""Materialize deterministic, graph-rich projects for browser visual checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .narrative_scale import SCENES_PER_CHAPTER, build_scale_library


FIXTURE_SCHEMA = "arcvellum/narrative-visual-fixture/v1"


def materialize_narrative_visual_fixture(
    target: Path,
    scene_count: int,
) -> dict[str, Any]:
    """Create a disposable work project without overwriting existing content."""

    count = int(scene_count)
    if count < 1:
        raise ValueError("scene_count must be positive")
    root = target.expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"visual fixture target is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    library = build_scale_library(count)
    sections = library["sections"]
    promoted_count = max(1, count // 10)
    _write_project(root, count)
    _write_characters(root, sections["characters"])
    _write_scenes(root, sections["scenes"], promoted_count)
    _write_branches(root, sections["branches"])
    _write_reviews(root, sections["reviews"])
    _write_canon_patches(root, count)
    _write_rhythm_plan(root, sections["scenes"])
    report = {
        "schema": FIXTURE_SCHEMA,
        "project_root": str(root),
        "scene_count": count,
        "chapter_count": (count + SCENES_PER_CHAPTER - 1) // SCENES_PER_CHAPTER,
        "character_count": len(sections["characters"]),
        "branch_count": len(sections["branches"]),
        "review_count": len(sections["reviews"]),
        "promoted_scene_count": promoted_count,
    }
    _write_json(root / ".arcvellum-visual-fixture.json", report)
    return report


def _write_project(root: Path, scene_count: int) -> None:
    root.joinpath("project.yaml").write_text(
        "\n".join(
            [
                "project:",
                "  title: 星仪规模验收作品",
                "  type: novel",
                "  status: drafting",
                "  language: zh-CN",
                f"  target_length: {scene_count * 1400}",
                "creative_brief:",
                "  premise: 一座记忆城市沿着失序时间重新发现自己的历史。",
                "  genre: speculative-fiction",
                "",
            ]
        ),
        encoding="utf-8",
    )
    canon = root / "canon"
    canon.mkdir()
    canon.joinpath("world_rules.yaml").write_text(
        "title: 记忆城市基本规则\nrules:\n  - 记忆只能被交换，不能凭空创造。\n  - 每次改写历史都会留下可追踪证据。\n",
        encoding="utf-8",
    )


def _write_characters(root: Path, characters: list[dict[str, Any]]) -> None:
    folder = root / "characters"
    folder.mkdir()
    for character in characters:
        character_id = str(character["id"])
        aliases = "\n".join(f"  - {item}" for item in character.get("aliases", []))
        folder.joinpath(f"{character_id}.yaml").write_text(
            "\n".join(
                [
                    f"character_id: {character_id}",
                    f"name: {character['title']}",
                    f"importance: {character['status']}",
                    "role: 记忆城市的见证者",
                    "aliases:",
                    aliases or "  []",
                    "background_story:",
                    f"  summary: {character['title']}曾经失去一段无法公开说明的城市记忆。",
                    "bdi:",
                    "  desire:",
                    "    - 找回被篡改的时间顺序",
                    "psychology:",
                    "  fear:",
                    "    - 自己才是历史断裂的原因",
                    "",
                ]
            ),
            encoding="utf-8",
        )


def _write_scenes(
    root: Path,
    scenes: list[dict[str, Any]],
    promoted_count: int,
) -> None:
    folder = root / "scenes"
    drafts = root / "drafts" / "scenes"
    folder.mkdir()
    drafts.mkdir(parents=True)
    for index, scene in enumerate(scenes, 1):
        scene_id = str(scene["id"])
        chapter_id = _fact(scene, "章节")
        participants = [str(item) for item in scene.get("participants", [])]
        participant_lines = "\n".join(f"  - {item}" for item in participants)
        tension = _tension(index)
        folder.joinpath(f"{scene_id}.yaml").write_text(
            "\n".join(
                [
                    f"scene_id: {scene_id}",
                    f"chapter_id: {chapter_id}",
                    f"volume_id: volume_{(index - 1) // 200 + 1:02d}",
                    f"title: {scene['title']}",
                    f"status: {'formal' if index <= promoted_count else 'planned'}",
                    f"word_count_target: {_fact(scene, '目标字数')}",
                    f"timeline_order: {index}",
                    f"spatial_time_gap_before: {1 + (index // SCENES_PER_CHAPTER) % 4 if index % SCENES_PER_CHAPTER == 1 else 0}",
                    "participants:",
                    participant_lines or "  []",
                    "participant_refs:",
                    participant_lines or "  []",
                    f"scene_goal: 让第 {index} 次记忆交换改变下一场的选择。",
                    "reader_experience:",
                    f"  reader_question: 第 {index} 场留下的证据将由谁解释？",
                    f"  promised_reward: 在第 {index + SCENES_PER_CHAPTER} 场前回应这项疑问。",
                    "narrative_rhythm:",
                    f"  rhythm_role: {_rhythm_role(index)}",
                    f"  pace: {_pace(index)}",
                    f"  detail_level: {_detail_level(index)}",
                    "  tension_curve:",
                    f"    entry: {tension[0]}",
                    f"    peak: {tension[1]}",
                    f"    exit: {tension[2]}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        if index <= promoted_count:
            drafts.joinpath(f"{scene_id}.md").write_text(
                f"# {scene['title']}\n\n城市的钟声在第 {index} 次交换后慢了半拍。"
                "记录员没有解释，只把新的证据夹进旧档案。\n\n"
                "有人因此改变了选择，代价则被留给下一场。\n",
                encoding="utf-8",
            )


def _write_branches(root: Path, branches: list[dict[str, Any]]) -> None:
    for branch in branches:
        scene_id = str(branch["id"])
        folder = root / "branches" / scene_id
        folder.mkdir(parents=True)
        options = [
            {
                "branch_id": str(item["id"]),
                "title": str(item["label"]),
                "premise": str(item["summary"]),
                "risks": ["关系压力增加"] if item["id"] == "A" else ["行动窗口缩短"],
            }
            for item in branch["options"]
        ]
        _write_json(
            folder / "branch_manifest.json",
            {
                "scene_id": scene_id,
                "recommended_branch": "A",
                "branches": options,
            },
        )
        folder.joinpath("branch_selection.md").write_text(
            "selected_branch: A\n\n选择理由：推进主线，同时保留未解决的关系压力。\n",
            encoding="utf-8",
        )


def _write_reviews(root: Path, reviews: list[dict[str, Any]]) -> None:
    folder = root / "reviews" / "agent"
    folder.mkdir(parents=True)
    for review in reviews:
        scene_id = str(review["id"]).removesuffix("-review")
        _write_json(
            folder / f"{scene_id}_scene_review.json",
            {
                "scene_id": scene_id,
                "conclusion": str(review["status"]),
                "summary": "场景因果成立，保留一项节奏调整建议。",
            },
        )


def _write_canon_patches(root: Path, scene_count: int) -> None:
    folder = root / "canon" / "patches"
    folder.mkdir()
    for index in range(17, scene_count + 1, 17):
        scene_id = f"scene_{index:04d}"
        _write_json(
            folder / f"{scene_id}_canon_patch.json",
            {
                "scene_id": scene_id,
                "canon_change": True,
                "applied": index % 34 == 0,
                "source": f"drafts/scenes/{scene_id}.md",
                "items": [{"kind": "memory-law", "summary": f"第 {index} 场确认了一条记忆交换边界。"}],
            },
        )


def _write_rhythm_plan(root: Path, scenes: list[dict[str, Any]]) -> None:
    entries = {}
    for index, scene in enumerate(scenes, 1):
        entry, peak, exit_value = _tension(index)
        entries[str(scene["id"])] = {
            "pace": _pace(index),
            "rhythm_role": _rhythm_role(index),
            "scene_function": ["推进因果", "改变读者预期"],
            "tension_curve": {"entry": entry, "peak": peak, "exit": exit_value},
            "detail_level": _detail_level(index),
            "spatial_time_gap_before": 1 + (index // SCENES_PER_CHAPTER) % 4
            if index % SCENES_PER_CHAPTER == 1
            else 0,
        }
    _write_json(
        root / "plot" / "rhythm_plan.json",
        {
            "schema": "literary-engineering-workbench/rhythm-plan/v0.2",
            "revision": 1,
            "book_profile": {
                "profile_id": "layered",
                "arc": {"opening": 2, "ascent": 4, "midpoint": 5, "crisis": 3, "finale": 5},
            },
            "scenes": entries,
        },
    )


def _fact(scene: dict[str, Any], label: str) -> str:
    for fact in scene.get("facts", []):
        if isinstance(fact, dict) and fact.get("label") == label:
            return str(fact.get("value") or "")
    return ""


def _tension(index: int) -> tuple[int, int, int]:
    entry = 1 + index % 4
    peak = min(5, entry + 1 + (index // SCENES_PER_CHAPTER) % 2)
    return entry, peak, max(1, peak - 1 - index % 2)


def _rhythm_role(index: int) -> str:
    return ("transition", "information", "conflict", "aftermath", "turn")[index % 5]


def _pace(index: int) -> str:
    return ("slow", "balanced", "fast", "fast_to_slow")[index % 4]


def _detail_level(index: int) -> str:
    return "set_piece" if index % 13 == 0 else "expanded" if index % 7 == 0 else "standard"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
