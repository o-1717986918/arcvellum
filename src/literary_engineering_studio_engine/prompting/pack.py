"""Prompt pack builder for scene generation providers."""

from __future__ import annotations

import json
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from string import Formatter
from typing import Any

from literary_engineering_studio_engine.literary.style.anti_ai import ANTI_AI_STYLE_PROMPT, ANTI_EVASION_REVISION_PROTOCOL
from literary_engineering_studio_engine.literary.review.creative_quality import (
    creative_quality_profile_exists,
    creative_quality_profile_path,
    load_creative_quality_profile,
    render_creative_quality_prompt,
)
from .scene_inputs import validated_scene_prompt_inputs
from ..literary.scene.composition.execution_contract import (
    load_prose_execution_contract,
    render_prose_execution_contract,
)
from literary_engineering_studio_engine.literary.planning.narrative_rhythm import narrative_rhythm_contract, render_narrative_rhythm_contract
from literary_engineering_studio_engine.literary.scene.state.new_character_register import render_new_character_register_contract
from literary_engineering_studio_engine.prompting.compiler import compile_active_constraints, render_compiled_constraints
from literary_engineering_studio_engine.literary.style.punctuation import render_punctuation_standard_for_prompt
from literary_engineering_studio_engine.literary.style.reference_projection import (
    recent_formal_reference_ids,
    render_style_reference_selection,
    select_active_style_references,
)
from literary_engineering_studio_engine.literary.review.reader_experience import (
    chapter_obligation_path,
    ensure_reader_experience_ready,
    render_reader_experience_contract,
    scene_chapter_obligation_id,
)
from literary_engineering_studio_engine.foundation.resources import engine_root
from ..literary.planning import contracts as word_budget_contracts
from ..literary.planning import rendering as word_budget_rendering
from .style_context import resolve_style_prompt_context


DEFAULT_CONTEXT_LIMIT = 18000
DEFAULT_COMPOSITION_LIMIT = 14000
DEFAULT_STYLE_LIMIT = 6000

STYLE_GENERATION_STANDARD = """# 文风生成标准（生成阶段执行）

先遵守 Canon、人物事实和场景目标，再把本场表达计划与所选完整参考转成语言动作。参考只提供叙述距离、句法运动、信息隐匿、对白回弹和意象来源，不复制原句或专名。

语言来自视角人物会注意、误解、回避和说出的事物。长短句随压力与认识变化，不把短句排成动作清单。修辞须改变视角、节奏、关系或信息；情绪可直述，也可由当前最有因果意义的行动、对白、沉默或感知承担，不轮流调用器官和声光。人物的稳定词域与当下对话对象共同决定言语行动。动作、对白或物证已成立时，停在后果，不替读者解释。

硬语言边界按项目已编译约束和标点规范执行；软审美风险在生成时自检，不作为词频配额。内部计划与自检不输出到正文。
"""

OUTPUT_CONTRACT = """模型输出必须使用以下 Markdown 结构：

## 正文候选

写入场景正文候选。遵守 Canon、人物、场景编排、文风生成标准与已编译硬语言边界；不输出文风分析、生成计划、自检表或工作流痕迹。

## 状态变化候选

### 新增事实候选

- 只列候选，不得声称已进入 canon。

### 人物状态变化

- 只列候选，等待人工确认。

### 关系变化

- 只列候选，等待人工确认。

### 伏笔变化

- 只列候选，等待人工确认。

## 新角色候选登记

- 若没有新角色，写：`status: none`。
- 若只有一次性路人，写：`status: ephemeral_only` 并说明豁免理由。
- 若有命名、会复用、掌握线索、影响关系或推动主线的新角色，写明候选角色资产路径、审查/approval/promotion 状态；未完成时不得伪装为已解决。

### 需要人工确认

- 列出所有可能影响 canon、人物重大转折、主线分支或发布边界的事项。
"""


@dataclass(frozen=True)
class PromptPack:
    project_root: Path
    scene_path: Path
    context_path: Path
    context_trace_path: Path
    composition_path: Path | None
    style_profile_path: Path | None
    style_mount_snapshot: dict[str, str]
    style_reference_selection: dict[str, Any]
    expression_plan_digest: str
    voice_digest: str
    word_budget_path: Path | None
    review_notes_path: Path | None
    creative_quality_profile: dict[str, Any]
    creative_quality_profile_path: Path | None
    creative_quality_profile_text: str
    style_generation_standard: str
    word_budget_generation_standard: str
    scene_word_budget_contract: dict[str, Any]
    scene_word_budget_contract_text: str
    reader_experience_contract: dict[str, Any]
    reader_experience_contract_text: str
    narrative_rhythm_contract: dict[str, Any]
    narrative_rhythm_contract_text: str
    review_notes_standard: str
    generation_constraint_brief: str
    compiled_constraints: dict[str, Any]
    compiled_constraints_text: str
    system_prompt: str
    user_prompt: str
    sources: list[dict[str, Any]]


def build_scene_prompt_pack(
    project_root: Path,
    scene_path: Path,
    context_path: Path,
    composition: Path | None = None,
    allow_unselected_composition: bool = False,
    allow_missing_composition: bool = False,
    materialization_scope: str = "full",
) -> PromptPack:
    """Render system/user prompts for a scene generation provider."""
    root, scene_path, context_path, context_trace_path, composition_path, scene_id = validated_scene_prompt_inputs(
        project_root, scene_path, context_path, composition,
        allow_unselected_composition=allow_unselected_composition,
        allow_missing_composition=allow_missing_composition,
    )
    word_budget_contract = word_budget_contracts.ensure_scene_word_budget_ready(
        root,
        scene_path,
        materialization_scope=materialization_scope,
    )
    reader_contract = ensure_reader_experience_ready(root, scene_path)
    rhythm_contract = narrative_rhythm_contract(root, scene_path, composition_path)
    style_context = resolve_style_prompt_context(root, text_limit=DEFAULT_STYLE_LIMIT)
    style_profile_path = style_context.path
    composition_payload = _read_json(_composition_json_path(composition_path)) if composition_path else {}
    reference_selection = select_active_style_references(
        root, _read(scene_path) + "\n" + str(composition_payload.get("composition_obligations") or ""),
        recent_unit_ids=recent_formal_reference_ids(root, exclude_scene_id=scene_id),
    )
    word_budget_path = _find_word_budget(root)
    review_notes_path = _find_scene_review_notes(root, scene_id)
    quality_profile = load_creative_quality_profile(root)
    quality_profile_path = creative_quality_profile_path(root) if creative_quality_profile_exists(root) else None
    quality_profile_text = render_creative_quality_prompt(quality_profile, scope=scene_id)
    compiled_constraints = compile_active_constraints(
        root,
        scene_path,
        style_text=_read(style_profile_path) if style_profile_path else "",
        revision_text=_read(review_notes_path) if review_notes_path else "",
    )
    compiled_constraints_text = render_compiled_constraints(compiled_constraints)
    values = {
        "scene_id": scene_id,
        "scene_text": _read(scene_path),
        "context_text": _limit(_read(context_path), DEFAULT_CONTEXT_LIMIT),
        "context_trace_text": _limit(_read(context_trace_path), DEFAULT_CONTEXT_LIMIT),
        "composition_text": _composition_contract_prompt_text(composition_path, allow_incomplete=allow_unselected_composition or allow_missing_composition),
        "style_profile": style_context.constraint,
        "style_reference_block": render_style_reference_selection(reference_selection),
        "style_generation_standard": _render_style_generation_standard(root, style_profile_path),
        "word_budget_generation_standard": word_budget_rendering.render_word_budget_generation_standard(root),
        "scene_word_budget_contract": word_budget_rendering.render_scene_word_budget_contract(
            root,
            scene_path,
            materialization_scope=materialization_scope,
        ),
        "reader_experience_contract": render_reader_experience_contract(root, scene_path),
        "narrative_rhythm_contract": render_narrative_rhythm_contract(root, scene_path, composition_path),
        "review_notes_standard": _render_review_notes_standard(root, scene_id, review_notes_path),
        "generation_constraint_brief": _render_generation_constraint_brief(root, style_profile_path, word_budget_path, review_notes_path, rhythm_contract),
        "compiled_constraints": compiled_constraints_text,
        "punctuation_standard": render_punctuation_standard_for_prompt(quality_profile, scope=scene_id),
        "anti_ai_style": ANTI_AI_STYLE_PROMPT,
        "creative_quality_profile": quality_profile_text,
        "new_character_register_contract": render_new_character_register_contract(),
        "output_contract": OUTPUT_CONTRACT.strip(),
        "generated_at": _now(),
    }
    system_template = _load_template(root, "scene_generation_system.md")
    user_template = _load_template(root, "scene_generation_user.md")
    system_prompt = _render_template(system_template, values)
    user_prompt = _ensure_style_generation_standard(_render_template(user_template, values), values["style_generation_standard"])
    user_prompt = _ensure_style_reference_selection(user_prompt, values["style_reference_block"])
    user_prompt = _ensure_word_budget_generation_standard(user_prompt, values["word_budget_generation_standard"])
    user_prompt = _ensure_scene_word_budget_contract(user_prompt, values["scene_word_budget_contract"])
    user_prompt = _ensure_reader_experience_contract(user_prompt, values["reader_experience_contract"])
    user_prompt = _ensure_narrative_rhythm_contract(user_prompt, values["narrative_rhythm_contract"])
    user_prompt = _ensure_review_notes_standard(user_prompt, values["review_notes_standard"])
    user_prompt = _ensure_generation_constraint_brief(user_prompt, values["generation_constraint_brief"])
    user_prompt = _ensure_compiled_constraints(user_prompt, compiled_constraints_text)
    user_prompt = _ensure_creative_quality_profile(user_prompt, quality_profile_text)
    user_prompt = _ensure_new_character_register_contract(user_prompt, values["new_character_register_contract"])
    user_prompt = _ensure_context_trace(user_prompt, values["context_trace_text"])
    sources = _sources(
        root,
        scene_path,
        context_path,
        context_trace_path,
        composition_path,
        style_profile_path,
        word_budget_path,
        review_notes_path,
        quality_profile_path,
    )
    return PromptPack(
        project_root=root,
        scene_path=scene_path,
        context_path=context_path,
        context_trace_path=context_trace_path,
        composition_path=composition_path,
        style_profile_path=style_profile_path,
        style_mount_snapshot=style_context.snapshot,
        style_reference_selection=reference_selection,
        expression_plan_digest=_object_digest(composition_payload.get("expression_plan")),
        voice_digest=_object_digest(composition_payload.get("dialogue_intents")),
        word_budget_path=word_budget_path,
        review_notes_path=review_notes_path,
        creative_quality_profile=quality_profile,
        creative_quality_profile_path=quality_profile_path,
        creative_quality_profile_text=quality_profile_text,
        style_generation_standard=values["style_generation_standard"],
        word_budget_generation_standard=values["word_budget_generation_standard"],
        scene_word_budget_contract=word_budget_contract,
        scene_word_budget_contract_text=values["scene_word_budget_contract"],
        reader_experience_contract=reader_contract,
        reader_experience_contract_text=values["reader_experience_contract"],
        narrative_rhythm_contract=rhythm_contract,
        narrative_rhythm_contract_text=values["narrative_rhythm_contract"],
        review_notes_standard=values["review_notes_standard"],
        generation_constraint_brief=values["generation_constraint_brief"],
        compiled_constraints=compiled_constraints,
        compiled_constraints_text=compiled_constraints_text,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        sources=sources,
    )


def write_prompt_manifest(pack: PromptPack, output: Path, provider: str, model: str = "") -> Path:
    """Write a reproducible prompt manifest next to a generated candidate."""

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "literary-engineering-workbench/prompt-pack/v0.1",
        "generated_at": _now(),
        "provider": provider,
        "model": model,
        "scene": _rel(pack.scene_path, pack.project_root),
        "context": _rel(pack.context_path, pack.project_root),
        "context_trace": _rel(pack.context_trace_path, pack.project_root),
        "composition": _rel(pack.composition_path, pack.project_root) if pack.composition_path else "",
        "style_profile": _rel(pack.style_profile_path, pack.project_root) if pack.style_profile_path else "",
        "style_mount_snapshot": pack.style_mount_snapshot,
        "style_reference_selection": pack.style_reference_selection,
        "expression_plan_digest": pack.expression_plan_digest,
        "voice_digest": pack.voice_digest,
        "generation_standards": {
            "style": pack.style_generation_standard,
            "style_profile_loaded": pack.style_profile_path is not None,
            "style_profile": _rel(pack.style_profile_path, pack.project_root) if pack.style_profile_path else "",
            "style_mount_snapshot": pack.style_mount_snapshot,
            "creative_quality_profile": pack.creative_quality_profile,
            "creative_quality_profile_path": _rel(pack.creative_quality_profile_path, pack.project_root) if pack.creative_quality_profile_path else "implicit-default",
            "creative_quality_profile_digest": str(pack.creative_quality_profile.get("digest") or ""),
            "word_budget": pack.word_budget_generation_standard,
            "word_budget_loaded": pack.word_budget_path is not None,
            "word_budget_path": _rel(pack.word_budget_path, pack.project_root) if pack.word_budget_path else "",
            "scene_word_budget_contract": pack.scene_word_budget_contract,
            "reader_experience_contract": pack.reader_experience_contract,
            "reader_experience_loaded": pack.reader_experience_contract.get("status") in {"pass", "not_required"},
            "narrative_rhythm_contract": pack.narrative_rhythm_contract,
            "narrative_rhythm_loaded": pack.narrative_rhythm_contract.get("status") in {"pass", "defaulted"},
            "review_notes": pack.review_notes_standard,
            "review_notes_loaded": pack.review_notes_path is not None,
            "review_notes_path": _rel(pack.review_notes_path, pack.project_root) if pack.review_notes_path else "",
            "anti_evasion": ANTI_EVASION_REVISION_PROTOCOL,
            "new_character_register": render_new_character_register_contract(),
            "hard_constraints": pack.generation_constraint_brief,
            "compiled_constraints": pack.compiled_constraints,
            "context_trace_loaded": pack.context_trace_path.exists(),
        },
        "sources": pack.sources,
        "messages": [
            {"role": "system", "content": pack.system_prompt},
            {"role": "user", "content": pack.user_prompt},
        ],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def _load_template(root: Path, name: str) -> str:
    project_template = root / "prompts" / name
    if project_template.exists():
        return _read(project_template)
    bundled = _bundle_root() / "templates" / "prompts" / name
    if bundled.exists():
        return _read(bundled)
    raise FileNotFoundError(f"prompt template not found: prompts/{name}")


def _render_template(template: str, values: dict[str, str]) -> str:
    required = {field for _, field, _, _ in Formatter().parse(template) if field}
    missing = [field for field in sorted(required) if field not in values]
    if missing:
        raise KeyError(f"missing prompt variables: {', '.join(missing)}")
    return template.format_map(values).strip() + "\n"


def _ensure_style_generation_standard(user_prompt: str, standard: str) -> str:
    if "## 文风生成标准" in user_prompt or "# 文风生成标准" in user_prompt:
        return user_prompt
    return user_prompt.rstrip() + "\n\n## 文风生成标准\n\n" + standard.strip() + "\n"


def _ensure_style_reference_selection(user_prompt: str, selection: str) -> str:
    if "## 本场参考选段" in user_prompt:
        return user_prompt
    return user_prompt.rstrip() + "\n\n## 本场参考选段\n\n" + selection.strip() + "\n"


def _ensure_creative_quality_profile(user_prompt: str, profile_text: str) -> str:
    if "# 本项目创作品质档案" in user_prompt:
        return user_prompt
    return user_prompt.rstrip() + "\n\n" + profile_text.strip() + "\n"


def _ensure_word_budget_generation_standard(user_prompt: str, standard: str) -> str:
    if "## 长篇字数预算标准" in user_prompt or "# 长篇字数预算标准" in user_prompt:
        return user_prompt
    return user_prompt.rstrip() + "\n\n## 长篇字数预算标准\n\n" + standard.strip() + "\n"


def _ensure_scene_word_budget_contract(user_prompt: str, standard: str) -> str:
    if "## 本场景字数预算硬属性" in user_prompt or "# 本场景字数预算硬属性" in user_prompt:
        return user_prompt
    return user_prompt.rstrip() + "\n\n## 本场景字数预算硬属性\n\n" + standard.strip() + "\n"


def _ensure_reader_experience_contract(user_prompt: str, standard: str) -> str:
    if "## 本场景读者体验硬属性" in user_prompt or "# 本场景读者体验硬属性" in user_prompt:
        return user_prompt
    return user_prompt.rstrip() + "\n\n## 本场景读者体验硬属性\n\n" + standard.strip() + "\n"


def _ensure_narrative_rhythm_contract(user_prompt: str, standard: str) -> str:
    if "## 本场景叙事节奏与场景桥接硬属性" in user_prompt or "# 本场景叙事节奏与场景桥接硬属性" in user_prompt:
        return user_prompt
    return user_prompt.rstrip() + "\n\n## 本场景叙事节奏与场景桥接硬属性\n\n" + standard.strip() + "\n"


def _ensure_review_notes_standard(user_prompt: str, standard: str) -> str:
    if "## AgentReview 小修约束" in user_prompt or "# AgentReview 小修约束" in user_prompt:
        return user_prompt
    return user_prompt.rstrip() + "\n\n## AgentReview 小修约束\n\n" + standard.strip() + "\n"


def _ensure_generation_constraint_brief(user_prompt: str, brief: str) -> str:
    if "## 生成前最终硬约束摘要" in user_prompt or "# 生成前最终硬约束摘要" in user_prompt:
        return user_prompt
    return user_prompt.rstrip() + "\n\n## 生成前最终硬约束摘要\n\n" + brief.strip() + "\n"


def _ensure_compiled_constraints(user_prompt: str, compiled: str) -> str:
    if "## 已编译创作约束" in user_prompt or "# 已编译创作约束" in user_prompt:
        return user_prompt
    return user_prompt.rstrip() + "\n\n" + compiled.strip() + "\n"


def _ensure_new_character_register_contract(user_prompt: str, contract: str) -> str:
    if "## 新角色登记契约" in user_prompt or "new_character_register" in user_prompt:
        return user_prompt
    return user_prompt.rstrip() + "\n\n## 新角色登记契约\n\n" + contract.strip() + "\n"


def _ensure_context_trace(user_prompt: str, trace_text: str) -> str:
    if "## Context Trace" in user_prompt or "## 上下文来源证明" in user_prompt:
        return user_prompt
    return (
        user_prompt.rstrip()
        + "\n\n## 上下文来源证明 Context Trace\n\n"
        + "正式生成前必须读取本 trace，确认 context packet 实际加载了哪些 canon、character、style、plot、word-budget 和 retrieval 文件。"
        + "如果 trace 显示缺少 required context，停止正文生成并修复上下文。\n\n"
        + "```json\n"
        + trace_text.strip()
        + "\n```\n"
    )


def _sources(
    root: Path,
    scene_path: Path,
    context_path: Path,
    context_trace_path: Path,
    composition_path: Path | None,
    style_profile_path: Path | None,
    word_budget_path: Path | None,
    review_notes_path: Path | None,
    quality_profile_path: Path | None,
) -> list[dict[str, Any]]:
    paths = [scene_path, context_path, context_trace_path]
    if composition_path:
        paths.append(composition_path)
        paths.append(_composition_json_path(composition_path))
    if style_profile_path:
        paths.append(style_profile_path)
    if word_budget_path:
        paths.append(word_budget_path)
    obligation = _reader_obligation_source_path(root, scene_path)
    if obligation and obligation.exists():
        paths.append(obligation)
    if review_notes_path:
        paths.append(review_notes_path)
    if quality_profile_path:
        paths.append(quality_profile_path)
    punctuation_ref = _bundle_root() / "references" / "punctuation-standard.md"
    if punctuation_ref.exists():
        paths.append(punctuation_ref)
    return [
        {
            "path": _rel(path, root),
            "chars": len(_read(path)),
        }
        for path in paths
    ]


def _composition_json_path(composition_path: Path | None) -> Path | None:
    if composition_path is None:
        return None
    path = composition_path if composition_path.suffix.lower() == ".json" else composition_path.with_suffix(".json")
    if not path.is_file():
        raise FileNotFoundError(f"composition JSON not found: {path}")
    return path


def _composition_prompt_text(composition_path: Path | None, execution_contract_text: str) -> str:
    if composition_path is None:
        return "内部实验模式：未加载场景创作编排包。正式生成必须先运行 simulate-scene --agent、branch-simulate --agent、记录 branch_selection.md，并重建 compose-scene。"
    markdown = _limit(_read(composition_path), DEFAULT_COMPOSITION_LIMIT)
    markdown = re.sub(r"(?ms)^## 正文种子\s*\n.*?(?=^## |\Z)", "## 历史正文种子\n\n此节为旧编排遗留，不作为措辞约束。\n\n", markdown)
    return markdown.rstrip() + "\n\n" + execution_contract_text.strip() + "\n"


def _execution_contract_text(
    composition_path: Path | None,
    *,
    allow_incomplete: bool = False,
) -> str:
    if composition_path is None:
        return ""
    try:
        contract = load_prose_execution_contract(
            _composition_json_path(composition_path)
        )
    except ValueError:
        if not allow_incomplete:
            raise
        return (
            "[MAINTAINER_EXPERIMENT: formal prose execution contract is incomplete; "
            "this prompt pack is not eligible for formal promotion or release.]"
        )
    return render_prose_execution_contract(contract)


def _composition_contract_prompt_text(
    composition_path: Path | None,
    *,
    allow_incomplete: bool,
) -> str:
    return _composition_prompt_text(
        composition_path,
        _execution_contract_text(
            composition_path,
            allow_incomplete=allow_incomplete,
        ),
    )


def _reader_obligation_source_path(root: Path, scene_path: Path) -> Path | None:
    chapter_id = scene_chapter_obligation_id(root, scene_path)
    if not chapter_id or chapter_id == "unassigned":
        return None
    path = chapter_obligation_path(root, chapter_id)
    return path if path.exists() else None


def _find_word_budget(root: Path) -> Path | None:
    path = root / "plot" / "word_budget" / "word_budget.json"
    return path if path.exists() else None


def _find_scene_review_notes(root: Path, scene_id: str) -> Path | None:
    candidates = [
        root / "reviews" / "agent" / f"{scene_id}_scene_review.json",
        root / "reviews" / f"{scene_id}-review.md",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _render_style_generation_standard(root: Path, style_path: Path | None) -> str:
    if style_path is None:
        return STYLE_GENERATION_STANDARD + "\n当前状态：未找到已挂载 Style Skill 或 style_prompt。使用本标准的中性版本：叙述距离与语言曲线随场景压力变化，句法服务行动、感知和人物声音，意象来自当前经验，并避免 AI 腔。"
    return (
        STYLE_GENERATION_STANDARD
        + "\n当前状态：已加载文风来源 `"
        + _rel(style_path, root)
        + "`。生成前必须先把该文风来源转译为本场的叙述距离、语言曲线、意象系统、心理呈现、人物对白策略和标点节奏。"
    )


def _render_review_notes_standard(root: Path, scene_id: str, review_path: Path | None) -> str:
    if review_path is None:
        return """# AgentReview 小修约束

当前未发现上一轮平台 Agent 场景审查。若这是初稿生成，按 canon、人物、文风、预算和输出契约创作；若这是修订稿，应先补齐或读取上一轮 review。"""
    if review_path.suffix.lower() == ".json":
        return _render_json_review_notes(root, review_path)
    text = _read(review_path)
    conclusion_match = re.search(r"(?m)^-\s*结论：\s*`?([^`\s]+)`?\s*$", text)
    conclusion = conclusion_match.group(1).strip() if conclusion_match else ""
    if conclusion == "pass_with_notes":
        return f"""# AgentReview 小修约束

已加载 `{_rel(review_path, root)}`。静态审查结论为 `pass_with_notes`：写作 agent 必须处理报告中的 low 级问题或在“需要人工确认”中说明豁免，不得直接视为完全通过。"""
    return f"""# AgentReview 小修约束

已加载 `{_rel(review_path, root)}`。当前静态审查结论为 `{conclusion or "unknown"}`；如果不是 `pass`，写作前先读取问题摘要并处理。"""


def _render_json_review_notes(root: Path, review_path: Path) -> str:
    payload = _read_json(review_path)
    conclusion = str(payload.get("conclusion") or "").strip()
    warnings = _json_list(payload.get("warnings"))
    revision_actions = _json_list(payload.get("revision_actions"))
    style_notes = _json_list(payload.get("style_notes"))
    style_status, style_adherence_notes = _style_adherence_notes(payload)
    if conclusion in {"revise_required", "reject"} or style_status in {"revise_required", "reject"}:
        leading = f"上一轮平台 Agent 场景审查结论为 `{conclusion or 'unknown'}`，文风执行门禁为 `{style_status or 'unknown'}`。这不是小修；不得直接润色通过，必须围绕 blocking issues / revision_actions / style_adherence 重写或退回审查。"
    elif conclusion == "pass_with_notes" or style_status == "pass_with_notes":
        leading = f"上一轮平台 Agent 场景审查结论为 `{conclusion or 'unknown'}`，文风执行门禁为 `{style_status or 'unknown'}`。写作 agent 不得把它当成完全通过；本轮必须执行轻微修订，或在“需要人工确认”中逐条说明无法执行的理由。"
    elif conclusion == "pass":
        return f"""# AgentReview 小修约束

已加载 `{_rel(review_path, root)}`。上一轮平台 Agent 审查结论为 `pass`，当前没有强制小修项；仍须遵守 canon、人物、文风、预算、标点和输出契约。"""
    else:
        return f"""# AgentReview 小修约束

已加载 `{_rel(review_path, root)}`，但未识别到有效 conclusion。写作前先检查该 review 是否完整；不要把缺失结论当成通过。"""
    return _review_notes_block(
        root, review_path, leading, revision_actions, warnings, style_notes, style_adherence_notes
    )


def _review_notes_block(
    root: Path,
    review_path: Path,
    leading: str,
    revision_actions: list[str],
    warnings: list[str],
    style_notes: list[str],
    style_adherence_notes: list[str],
) -> str:
    return "\n".join(
        [
            "# AgentReview 小修约束",
            "",
            f"已加载 `{_rel(review_path, root)}`。",
            "",
            leading,
            "",
            "执行规则：",
            "",
            "- 优先处理 revision_actions，其次处理 style_adherence 偏差，再处理 warnings 和 style_notes。",
            "- 小修应尽量局部：改动作、信息呈现、标点节奏、人物语气或段落收束，不随意新增 canon。",
            "- 候选正文的 manifest 应记录 `pass_with_notes_actions_applied=true`；若没有可执行项，记录 `pass_with_notes_noop_reason`。",
            "- 若任何修订会改变 canon、人物重大转折或分支选择，把它列入“需要人工确认”，不要偷偷写实。",
            "",
            "revision_actions:",
            _bullet_list(revision_actions),
            "",
            "warnings:",
            _bullet_list(warnings),
            "",
            "style_notes:",
            _bullet_list(style_notes),
            "",
            "style_adherence:",
            _bullet_list(style_adherence_notes),
        ]
    )


def _render_generation_constraint_brief(
    root: Path,
    style_path: Path | None,
    word_budget_path: Path | None,
    review_notes_path: Path | None,
    rhythm_contract: dict[str, Any] | None = None,
) -> str:
    rhythm_status = str((rhythm_contract or {}).get("status") or "missing")
    return f"""# 生成前最终硬约束摘要

Canon、用户明确约束和人物事实优先。正式生成执行已选择的 composition 分支、场景义务、人物当下声音和 expression plan；旧 composition 的 prose seed 仅为历史证据，不复现其措辞。文风来源：{_loaded_label(style_path, root, "已加载", "未加载")}；节奏合同：`{rhythm_status}`；预算：{_loaded_label(word_budget_path, root, "已加载", "未加载")}；审读小修：{_loaded_label(review_notes_path, root, "已加载", "未加载")}。

中文标点、项目禁用表达和机械对照按已编译约束审查。软审美问题由表达计划和人物声音在生成时处理，不把密度阈值当作写作配额。只输出候选正文和状态变化候选；需要偏离已确认事实时写入“需要人工确认”。
"""


def _loaded_label(path: Path | None, root: Path, loaded: str, missing: str) -> str:
    return f"{loaded} `{_rel(path, root)}`" if path else missing


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _object_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest() if value is not None else ""


def _json_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = "; ".join(f"{key}: {val}" for key, val in item.items() if val not in ("", None))
        else:
            text = str(item).strip()
        if text:
            items.append(text)
    return items


def _style_adherence_notes(payload: dict[str, Any]) -> tuple[str, list[str]]:
    adherence = payload.get("style_adherence")
    if not isinstance(adherence, dict):
        return "", []
    status = str(adherence.get("status") or "").strip().lower()
    notes: list[str] = []
    for key in ("revision_actions", "deviations", "evidence"):
        for item in _json_list(adherence.get(key)):
            notes.append(f"{key}: {item}")
    if status and not notes:
        notes.append(f"status: {status}")
    return status, notes


def _bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- 无。"


def _bundle_root() -> Path:
    return engine_root()


def _read(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _limit(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[内容因提示词长度限制被截断。]"


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
