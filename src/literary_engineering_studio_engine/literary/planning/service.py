"""Orchestrates long-form budget generation without owning formulas or rendering."""

from __future__ import annotations

import json
from pathlib import Path

from literary_engineering_studio_engine.foundation.text_counts import CHINESE_CONTENT_COUNT_UNIT, MACHINE_NONSPACE_COUNT_UNIT
from .common import (
    WordBudgetResult,
    _now,
    _project_genre,
    _project_int,
    _read,
    _resolve,
    _resolve_output,
)
from .inventory import _budget_issues, _outline_inventory, _scene_inventory_binding
from .allocation import _chapter_budgets, _distribute_counts, _distribute_words, _infer_volumes, _preset_for, _volume_budget
from .rendering import (
    _render_markdown,
    _write_agent_tasks,
    _write_chapter_obligation_plan_tasks,
    _write_scene_inventory_agent_tasks,
)

def build_word_budget(
    project_root: Path,
    *,
    target_words: int = 0,
    volumes: int = 0,
    target_chapters: int = 0,
    target_scenes: int = 0,
    genre: str = "",
    time_span: str = "",
    outline: Path | None = None,
    output: Path | None = None,
    json_output: Path | None = None,
    agent_tasks_output: Path | None = None,
) -> WordBudgetResult:
    root = project_root.resolve()
    payload = calculate_word_budget(
        root,
        target_words=target_words,
        volumes=volumes,
        target_chapters=target_chapters,
        target_scenes=target_scenes,
        genre=genre,
        time_span=time_span,
        outline=outline,
    )
    payload = {
        "generated_at": _now(),
        "project_root": str(root),
        **payload,
        "candidate_outputs": _candidate_outputs(),
        "standard_chain": {
            "must_run_before": ["agent-create-outline", "outline-lab", "scene-development", "generate-scene"],
            "platform_agent_required_for": [
                "budgeted outline expansion",
                "volume/chapter/scene creative allocation",
                "narrative-load review",
                "chapter obligation and reader-experience planning",
                "approval before promotion",
            ],
        },
    }
    totals = payload["totals"]
    outline_path = _resolve(root, outline) if outline else root / "plot" / "outline.md"
    markdown_path = _resolve_output(root, output, "plot", "word_budget", "word_budget.md")
    json_path = _resolve_output(root, json_output, "plot", "word_budget", "word_budget.json")
    task_path = _resolve_output(root, agent_tasks_output, "plot", "word_budget", "word_budget.agent_tasks.md")
    scene_task_path = root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md"
    chapter_obligation_task_path = root / "plot" / "chapter_obligations" / "chapter_obligations.agent_tasks.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.parent.mkdir(parents=True, exist_ok=True)
    (root / "reviews" / "word_budget").mkdir(parents=True, exist_ok=True)
    (root / "plot" / "candidates" / "outlines").mkdir(parents=True, exist_ok=True)
    (root / "plot" / "candidates" / "scenes").mkdir(parents=True, exist_ok=True)
    (root / "plot" / "chapter_obligations").mkdir(parents=True, exist_ok=True)

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown(root, payload, json_path), encoding="utf-8")
    _write_agent_tasks(root, markdown_path, json_path, outline_path, task_path, payload)
    _write_scene_inventory_agent_tasks(root, markdown_path, json_path, outline_path, scene_task_path, payload)
    _write_chapter_obligation_plan_tasks(root, markdown_path, json_path, outline_path, chapter_obligation_task_path, payload)

    return WordBudgetResult(
        project_root=root,
        markdown_path=markdown_path,
        json_path=json_path,
        agent_tasks_path=task_path,
        scene_inventory_tasks_path=scene_task_path,
        chapter_obligation_tasks_path=chapter_obligation_task_path,
        target_words=int(totals["target_words"]),
        volume_count=int(totals["volume_count"]),
        chapter_count=int(totals["chapter_count"]),
        scene_count=int(totals["scene_count"]),
        status=str(payload["status"]),
        issue_count=len(payload["issues"]),
    )


def calculate_word_budget(
    project_root: Path,
    *,
    target_words: int = 0,
    volumes: int = 0,
    target_chapters: int = 0,
    target_scenes: int = 0,
    genre: str = "",
    time_span: str = "",
    outline: Path | None = None,
) -> dict[str, object]:
    """Calculate a budget without creating old route tasks or project files."""
    root = project_root.resolve()
    if not (root / "project.yaml").exists():
        raise FileNotFoundError(f"work project not found: {root}")
    project_text = _read(root / "project.yaml")
    contract = _resolve_budget_contract(
        project_text, target_words, volumes, target_chapters, target_scenes,
    )
    preset_key, preset = _preset_for(genre or _project_genre(project_text))
    volume_budgets = _volume_budgets(contract, preset)
    chapter_budgets = _chapter_budgets(volume_budgets)
    totals = _budget_totals(contract, volume_budgets)
    outline_path = _resolve(root, outline) if outline else root / "plot" / "outline.md"
    inventory = _outline_inventory(root, outline_path)
    scene_inventory_binding = _scene_inventory_binding(root, chapter_budgets)
    issues = _budget_issues(totals, inventory, scene_inventory_binding)
    status = "pass" if not [issue for issue in issues if issue["severity"] in {"high", "medium"}] else "needs_expansion"

    return {
        "schema": "literary-engineering-workbench/word-budget/v1",
        "target": {
            "target_words": contract["target_words"],
            "target_chinese_chars": contract["target_words"],
            "count_unit": CHINESE_CONTENT_COUNT_UNIT,
            "volumes": contract["volumes"],
            "genre": preset_key,
            "genre_label": preset["label"],
            "time_span": time_span,
            "target_chapters": contract["target_chapters"],
            "target_scenes": contract["target_scenes"],
            "structure_source": contract["structure_source"],
        },
        "preset": {key: value for key, value in preset.items() if key != "aliases"},
        "totals": totals,
        "counting_policy": {
            "formal_target_unit": CHINESE_CONTENT_COUNT_UNIT,
            "machine_diagnostic_unit": MACHINE_NONSPACE_COUNT_UNIT,
            "rule": "User-facing word budgets are interpreted as cleaned Chinese deliverable characters, including Chinese punctuation.",
            "mapping": "Machine non-whitespace counts are retained only as diagnostics because markdown traces, paths, ASCII labels, and workflow residue can inflate them.",
        },
        "volume_budgets": volume_budgets,
        "chapter_budgets": chapter_budgets,
        "outline_inventory": inventory,
        "scene_inventory_binding": scene_inventory_binding,
        "issues": issues,
        "status": status,
    }


def _resolve_budget_contract(
    project_text: str,
    target_words: int,
    volumes: int,
    target_chapters: int,
    target_scenes: int,
) -> dict[str, int | str]:
    target = int(target_words or _project_int(project_text, "target_length") or 100000)
    if target <= 0:
        raise ValueError("target Chinese-content characters must be positive")
    volume_count = max(int(volumes or _infer_volumes(project_text, target)), 1)
    chapters = max(int(target_chapters or _project_int(project_text, "target_chapters")), 0)
    scenes = max(int(target_scenes or _project_int(project_text, "target_scenes")), 0)
    _validate_structure_counts(volume_count, chapters, scenes)
    return {
        "target_words": target, "volumes": volume_count,
        "target_chapters": chapters, "target_scenes": scenes,
        "structure_source": "explicit_project_contract" if chapters or scenes else "genre_inference",
    }


def _validate_structure_counts(volume_count: int, chapters: int, scenes: int) -> None:
    if chapters and chapters < volume_count:
        raise ValueError("target chapters cannot be fewer than volumes")
    if scenes and scenes < volume_count:
        raise ValueError("target scenes cannot be fewer than volumes")
    if chapters and scenes and scenes < chapters:
        raise ValueError("target scenes cannot be fewer than target chapters")


def _volume_budgets(contract: dict[str, int | str], preset: dict[str, object]) -> list[dict[str, object]]:
    volume_count = int(contract["volumes"])
    volume_words = _distribute_words(int(contract["target_words"]), volume_count)
    chapters = int(contract["target_chapters"])
    scenes = int(contract["target_scenes"])
    chapter_counts = _distribute_counts(chapters, volume_count) if chapters else [0] * volume_count
    scene_counts = _distribute_counts(scenes, volume_count) if scenes else [0] * volume_count
    return [
        _volume_budget(index + 1, words, preset,
                       target_chapters=chapter_counts[index], target_scenes=scene_counts[index])
        for index, words in enumerate(volume_words)
    ]


def _budget_totals(
    contract: dict[str, int | str], volume_budgets: list[dict[str, object]]
) -> dict[str, object]:
    target = int(contract["target_words"])
    chapters = sum(int(item["chapter_count"]) for item in volume_budgets)
    scenes = sum(int(item["scene_count"]) for item in volume_budgets)
    return {
        "target_words": target, "target_chinese_chars": target,
        "count_unit": CHINESE_CONTENT_COUNT_UNIT,
        "volume_count": int(contract["volumes"]),
        "chapter_count": chapters, "scene_count": scenes,
        "avg_chapter_words": round(target / max(chapters, 1)),
        "avg_scene_words": round(target / max(scenes, 1)),
    }


def _candidate_outputs() -> dict[str, str]:
    return {
        "budgeted_outline_candidate": "plot/candidates/outlines/word_budget_expansion.md",
        "budget_review": "reviews/word_budget/word_budget_review.md",
        "budget_review_contract": "reviews/word_budget/word_budget_review.json",
        "scene_inventory_expansion": "plot/candidates/scenes/word_budget_scene_inventory.md",
        "scene_inventory_review": "reviews/word_budget/scene_inventory_review.md",
        "scene_inventory_review_contract": "reviews/word_budget/scene_inventory_review.json",
        "chapter_obligations": "plot/chapter_obligations/",
        "chapter_obligation_review": "reviews/word_budget/chapter_obligation_review.md",
        "chapter_obligation_review_contract": "reviews/word_budget/chapter_obligation_review.json",
    }
