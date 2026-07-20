"""Long-form word budget and narrative inventory planning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .agent_tasks import agent_task_completion_status, write_agent_tasks
from .draft_text import (
    count_delivery_chars,
    count_delivery_chinese_content_chars,
    delivery_char_count_mapping,
    final_body_from_draft_path,
)
from .text_counts import CHINESE_CONTENT_COUNT_UNIT, MACHINE_NONSPACE_COUNT_UNIT


GENRE_PRESETS = {
    "general": {
        "label": "通用长篇",
        "aliases": {"general", "novel", "通用", "小说", "长篇"},
        "chapter_words": 4000,
        "scene_words": 1400,
        "scenes_per_chapter_min": 2,
        "scenes_per_chapter_max": 4,
        "mainline_ratio": 0.42,
        "relationship_ratio": 0.20,
        "world_info_ratio": 0.13,
        "consequence_ratio": 0.15,
        "breath_ratio": 0.10,
    },
    "mystery": {
        "label": "悬疑/推理",
        "aliases": {"mystery", "suspense", "thriller", "悬疑", "推理", "惊悚"},
        "chapter_words": 3800,
        "scene_words": 1250,
        "scenes_per_chapter_min": 3,
        "scenes_per_chapter_max": 5,
        "mainline_ratio": 0.38,
        "relationship_ratio": 0.17,
        "world_info_ratio": 0.18,
        "consequence_ratio": 0.17,
        "breath_ratio": 0.10,
    },
    "speculative": {
        "label": "科幻/奇幻/玄幻",
        "aliases": {"speculative", "fantasy", "sci-fi", "science-fiction", "科幻", "奇幻", "玄幻"},
        "chapter_words": 4200,
        "scene_words": 1500,
        "scenes_per_chapter_min": 2,
        "scenes_per_chapter_max": 4,
        "mainline_ratio": 0.36,
        "relationship_ratio": 0.16,
        "world_info_ratio": 0.24,
        "consequence_ratio": 0.14,
        "breath_ratio": 0.10,
    },
    "urban": {
        "label": "都市/职场/现实",
        "aliases": {"urban", "workplace", "realist", "都市", "职场", "现实"},
        "chapter_words": 3600,
        "scene_words": 1200,
        "scenes_per_chapter_min": 3,
        "scenes_per_chapter_max": 5,
        "mainline_ratio": 0.34,
        "relationship_ratio": 0.26,
        "world_info_ratio": 0.12,
        "consequence_ratio": 0.18,
        "breath_ratio": 0.10,
    },
    "literary": {
        "label": "文学向",
        "aliases": {"literary", "literature", "文学", "严肃文学"},
        "chapter_words": 4500,
        "scene_words": 1600,
        "scenes_per_chapter_min": 2,
        "scenes_per_chapter_max": 4,
        "mainline_ratio": 0.30,
        "relationship_ratio": 0.24,
        "world_info_ratio": 0.10,
        "consequence_ratio": 0.20,
        "breath_ratio": 0.16,
    },
}


@dataclass(frozen=True)
class WordBudgetResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    agent_tasks_path: Path
    scene_inventory_tasks_path: Path
    chapter_obligation_tasks_path: Path
    target_words: int
    volume_count: int
    chapter_count: int
    scene_count: int
    status: str
    issue_count: int


def build_word_budget(
    project_root: Path,
    *,
    target_words: int = 0,
    volumes: int = 0,
    genre: str = "",
    time_span: str = "",
    outline: Path | None = None,
    output: Path | None = None,
    json_output: Path | None = None,
    agent_tasks_output: Path | None = None,
) -> WordBudgetResult:
    root = project_root.resolve()
    if not (root / "project.yaml").exists():
        raise FileNotFoundError(f"work project not found: {root}")
    project_text = _read(root / "project.yaml")
    resolved_target = int(target_words or _project_int(project_text, "target_length") or 100000)
    if resolved_target <= 0:
        raise ValueError("target Chinese-content characters must be positive")
    volume_count = max(int(volumes or _infer_volumes(project_text, resolved_target)), 1)
    preset_key, preset = _preset_for(genre or _project_genre(project_text))
    volume_words = _distribute_words(resolved_target, volume_count)
    volume_budgets = [_volume_budget(index + 1, words, preset) for index, words in enumerate(volume_words)]
    chapter_budgets = _chapter_budgets(volume_budgets)
    totals = {
        "target_words": resolved_target,
        "target_chinese_chars": resolved_target,
        "count_unit": CHINESE_CONTENT_COUNT_UNIT,
        "volume_count": volume_count,
        "chapter_count": sum(item["chapter_count"] for item in volume_budgets),
        "scene_count": sum(item["scene_count"] for item in volume_budgets),
        "avg_chapter_words": round(resolved_target / max(sum(item["chapter_count"] for item in volume_budgets), 1)),
        "avg_scene_words": round(resolved_target / max(sum(item["scene_count"] for item in volume_budgets), 1)),
    }
    outline_path = _resolve(root, outline) if outline else root / "plot" / "outline.md"
    inventory = _outline_inventory(root, outline_path)
    scene_inventory_binding = _scene_inventory_binding(root, chapter_budgets)
    issues = _budget_issues(totals, inventory, scene_inventory_binding)
    candidate_outputs = {
        "budgeted_outline_candidate": "plot/candidates/outlines/word_budget_expansion.md",
        "budget_review": "reviews/word_budget/word_budget_review.md",
        "scene_inventory_expansion": "plot/candidates/scenes/word_budget_scene_inventory.md",
        "scene_inventory_review": "reviews/word_budget/scene_inventory_review.md",
        "chapter_obligations": "plot/chapter_obligations/",
        "chapter_obligation_review": "reviews/word_budget/chapter_obligation_review.md",
    }
    status = "pass" if not [issue for issue in issues if issue["severity"] in {"high", "medium"}] else "needs_expansion"

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

    payload = {
        "schema": "literary-engineering-workbench/word-budget/v1",
        "generated_at": _now(),
        "project_root": str(root),
        "target": {
            "target_words": resolved_target,
            "target_chinese_chars": resolved_target,
            "count_unit": CHINESE_CONTENT_COUNT_UNIT,
            "volumes": volume_count,
            "genre": preset_key,
            "genre_label": preset["label"],
            "time_span": time_span,
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
        "candidate_outputs": candidate_outputs,
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
        target_words=resolved_target,
        volume_count=volume_count,
        chapter_count=totals["chapter_count"],
        scene_count=totals["scene_count"],
        status=status,
        issue_count=len(issues),
    )


def load_word_budget_summary(root: Path) -> dict[str, object]:
    path = root / "plot" / "word_budget" / "word_budget.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {
        "path": _rel(path, root),
        "status": payload.get("status", ""),
        "target": payload.get("target", {}),
        "totals": payload.get("totals", {}),
        "chapter_budgets": payload.get("chapter_budgets", []),
        "scene_inventory_binding": payload.get("scene_inventory_binding", {}),
        "issues": payload.get("issues", []),
    }


def scene_word_budget_contract(root: Path, scene_path: Path) -> dict[str, object]:
    """Return the hard per-scene word-budget contract for formal generation/review."""

    root = root.resolve()
    scene_path = scene_path if scene_path.is_absolute() else root / scene_path
    scene_text = _read(scene_path)
    scene_id = _scalar(scene_text, "scene_id") or scene_path.stem
    chapter_id = _scalar(scene_text, "chapter_id") or "unassigned"
    scene_yaml_target = _scene_word_count_target(scene_text)
    scene_yaml_min = _to_int(_scalar(scene_text, "word_count_min"))
    scene_yaml_max = _to_int(_scalar(scene_text, "word_count_max"))
    project_text = _read(root / "project.yaml")
    project_target = int(_project_int(project_text, "target_length") or _project_int(project_text, "target_words") or 0)
    required = project_target >= 100000
    budget_path = root / "plot" / "word_budget" / "word_budget.json"
    base = {
        "schema": "literary-engineering-workbench/scene-word-budget-contract/v1",
        "scene_id": scene_id,
        "chapter_id": chapter_id,
        "required": required,
        "budget_path": _rel(budget_path, root),
        "status": "not_required",
        "message": "word budget is not required for this project scale",
        "count_unit": CHINESE_CONTENT_COUNT_UNIT,
        "machine_count_unit": MACHINE_NONSPACE_COUNT_UNIT,
        "target_words": 0,
        "min_words": 0,
        "max_words": 0,
        "target_chinese_chars": 0,
        "min_chinese_chars": 0,
        "max_chinese_chars": 0,
        "scene_yaml_target_words": scene_yaml_target,
        "scene_yaml_target_chinese_chars": scene_yaml_target,
        "derived_target_words": 0,
        "derived_target_chinese_chars": 0,
        "machine_count_mapping": {},
        "source": "",
        "alignment_status": "",
        "warnings": [],
        "tolerance": {"min_ratio": 0.85, "max_ratio": 1.25},
        "narrative_load": [],
        "budget_status": "",
    }
    if not budget_path.exists():
        if required:
            base.update(
                {
                    "status": "missing",
                    "message": "formal longform scene generation requires plot/word_budget/word_budget.json",
                }
            )
        return base
    payload = _read_json(budget_path)
    if not payload:
        base.update({"status": "invalid", "required": True, "message": "word_budget.json is not valid JSON"})
        return base
    budget_status = str(payload.get("status") or "").strip().lower()
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    totals = payload.get("totals") if isinstance(payload.get("totals"), dict) else {}
    if int(target.get("target_words") or totals.get("target_words") or project_target or 0) >= 100000:
        required = True
    base["required"] = required
    base["budget_status"] = budget_status
    if budget_status == "needs_expansion":
        base.update(
            {
                "status": "needs_expansion",
                "message": "word budget reports needs_expansion; process budget and scene-inventory sidecars before formal generation",
            }
        )
        return base
    chapter_row = _chapter_budget_row(payload, chapter_id)
    if not chapter_row:
        if required:
            base.update(
                {
                    "status": "missing_chapter",
                    "message": f"word budget has no chapter row for {chapter_id}",
                }
            )
        return base
    chapter_target = _to_int(chapter_row.get("target_words"))
    scene_count = max(
        _to_int(chapter_row.get("target_scene_count")),
        _to_int(chapter_row.get("scene_count")),
        len(_scene_ids_for_chapter(root, chapter_id)),
        1,
    )
    derived_target = _to_int(chapter_row.get("avg_scene_words")) or round(chapter_target / max(scene_count, 1))
    target_words = scene_yaml_target or derived_target
    min_words = max(round(target_words * 0.85), 1) if target_words else 0
    max_words = max(round(target_words * 1.25), min_words) if target_words else 0
    if scene_yaml_target:
        min_words = scene_yaml_min or min_words
        max_words = scene_yaml_max or max_words
        if max_words and min_words > max_words:
            base.update(
                {
                    "status": "invalid",
                    "message": "scene.yaml word_count_min is greater than word_count_max",
                    "target_words": target_words,
                    "min_words": min_words,
                    "max_words": max_words,
                    "target_chinese_chars": target_words,
                    "min_chinese_chars": min_words,
                    "max_chinese_chars": max_words,
                    "source": "scene_yaml",
                    "derived_target_words": derived_target,
                    "derived_target_chinese_chars": derived_target,
                }
            )
            return base
    warnings: list[str] = []
    alignment_status = "derived_from_word_budget"
    source = "word_budget"
    if scene_yaml_target:
        source = "scene_yaml"
        if derived_target and (scene_yaml_target < round(derived_target * 0.5) or scene_yaml_target > round(derived_target * 1.8)):
            alignment_status = "manual_override_needs_review"
            warnings.append(
                f"scene.yaml word_count_target={scene_yaml_target} differs sharply from derived chapter average {derived_target}; require word-budget review confirmation"
            )
        else:
            alignment_status = "scene_yaml_aligned"
    narrative_load = chapter_row.get("required_functions") or chapter_row.get("scene_load") or [
        "mainline_action",
        "relationship_pressure",
        "information_release",
        "consequence_chain",
        "setup_or_payoff",
    ]
    if isinstance(narrative_load, dict):
        narrative_load = [str(key) for key, value in narrative_load.items() if _to_int(value) > 0]
    if not isinstance(narrative_load, list):
        narrative_load = [str(narrative_load)]
    base.update(
        {
            "status": "pass" if target_words else "invalid",
            "message": "scene Chinese-content word budget contract is ready" if target_words else "scene target Chinese-content characters could not be computed",
            "target_words": target_words,
            "min_words": min_words,
            "max_words": max_words,
            "target_chinese_chars": target_words,
            "min_chinese_chars": min_words,
            "max_chinese_chars": max_words,
            "scene_yaml_target_words": scene_yaml_target,
            "scene_yaml_target_chinese_chars": scene_yaml_target,
            "derived_target_words": derived_target,
            "derived_target_chinese_chars": derived_target,
            "machine_count_mapping": {
                "target_unit": CHINESE_CONTENT_COUNT_UNIT,
                "machine_unit": MACHINE_NONSPACE_COUNT_UNIT,
                "target_chinese_chars": target_words,
                "rough_expected_machine_chars": target_words,
                "rough_expected_machine_chars_range": [round(target_words * 0.95), round(target_words * 1.15)],
                "baseline_machine_chars_1_to_1_range": [round(target_words * 0.95), round(target_words * 1.15)],
                "mapping_basis": "pre_generation_baseline_1_to_1",
                "note": "Formal gates use Chinese content chars; machine nonspace chars are diagnostic only. This pre-generation range is a rough 1:1 Chinese-prose baseline for UI/platform displays, not a pass/fail threshold.",
            },
            "source": source,
            "alignment_status": alignment_status,
            "warnings": warnings,
            "narrative_load": [str(item) for item in narrative_load if str(item).strip()],
            "chapter_target_words": chapter_target,
            "chapter_scene_count": scene_count,
        }
    )
    return base


def ensure_scene_word_budget_ready(root: Path, scene_path: Path) -> dict[str, object]:
    """Raise when a formal scene has no usable word-budget contract."""

    contract = scene_word_budget_contract(root, scene_path)
    if contract.get("status") == "not_required":
        return contract
    if contract.get("status") == "pass":
        budget_task = root / "plot" / "word_budget" / "word_budget.agent_tasks.md"
        budget_review = root / "reviews" / "word_budget" / "word_budget_review.md"
        completion = agent_task_completion_status(budget_task, root=root)
        if completion.get("complete") is not True:
            raise ValueError(
                "formal scene generation requires the word-budget platform-agent task to be completed before prose: "
                f"{completion.get('message')}"
            )
        if not budget_review.exists():
            raise ValueError(
                "formal scene generation requires reviews/word_budget/word_budget_review.md before prose. "
                "The platform agent must review the word-budget to confirm the target-length to narrative-inventory mapping."
            )
        return contract
    raise ValueError(
        "formal scene generation requires a ready scene word-budget contract: "
        f"{contract.get('message')}. Run word-budget / longform-budget, handle its .agent_tasks.md sidecars, "
        "review the budgeted outline and scene inventory, then retry."
    )


def word_budget_adherence_for_body(root: Path, scene_path: Path, body: str) -> dict[str, object]:
    """Return deterministic cleaned-body word-budget adherence for a scene draft/candidate."""

    contract = scene_word_budget_contract(root, scene_path)
    clean_machine_chars = count_delivery_chars(body)
    clean_chinese_chars = count_delivery_chinese_content_chars(body)
    status = str(contract.get("status") or "")
    target_chinese_chars = _to_int(contract.get("target_chinese_chars") or contract.get("target_words"))
    mapping = delivery_char_count_mapping(body, target_chinese_chars=target_chinese_chars)
    if status == "not_required":
        conclusion = "not_required"
        message = "word budget is not required for this project scale"
    elif status != "pass":
        conclusion = "revise_required"
        message = str(contract.get("message") or "word budget contract is not ready")
    else:
        min_words = _to_int(contract.get("min_chinese_chars") or contract.get("min_words"))
        max_words = _to_int(contract.get("max_chinese_chars") or contract.get("max_words"))
        if clean_chinese_chars < min_words:
            conclusion = "under_target"
            message = f"cleaned body has {clean_chinese_chars} Chinese content chars, below min_chinese_chars={min_words}"
        elif max_words and clean_chinese_chars > max_words:
            conclusion = "over_target"
            message = f"cleaned body has {clean_chinese_chars} Chinese content chars, above max_chinese_chars={max_words}"
        else:
            conclusion = "pass"
            message = "cleaned body is within the scene Chinese-content word-budget range"
    return {
        "status": conclusion,
        "count_unit": CHINESE_CONTENT_COUNT_UNIT,
        "machine_count_unit": MACHINE_NONSPACE_COUNT_UNIT,
        "clean_body_words": clean_chinese_chars,
        "clean_body_chinese_chars": clean_chinese_chars,
        "clean_body_machine_chars": clean_machine_chars,
        "target_words": _to_int(contract.get("target_words")),
        "min_words": _to_int(contract.get("min_words")),
        "max_words": _to_int(contract.get("max_words")),
        "target_chinese_chars": target_chinese_chars,
        "min_chinese_chars": _to_int(contract.get("min_chinese_chars") or contract.get("min_words")),
        "max_chinese_chars": _to_int(contract.get("max_chinese_chars") or contract.get("max_words")),
        "formal_count_policy": "pass/fail uses clean_body_chinese_chars against target_chinese_chars/min_chinese_chars/max_chinese_chars; *_words fields are legacy aliases.",
        "machine_count_mapping": mapping,
        "narrative_load": contract.get("narrative_load", []),
        "budget_contract_status": status,
        "budget_path": contract.get("budget_path", ""),
        "message": message,
    }


def render_word_budget_generation_standard(root: Path) -> str:
    summary = load_word_budget_summary(root)
    if not summary:
        return """# 长篇字数预算标准

当前项目尚未生成 `plot/word_budget/word_budget.json`。若目标是中长篇或百万字级项目，进入正式大纲、章节或场景生成前应先运行 `word-budget`，把总字数拆成卷、章、场景和叙事负载。"""
    target = summary.get("target", {})
    totals = summary.get("totals", {})
    binding = summary.get("scene_inventory_binding", {})
    binding = binding if isinstance(binding, dict) else {}
    underbuilt = binding.get("underbuilt_chapter_count", 0)
    missing_scenes = binding.get("missing_scene_count", 0)
    shortfall = binding.get("word_shortfall", 0)
    return f"""# 长篇字数预算标准

已加载 `{summary.get("path", "")}`。生成和扩写必须遵守以下预算，不得把大纲压缩成剧情摘要：

- 目标中文内容字符：{target.get("target_chinese_chars", target.get("target_words", 0))}
- 卷数：{target.get("volumes", 0)}
- 类型：{target.get("genre_label", target.get("genre", ""))}
- 目标章节数：{totals.get("chapter_count", 0)}
- 目标场景数：{totals.get("scene_count", 0)}
- 平均章中文内容字符：{totals.get("avg_chapter_words", 0)}
- 平均场景中文内容字符：{totals.get("avg_scene_words", 0)}
- 欠账章节数：{underbuilt}
- 缺失场景数：{missing_scenes}
- 正文缺口：{shortfall}

场景生成前必须确认当前场景承担明确叙事负载：主线行动、关系压力、世界/信息释放、行动后果或节奏调节。若 `scene_inventory_binding` 显示当前章节欠场景或正文缺口，先处理 `scene_inventory_expansion.agent_tasks.md`，补候选场景和因果链，不要用长段总结、空泛抒情或重复心理解释灌字数。"""


def render_scene_word_budget_contract(root: Path, scene_path: Path) -> str:
    contract = scene_word_budget_contract(root, scene_path)
    status = contract.get("status", "")
    if status == "not_required":
        return "本项目当前未达到强制长篇预算规模；仍应避免把剧情量压缩成摘要或用空泛描写灌字数。"
    if status != "pass":
        return f"本场景字数预算门禁未通过：{contract.get('message')}"
    return "\n".join(
        [
            f"- 场景：{contract.get('scene_id')}",
            f"- 章节：{contract.get('chapter_id')}",
            f"- 目标中文内容字符：{contract.get('target_chinese_chars')}",
            f"- 最低中文内容字符：{contract.get('min_chinese_chars')}",
            f"- 最高中文内容字符：{contract.get('max_chinese_chars')}",
            f"- 机器非空白字符诊断基准：{contract.get('machine_count_mapping', {}).get('rough_expected_machine_chars', contract.get('target_words'))}",
            f"- 机器非空白粗略范围：{contract.get('machine_count_mapping', {}).get('rough_expected_machine_chars_range', [])}",
            f"- 机器映射依据：{contract.get('machine_count_mapping', {}).get('mapping_basis', '')}",
            f"- 目标来源：{contract.get('source') or 'unknown'}",
            f"- scene.yaml 显式目标：{contract.get('scene_yaml_target_words') or 0}",
            f"- 预算推导目标：{contract.get('derived_target_words') or 0}",
            f"- 叙事负载：{', '.join(str(item) for item in contract.get('narrative_load', []))}",
            f"- 预算来源：{contract.get('budget_path')}",
            f"- 对齐状态：{contract.get('alignment_status') or 'n/a'}",
        ]
    )


def _write_agent_tasks(root: Path, markdown_path: Path, json_path: Path, outline_path: Path, task_path: Path, payload: dict) -> None:
    candidate = payload["candidate_outputs"]["budgeted_outline_candidate"]
    review = payload["candidate_outputs"]["budget_review"]
    source_paths = [markdown_path, json_path, root / "project.yaml"]
    if outline_path.exists():
        source_paths.append(outline_path)
    write_agent_tasks(
        task_path,
        title="longform word budget and narrative inventory review",
        root=root,
        source_paths=source_paths,
        notes=[
            "这是长篇字数预算与剧情库存门禁任务。",
            "CLI 只负责计算预算、统计现有大纲库存和生成诊断；卷章场景创意分配必须由平台 agent 完成。",
            "预算不等于灌字数。补足字数必须通过因果链、场景功能、人物状态、信息释放和行动后果增加剧情库存。",
            "候选大纲未经审查和用户批准，不得覆盖 plot/outline.md 或正式 scene 文件。",
        ],
        tasks=[
            (
                "审查预算与类型映射",
                """读取 word_budget.json / word_budget.md，确认目标中文内容字符、卷数、类型、时间跨度、章节数、场景数和平均场景中文内容字符是否适合该作品。若类型或时间跨度导致节奏不合理，提出修正预算而不是直接缩水。""",
            ),
            (
                "补足剧情库存候选",
                f"""创建或覆盖 `{candidate}`。按卷 -> 章 -> 场景列出可支撑目标中文内容字符的候选结构。每章必须包含目标中文内容字符、2-5个场景、每个场景的功能、目标中文内容字符、主线/副线/人物线/世界信息/后果负载、详略等级和承接的前后因果。不得只写概括性梗概。""",
            ),
            (
                "建立字数-剧情量映射",
                """为每卷写出剧情库存说明：核心事件数、调查/行动链数、人物关系变化数、信息释放点、失败/代价点、伏笔设置和回收点。若某卷目标约10万字，场景库存通常应达到60-90个；不足时必须标注 underbuilt。""",
            ),
            (
                "写入预算审查报告",
                f"""创建或覆盖 `{review}`。报告结论使用 pass / pass_with_notes / revise_required / reject，说明当前大纲是否足以支撑目标中文内容字符、哪里欠剧情库存、哪些卷需要扩展、哪些内容需要用户确认。不要写入 `[AGENT_TASK: ...]`。""",
            ),
        ],
    )


def _write_scene_inventory_agent_tasks(root: Path, markdown_path: Path, json_path: Path, outline_path: Path, task_path: Path, payload: dict) -> None:
    candidate = payload["candidate_outputs"]["scene_inventory_expansion"]
    review = payload["candidate_outputs"]["scene_inventory_review"]
    source_paths = [markdown_path, json_path, root / "project.yaml", root / "scenes"]
    if outline_path.exists():
        source_paths.append(outline_path)
    write_agent_tasks(
        task_path,
        title="longform scene inventory expansion",
        root=root,
        source_paths=source_paths,
        notes=[
            "这是字数预算到场景库存的绑定任务。",
            "CLI 已计算每章目标中文内容字符、目标场景数、实际 scene 文件数、已写正文中文内容字符、机器非空白字符诊断、缺失场景数和正文缺口。",
            "平台 agent 必须把缺口转化为新场景候选、关系转折、信息释放、行动后果和伏笔链，不得用灌水描写填字数。",
            "候选场景列表未经审查和用户批准，不得直接写入 scenes/ 或覆盖 plot/outline.md。",
        ],
        tasks=[
            (
                "读取欠账章节",
                """读取 word_budget.json 的 `scene_inventory_binding.chapter_rows`。筛出 status 为 underbuilt / missing_scenes / word_shortfall 的章节，确认每章缺几个场景、缺多少正文字符、缺哪类叙事负载。""",
            ),
            (
                "生成扩场景候选",
                f"""创建或覆盖 `{candidate}`。按章节列出补足目标中文内容字符所需的新场景候选：每个候选包含 scene_id 建议、目标中文内容字符、场景功能、参与角色、冲突、信息释放、关系变化、行动后果、伏笔设置/回收、承接前后因果。不得只写“增加描写”。""",
            ),
            (
                "写入扩场景审查报告",
                f"""创建或覆盖 `{review}`。报告结论使用 pass / pass_with_notes / revise_required / reject，说明候选场景是否足以支撑预算，哪些候选需要用户确认，哪些不能直接晋升。不要写入 `[AGENT_TASK: ...]`。""",
            ),
        ],
    )


def _write_chapter_obligation_plan_tasks(root: Path, markdown_path: Path, json_path: Path, outline_path: Path, task_path: Path, payload: dict) -> None:
    review = payload["candidate_outputs"]["chapter_obligation_review"]
    source_paths = [markdown_path, json_path, root / "project.yaml", root / "scenes"]
    if outline_path.exists():
        source_paths.append(outline_path)
    write_agent_tasks(
        task_path,
        title="longform chapter obligation and reader-experience planning",
        root=root,
        source_paths=source_paths,
        notes=[
            "这是从字数预算进入正文生成前的章节义务总规划任务。",
            "CLI 已给出 chapter_budgets 和 scene_inventory_binding，但读者问题、章节承诺、悬念兑现和反摘要要求必须由平台 Agent 判断。",
            "每个长篇章节正式生成前，还应运行 chapter-obligation --chapter-id <chapter_id> 生成单章契约侧车并完成 marker。",
        ],
        tasks=[
            (
                "建立章节承诺表",
                """读取 word_budget.json 的 chapter_budgets。按每章建立一行章节义务：chapter_id、目标中文内容字符、目标场景数、chapter_function、must_payoff、must_setup、must_change、must_not_resolve、inherited_hooks、ending_hook、inventory_sufficiency、expansion_needed。""",
            ),
            (
                "建立读者体验规划",
                """为每章列出读者将带着什么问题进入、期望什么回报、哪些信息暂扣、哪些承诺本章兑现、哪些必须延迟到后文。重点检查剧情库存是否支撑目标中文内容字符；不足时补事件链、关系压力、信息释放和后果，而不是要求正文灌水。""",
            ),
            (
                "写入章节义务审查报告",
                f"""创建或覆盖 `{review}`。报告结论使用 pass / pass_with_notes / revise_required / reject。若未能为主要章节建立可执行的读者体验契约，不得进入批量 scene-development。""",
            ),
        ],
    )


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


def _scene_inventory_binding(root: Path, chapter_budgets: list[dict[str, object]]) -> dict[str, object]:
    scenes = _scan_scene_files(root)
    by_chapter: dict[str, list[dict[str, object]]] = {}
    for scene in scenes:
        by_chapter.setdefault(str(scene["chapter_id"]), []).append(scene)
    rows = []
    for chapter in chapter_budgets:
        chapter_id = str(chapter["chapter_id"])
        expected_scenes = int(chapter["scene_count"])
        target_words = int(chapter["target_words"])
        actual = by_chapter.get(chapter_id, [])
        actual_scene_count = len(actual)
        actual_chars = sum(int(scene["draft_chinese_chars"]) for scene in actual)
        actual_machine_chars = sum(int(scene["draft_machine_chars"]) for scene in actual)
        missing_scene_count = max(expected_scenes - actual_scene_count, 0)
        word_shortfall = max(target_words - actual_chars, 0)
        if missing_scene_count:
            status = "missing_scenes"
        elif word_shortfall > max(target_words * 0.2, int(chapter.get("avg_scene_words", 0))):
            status = "word_shortfall"
        else:
            status = "ok"
        rows.append(
            {
                "chapter_id": chapter_id,
                "volume_id": chapter["volume_id"],
                "target_words": target_words,
                "target_scene_count": expected_scenes,
                "avg_scene_words": chapter["avg_scene_words"],
                "actual_scene_count": actual_scene_count,
                "actual_draft_chars": actual_chars,
                "actual_draft_chinese_chars": actual_chars,
                "actual_draft_machine_chars": actual_machine_chars,
                "missing_scene_count": missing_scene_count,
                "word_shortfall": word_shortfall,
                "status": status,
                "scene_ids": [scene["scene_id"] for scene in actual],
            }
        )
    return {
        "chapter_rows": rows,
        "underbuilt_chapter_count": sum(1 for row in rows if row["status"] != "ok"),
        "missing_scene_count": sum(int(row["missing_scene_count"]) for row in rows),
        "word_shortfall": sum(int(row["word_shortfall"]) for row in rows),
        "actual_scene_count": len(scenes),
        "actual_draft_chars": sum(int(scene["draft_chars"]) for scene in scenes),
        "actual_draft_chinese_chars": sum(int(scene["draft_chinese_chars"]) for scene in scenes),
        "actual_draft_machine_chars": sum(int(scene["draft_machine_chars"]) for scene in scenes),
    }


def _scan_scene_files(root: Path) -> list[dict[str, object]]:
    scene_dir = root / "scenes"
    if not scene_dir.exists():
        return []
    rows = []
    for path in sorted(scene_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        text = _read(path)
        scene_id = _scalar(text, "scene_id") or path.stem
        chapter_id = _scalar(text, "chapter_id") or "unassigned"
        draft_path = root / "drafts" / "scenes" / f"{scene_id}.md"
        body = final_body_from_draft_path(draft_path) if draft_path.exists() else ""
        rows.append(
            {
                "scene_id": scene_id,
                "chapter_id": chapter_id,
                "scene_path": _rel(path, root),
                "draft_path": _rel(draft_path, root) if draft_path.exists() else "",
                "draft_chars": count_delivery_chinese_content_chars(body),
                "draft_chinese_chars": count_delivery_chinese_content_chars(body),
                "draft_machine_chars": count_delivery_chars(body),
            }
        )
    return rows


def _chapter_budget_row(payload: dict[str, object], chapter_id: str) -> dict[str, object]:
    binding = payload.get("scene_inventory_binding") if isinstance(payload.get("scene_inventory_binding"), dict) else {}
    rows = binding.get("chapter_rows") if isinstance(binding, dict) else []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and str(row.get("chapter_id") or "") == chapter_id:
                return row
    rows = payload.get("chapter_budgets")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and str(row.get("chapter_id") or "") == chapter_id:
                return row
    return {}


def _scene_ids_for_chapter(root: Path, chapter_id: str) -> list[str]:
    scene_dir = root / "scenes"
    if not scene_dir.exists():
        return []
    ids = []
    for path in sorted(scene_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        text = _read(path)
        if (_scalar(text, "chapter_id") or "unassigned") != chapter_id:
            continue
        ids.append(_scalar(text, "scene_id") or path.stem)
    return ids


def _scene_word_count_target(scene_text: str) -> int:
    """Read explicit per-scene word target aliases from scene YAML."""

    for key in ("word_count_target", "target_words", "word_target"):
        value = _to_int(_scalar(scene_text, key))
        if value > 0:
            return value
    return 0


def _budget_issues(totals: dict[str, int], inventory: dict[str, int | str], scene_inventory_binding: dict[str, object]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    planned_chapters = int(inventory.get("planned_chapter_count", 0))
    planned_scenes = int(inventory.get("planned_scene_count", 0))
    required_chapters = totals["chapter_count"]
    required_scenes = totals["scene_count"]
    if planned_chapters and planned_chapters < required_chapters * 0.75:
        issues.append(
            {
                "severity": "medium",
                "category": "chapter_inventory",
                "message": f"现有章节库存约 {planned_chapters}，低于预算章节 {required_chapters} 的 75%。",
                "recommendation": "扩展卷章结构，增加可承载场景的章节，不要用章节摘要替代场景。",
            }
        )
    elif not planned_chapters:
        issues.append(
            {
                "severity": "medium",
                "category": "chapter_inventory",
                "message": f"未检测到明确章节库存，预算需要约 {required_chapters} 章。",
                "recommendation": "先生成预算化章节候选，再进入场景开发。",
            }
        )
    if planned_scenes and planned_scenes < required_scenes * 0.75:
        issues.append(
            {
                "severity": "high",
                "category": "scene_inventory",
                "message": f"现有场景库存约 {planned_scenes}，低于预算场景 {required_scenes} 的 75%。",
                "recommendation": "按主线、关系线、信息释放、行动后果和节奏调节补足场景库存。",
            }
        )
    elif not planned_scenes:
        issues.append(
            {
                "severity": "high",
                "category": "scene_inventory",
                "message": f"未检测到明确场景库存，预算需要约 {required_scenes} 个场景。",
                "recommendation": "先拆出卷-章-场景级候选，不要直接生成正文。",
            }
        )
    missing_scene_count = int(scene_inventory_binding.get("missing_scene_count", 0) or 0)
    word_shortfall = int(scene_inventory_binding.get("word_shortfall", 0) or 0)
    underbuilt_chapters = int(scene_inventory_binding.get("underbuilt_chapter_count", 0) or 0)
    if underbuilt_chapters:
        issues.append(
            {
                "severity": "high" if missing_scene_count else "medium",
                "category": "chapter_scene_binding",
                "message": f"预算绑定显示 {underbuilt_chapters} 个章节存在场景或正文缺口，缺失场景 {missing_scene_count} 个，正文缺口约 {word_shortfall} 字。",
                "recommendation": "处理 scene_inventory_expansion.agent_tasks.md，为欠账章节补足有因果功能的候选场景。",
            }
        )
    return issues


def _outline_inventory(root: Path, outline_path: Path) -> dict[str, int | str]:
    text = _read(outline_path)
    scene_files = [path for path in (root / "scenes").glob("*.yaml") if not path.name.startswith("_")] if (root / "scenes").exists() else []
    volume_count = len(re.findall(r"(?im)^(?:#{1,6}\s*)?(?:第[一二三四五六七八九十百\d]+卷|volume\s+\d+|卷\s*[一二三四五六七八九十百\d]+)", text))
    chapter_count = len(re.findall(r"(?im)^(?:#{1,6}\s*)?(?:第[一二三四五六七八九十百\d]+章|chapter\s+\d+|chapter_\d+)", text))
    scene_markers = len(re.findall(r"(?im)^(?:#{1,6}\s*)?(?:场景\s*[一二三四五六七八九十百\d]+|scene[_\s-]?\d+)", text))
    return {
        "outline_path": _rel(outline_path, root) if outline_path.exists() else "",
        "planned_volume_count": volume_count,
        "planned_chapter_count": chapter_count,
        "outline_scene_markers": scene_markers,
        "scene_file_count": len(scene_files),
        "planned_scene_count": max(scene_markers, len(scene_files)),
    }


def _render_markdown(root: Path, payload: dict, json_path: Path) -> str:
    target = payload["target"]
    totals = payload["totals"]
    inventory = payload["outline_inventory"]
    lines = [
        "# 长篇字数预算与剧情库存报告",
        "",
        f"- JSON：`{_rel(json_path, root)}`",
        f"- 状态：`{payload['status']}`",
        f"- 目标中文内容字符：{target['target_chinese_chars']}",
        "- 计数口径：清洗后中文正文字符，计入汉字和中文标点；机器非空白字符仅作为诊断映射。",
        f"- 卷数：{target['volumes']}",
        f"- 类型：{target['genre_label']}",
        f"- 时间跨度：{target.get('time_span') or '未指定'}",
        f"- 预算章节：{totals['chapter_count']}",
        f"- 预算场景：{totals['scene_count']}",
        f"- 平均章中文内容字符：{totals['avg_chapter_words']}",
        f"- 平均场景中文内容字符：{totals['avg_scene_words']}",
        "",
        "## 卷级预算",
        "",
        "| 卷 | 目标中文内容字符 | 章节 | 场景 | 章均中文内容字符 | 场景均中文内容字符 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in payload["volume_budgets"]:
        lines.append(
            f"| {item['volume_id']} | {item['target_words']} | {item['chapter_count']} | {item['scene_count']} | {item['avg_chapter_words']} | {item['avg_scene_words']} |"
        )
    lines.extend(
        [
            "",
            "## 章节-场景预算绑定",
            "",
            f"- 欠账章节：{payload['scene_inventory_binding']['underbuilt_chapter_count']}",
            f"- 缺失场景：{payload['scene_inventory_binding']['missing_scene_count']}",
            f"- 正文缺口：{payload['scene_inventory_binding']['word_shortfall']}",
            f"- 已有 scene 文件：{payload['scene_inventory_binding']['actual_scene_count']}",
            f"- 已有清洗后正文字符：{payload['scene_inventory_binding']['actual_draft_chars']}",
            "",
            "| 章节 | 卷 | 目标中文内容字符 | 目标场景 | 已有场景 | 已有正文中文内容字符 | 缺场景 | 正文缺口 | 状态 |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload["scene_inventory_binding"]["chapter_rows"][:40]:
        lines.append(
            "| {chapter} | {volume} | {target} | {target_scenes} | {actual_scenes} | {actual_chars} | {missing_scenes} | {shortfall} | {status} |".format(
                chapter=row["chapter_id"],
                volume=row["volume_id"],
                target=row["target_words"],
                target_scenes=row["target_scene_count"],
                actual_scenes=row["actual_scene_count"],
                actual_chars=row["actual_draft_chars"],
                missing_scenes=row["missing_scene_count"],
                shortfall=row["word_shortfall"],
                status=row["status"],
            )
        )
    if len(payload["scene_inventory_binding"]["chapter_rows"]) > 40:
        lines.append("| ... | ... | ... | ... | ... | ... | ... | ... | 仅显示前 40 行，完整数据见 JSON |")
    lines.extend(
        [
            "",
            "## 现有大纲库存",
            "",
            f"- 大纲：`{inventory.get('outline_path') or 'missing'}`",
            f"- 已规划卷：{inventory['planned_volume_count']}",
            f"- 已规划章：{inventory['planned_chapter_count']}",
            f"- 大纲场景标记：{inventory['outline_scene_markers']}",
            f"- scene 文件：{inventory['scene_file_count']}",
            f"- 估算场景库存：{inventory['planned_scene_count']}",
            "",
            "## 风险",
            "",
        ]
    )
    if payload["issues"]:
        for issue in payload["issues"]:
            lines.append(f"- **{issue['severity']} / {issue['category']}**：{issue['message']} 建议：{issue['recommendation']}")
    else:
        lines.append("- 未发现明显字数-剧情库存风险。")
    lines.extend(
        [
            "",
            "## 标准链路",
            "",
            "1. 先用本预算确认卷、章、场景和叙事负载。",
            "2. 平台 Agent 根据 `word_budget.agent_tasks.md` 生成预算化大纲候选。",
            "3. 平台 Agent 根据 `scene_inventory_expansion.agent_tasks.md` 补足欠账章节的场景候选。",
            "4. 预算化大纲和扩场景候选通过审查和用户批准前，不得覆盖正式 `plot/outline.md` 或 `scenes/`。",
            "5. 场景生成必须读取预算标准，避免把长篇目标压缩成短篇摘要。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


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


def _project_int(project_text: str, key: str) -> int:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(\d+)", project_text)
    return int(match.group(1)) if match else 0


def _project_genre(project_text: str) -> str:
    match = re.search(r"(?m)^[ \t]*genre:[ \t]*(.*?)\s*$", project_text)
    return match.group(1).strip().strip("\"'") if match else ""


def _scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^[ \t]*{re.escape(key)}:[ \t]*(.*?)\s*$", text)
    if not match:
        return ""
    value = match.group(1).strip()
    if value in {"null", "[]", "{}"}:
        return ""
    return value.strip("\"'")


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _resolve_output(root: Path, output: Path | None, *default_parts: str) -> Path:
    if output is None:
        return root.joinpath(*default_parts)
    return output if output.is_absolute() else root / output


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip() if path.exists() else ""


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _to_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).replace(",", "").replace("_", "").strip())
    except (TypeError, ValueError):
        return 0


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
