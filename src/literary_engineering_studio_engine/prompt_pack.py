"""Prompt pack builder for scene generation providers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from string import Formatter
from typing import Any

from .anti_ai_style import ANTI_AI_STYLE_PROMPT, ANTI_EVASION_REVISION_PROTOCOL
from .context_broker import default_context_trace_path
from .creative_quality import (
    creative_quality_profile_exists,
    creative_quality_profile_path,
    load_creative_quality_profile,
    render_creative_quality_prompt,
)
from .flow_gates import ensure_composition_ready_for_generation
from .narrative_rhythm import narrative_rhythm_contract, render_narrative_rhythm_contract
from .new_character_register import render_new_character_register_contract
from .punctuation_standard import render_punctuation_standard_for_prompt
from .reader_experience import (
    chapter_obligation_path,
    ensure_reader_experience_ready,
    render_reader_experience_contract,
    scene_chapter_obligation_id,
)
from .resources import engine_root
from .word_budget import (
    ensure_scene_word_budget_ready,
    render_scene_word_budget_contract,
    render_word_budget_generation_standard,
    scene_word_budget_contract,
)


DEFAULT_CONTEXT_LIMIT = 18000
DEFAULT_COMPOSITION_LIMIT = 14000
DEFAULT_STYLE_LIMIT = 6000

STYLE_GENERATION_STANDARD = """# 文风生成标准（生成前硬约束）

本标准必须在动笔前执行，不能等到审查阶段再补救。平台 agent 或本地 provider 在生成正文候选前，应先把已挂载 Style Skill / style profile 转译为本场景的表达策略；该策略不输出到候选正文，只用于指导写作。

执行顺序：

1. 先读取文风约束提示词，提取本场景可执行的六类表达机制：叙述距离、句法与段落节奏、意象/感官系统、心理呈现方式、对白密度与语气、标点停顿节奏。
2. 再读取 scene.yaml、context packet、context trace 和 composition，确认 canon、人物 BDI、background_story 隐性动因、场景目标、已加载来源和禁止改动项。
3. 写作时每个段落至少承担一种具体叙事功能：推进行动、改变信息、暴露关系压力、呈现人物选择、加固意象或留下后果；不得只承担“文艺化润色”功能。
4. 文风要通过叙事机制生效，不靠复用高频词、套用金句、堆叠形容词或复制原文片段。
5. 文风可以改变句长、停顿、意象密度和对白疏密，但不能突破标准中文标点规范，不能制造密集句号、长逗号链、破折号、机械转折或器官轮岗。
6. 生硬对照句式一律禁用：不使用“不是……而是……”“并非……而是……”“与其说……不如说……”以及“不是……——是……”“不是……。是……”“不是……，是……”等变体；不要把这类结构判断为合理修辞。
7. 禁止换皮转折：不使用“并不是……只是……”“倒不是……只是……”“不是说……只是……”“看似……其实……”“表面上……实则……”“没有……只是……”“也不……也不……只是……”等同功能替代。若必须保留显式转折，先做负担证明：它承担的叙事功能、为什么动作/事实顺序/信息差不能替代、是否仍有换皮嫌疑。
8. 正式正文原则上不用破折号。需要停顿、插入或转折时，优先换句、换段、删掉冗余渲染，或用动作/事实顺序承接；孤立破折号需逐句复核，超过约 2% 叙事单元密度或替代“而是/但是/于是”时必须修订。
9. 执行朴素叙述标准：像给朋友讲一件事，像日记里会写的句子。过场一句话交代；高潮可以细写，但细写不等于堆形容词、身体反应、华丽比喻或景物同步。器官轮岗、万能占位、比喻依赖和高频套话按约 2% 叙事单元密度门禁控制，孤例复核，密集修订。
10. 若文风要求与 canon、人物逻辑、场景因果或用户明确要求冲突，保留硬事实，在“需要人工确认”中说明冲突，不要用文风掩盖逻辑问题。
11. 输出前做内部自检：正文是否先服从了文风机制，是否降低 AI 腔，是否仍保持人物和剧情因果。不要把自检过程、风格分析或工作流痕迹写进正文候选。
"""

OUTPUT_CONTRACT = """模型输出必须使用以下 Markdown 结构：

## 正文候选

写入场景正文候选。正文必须先执行“文风生成标准”和“新角色登记契约”，再遵守 canon、人物 BDI、背景故事隐性动因、场景编排包和文风 profile。
正文还必须遵守标准中文标点约束：中文句子使用全角标点，省略号用“……”，避免英文标点混入中文正文和连续感叹/疑问符。
标点必须服务朴素叙述：一句话尽量少用逗号，超过三个逗号通常要拆句；正式正文原则上不用破折号，不靠“但是、然而、于是、然后、突然”机械制造转折。
正文必须降低 AI 腔：禁用机械“不是……而是……”“并非……而是……”“与其说……不如说……”以及“不是……——是……”“不是……。是……”等变体；不要把这类结构判断为合理修辞。也禁止“并不是……只是……”“倒不是……只是……”“看似……其实……”“表面上……实则……”“没有……只是……”等换皮转折。器官轮岗、万能占位、比喻依赖、抽象总结、解释性心理标签、模板化转折、对称排比、全知说教、景物强制同步和结尾金句化按密度控制：约 2% 叙事单元以内的孤立风险点可进入低级复核，密集出现必须修订。
不要用脚本化思维改写正文：生成时避免问题，修订时逐句语义判断；不得把否定、纠偏或人物心理误删成反义。
不要在正文候选中输出文风分析、生成计划、自检表或工作流痕迹；这些只能作为内部生成标准。

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

    root = project_root.resolve()
    scene_path = _resolve(root, scene_path)
    context_path = _resolve(root, context_path)
    context_trace_path = default_context_trace_path(context_path)
    if not context_trace_path.exists():
        raise FileNotFoundError(
            f"context trace not found: {_rel(context_trace_path, root)}. "
            "Run context again so formal generation can audit loaded canon/character/style/word-budget inputs."
        )
    scene_id = scene_path.stem or "scene"
    default_composition = root / "drafts" / "compositions" / f"{scene_id}_composition.md"
    composition_path = _resolve(root, composition) if composition else default_composition
    if not composition_path.exists():
        composition_path = None
    ensure_composition_ready_for_generation(
        root,
        composition_path,
        allow_unselected_composition=allow_unselected_composition,
        allow_missing_composition=allow_missing_composition,
    )
    word_budget_contract = ensure_scene_word_budget_ready(
        root,
        scene_path,
        materialization_scope=materialization_scope,
    )
    reader_contract = ensure_reader_experience_ready(root, scene_path)
    rhythm_contract = narrative_rhythm_contract(root, scene_path, composition_path)
    style_profile_path = _find_style_asset(root)
    word_budget_path = _find_word_budget(root)
    review_notes_path = _find_scene_review_notes(root, scene_id)
    quality_profile = load_creative_quality_profile(root)
    quality_profile_path = creative_quality_profile_path(root) if creative_quality_profile_exists(root) else None
    quality_profile_text = render_creative_quality_prompt(quality_profile, scope=scene_id)

    values = {
        "scene_id": scene_id,
        "scene_text": _read(scene_path),
        "context_text": _limit(_read(context_path), DEFAULT_CONTEXT_LIMIT),
        "context_trace_text": _limit(_read(context_trace_path), DEFAULT_CONTEXT_LIMIT),
        "composition_text": _limit(_read(composition_path), DEFAULT_COMPOSITION_LIMIT) if composition_path else "内部实验模式：未加载场景创作编排包。正式生成必须先运行 simulate-scene --agent、branch-simulate --agent、记录 branch_selection.md，并重建 compose-scene。",
        "style_profile": _render_style_constraint(root, style_profile_path),
        "style_generation_standard": _render_style_generation_standard(root, style_profile_path),
        "word_budget_generation_standard": render_word_budget_generation_standard(root),
        "scene_word_budget_contract": render_scene_word_budget_contract(
            root,
            scene_path,
            materialization_scope=materialization_scope,
        ),
        "reader_experience_contract": render_reader_experience_contract(root, scene_path),
        "narrative_rhythm_contract": render_narrative_rhythm_contract(root, scene_path, composition_path),
        "review_notes_standard": _render_review_notes_standard(root, scene_id, review_notes_path),
        "generation_constraint_brief": _render_generation_constraint_brief(root, style_profile_path, word_budget_path, review_notes_path, rhythm_contract),
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
    user_prompt = _ensure_word_budget_generation_standard(user_prompt, values["word_budget_generation_standard"])
    user_prompt = _ensure_scene_word_budget_contract(user_prompt, values["scene_word_budget_contract"])
    user_prompt = _ensure_reader_experience_contract(user_prompt, values["reader_experience_contract"])
    user_prompt = _ensure_narrative_rhythm_contract(user_prompt, values["narrative_rhythm_contract"])
    user_prompt = _ensure_review_notes_standard(user_prompt, values["review_notes_standard"])
    user_prompt = _ensure_generation_constraint_brief(user_prompt, values["generation_constraint_brief"])
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
        "generation_standards": {
            "style": pack.style_generation_standard,
            "style_profile_loaded": pack.style_profile_path is not None,
            "style_profile": _rel(pack.style_profile_path, pack.project_root) if pack.style_profile_path else "",
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


def _reader_obligation_source_path(root: Path, scene_path: Path) -> Path | None:
    chapter_id = scene_chapter_obligation_id(root, scene_path)
    if not chapter_id or chapter_id == "unassigned":
        return None
    path = chapter_obligation_path(root, chapter_id)
    return path if path.exists() else None


def _find_style_asset(root: Path) -> Path | None:
    mounted = _find_mounted_style_skill(root)
    if mounted:
        return mounted
    style_root = root / "style"
    candidates = [style_root / "style_prompt.md"]
    if style_root.exists():
        candidates.extend(sorted(style_root.glob("*/style_prompt.md"), key=lambda path: path.stat().st_mtime, reverse=True))
    candidates.append(style_root / "style-profile.md")
    if style_root.exists():
        candidates.extend(sorted(style_root.glob("*/style-profile.md"), key=lambda path: path.stat().st_mtime, reverse=True))
    for path in candidates:
        if path.exists():
            return path
    return None


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


def _find_mounted_style_skill(root: Path) -> Path | None:
    active = root / "style" / "active_style_skill.json"
    if not active.exists():
        return None
    try:
        payload = json.loads(active.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        return None
    path = root / prompt
    return path if path.exists() else None


def _render_style_constraint(root: Path, style_path: Path | None) -> str:
    if style_path is None:
        return "未找到挂载的 style skill 或 style/style-profile.md。若项目要求文风门禁，应先在文风学习页挂载 active style skill。"
    text = _limit(_read(style_path), DEFAULT_STYLE_LIMIT)
    active = root / "style" / "active_style_skill.json"
    if active.exists():
        try:
            payload = json.loads(active.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        return f"""# 已挂载文风 Style Skill（最高优先级）

- Style ID: `{payload.get("style_id", "")}`
- Priority: `{payload.get("priority", "highest")}`
- Mount: `{payload.get("mount_path", "")}`

硬规则：

- 本 Style Skill 在表达层拥有最高优先级：叙述距离、句法节奏、意象系统、心理呈现、对白密度和段落推进必须先服从它。
- 它不覆盖 canon、人物事实、剧情因果、用户明确约束和安全边界。
- 如文风要求与 canon/人物逻辑冲突，保留 canon/人物逻辑，并在“需要人工确认”中说明文风冲突。

## Style Skill Prompt

{text}
"""
    return text


def _render_style_generation_standard(root: Path, style_path: Path | None) -> str:
    if style_path is None:
        return STYLE_GENERATION_STANDARD + "\n当前状态：未找到已挂载 Style Skill 或 style_prompt。仍必须使用本标准的中性版本：保持叙述距离稳定、句法服务行动和感知、意象来自场景物理细节、心理通过动作和选择呈现，并避免 AI 腔。"
    return (
        STYLE_GENERATION_STANDARD
        + "\n当前状态：已加载文风来源 `"
        + _rel(style_path, root)
        + "`。生成前必须先把该文风来源转译为本场景的叙述距离、句法节奏、意象系统、心理呈现、对白策略和标点节奏。"
    )


def _render_review_notes_standard(root: Path, scene_id: str, review_path: Path | None) -> str:
    if review_path is None:
        return """# AgentReview 小修约束

当前未发现上一轮平台 Agent 场景审查。若这是初稿生成，按 canon、人物、文风、预算和输出契约创作；若这是修订稿，应先补齐或读取上一轮 review。"""
    if review_path.suffix.lower() == ".json":
        payload = _read_json(review_path)
        conclusion = str(payload.get("conclusion") or "").strip()
        warnings = _json_list(payload.get("warnings"))
        revision_actions = _json_list(payload.get("revision_actions"))
        style_notes = _json_list(payload.get("style_notes"))
        style_adherence_status, style_adherence_notes = _style_adherence_notes(payload)
        if conclusion in {"revise_required", "reject"} or style_adherence_status in {"revise_required", "reject"}:
            return _review_notes_block(
                root,
                review_path,
                f"上一轮平台 Agent 场景审查结论为 `{conclusion or 'unknown'}`，文风执行门禁为 `{style_adherence_status or 'unknown'}`。这不是小修；不得直接润色通过，必须围绕 blocking issues / revision_actions / style_adherence 重写或退回审查。",
                revision_actions,
                warnings,
                style_notes,
                style_adherence_notes,
            )
        if conclusion == "pass_with_notes" or style_adherence_status == "pass_with_notes":
            return _review_notes_block(
                root,
                review_path,
                f"上一轮平台 Agent 场景审查结论为 `{conclusion or 'unknown'}`，文风执行门禁为 `{style_adherence_status or 'unknown'}`。写作 agent 不得把它当成完全通过；本轮必须执行轻微修订，或在“需要人工确认”中逐条说明无法执行的理由。",
                revision_actions,
                warnings,
                style_notes,
                style_adherence_notes,
            )
        if conclusion == "pass":
            return f"""# AgentReview 小修约束

已加载 `{_rel(review_path, root)}`。上一轮平台 Agent 审查结论为 `pass`，当前没有强制小修项；仍须遵守 canon、人物、文风、预算、标点和输出契约。"""
        return f"""# AgentReview 小修约束

已加载 `{_rel(review_path, root)}`，但未识别到有效 conclusion。写作前先检查该 review 是否完整；不要把缺失结论当成通过。"""
    text = _read(review_path)
    conclusion_match = re.search(r"(?m)^-\s*结论：\s*`?([^`\s]+)`?\s*$", text)
    conclusion = conclusion_match.group(1).strip() if conclusion_match else ""
    if conclusion == "pass_with_notes":
        return f"""# AgentReview 小修约束

已加载 `{_rel(review_path, root)}`。静态审查结论为 `pass_with_notes`：写作 agent 必须处理报告中的 low 级问题或在“需要人工确认”中说明豁免，不得直接视为完全通过。"""
    return f"""# AgentReview 小修约束

已加载 `{_rel(review_path, root)}`。当前静态审查结论为 `{conclusion or "unknown"}`；如果不是 `pass`，写作前先读取问题摘要并处理。"""


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

写作 agent 必须按以下顺序执行，不能只把它们当成审查清单：

1. Canon / 用户明确约束优先：不得改动已确认事实、适用范围、时间线、角色身份、规则边界和用户给定方向。
2. 场景目标与编排包优先：正式生成必须存在 composition，并先执行 selected branch、beats、subtext、dialogue intents 和 prose seed；偏离必须写入“需要人工确认”。仅内部实验可显式缺省 composition。
3. 人物逻辑优先：行动来自 BDI、当前信息差、关系压力、道德边界和 hidden background_story 的隐性影响，不为方便剧情强行转向。
4. 文风优先级：{_loaded_label(style_path, root, "已加载", "未加载")}。文风改变表达机制，不覆盖事实。
5. 读者体验与章节义务：长篇正式生成必须有 ready 的 reader_experience_contract。每场要推进读者问题、承诺回报、暂扣信息、兑现/延迟、张力来源和读后余味，不能只把剧情写成摘要。
6. 叙事节奏与场景桥接：状态 `{rhythm_status}`。开头接住入场压力，中段有 scene_turn，过场快速通过，关键选择放慢，结尾给下一场留下 outgoing_hook；不要把所有场景写成同一种平均节奏。
7. 长篇预算：{_loaded_label(word_budget_path, root, "已加载", "未加载")}。场景必须承担明确叙事功能，不用空泛描写灌字数，也不把剧情量压缩成摘要；目标单位是中文内容字符，机器非空白字符只作诊断。
8. AgentReview 小修：{_loaded_label(review_notes_path, root, "已加载", "未加载")}。若上一轮为 pass_with_notes，必须执行小修或逐条说明豁免。
9. 标点与 AI 腔：遵守标准中文标点，禁用机械“不是……而是……”和“不是……——是”等生硬对照，不判断为合理修辞；禁用“并不是……只是……”“看似……其实……”“表面上……实则……”等换皮转折。正式正文原则上不用破折号，孤立破折号需逐句复核，超过约 2% 叙事单元密度或替代转折时必须修订；一句话超过三个逗号通常要拆句。转折由动作、信息差、因果和人物选择产生，器官轮岗、万能占位、比喻依赖、抽象总结、解释性心理标签、模板转折、景物强制同步、对称排比和金句化收束按约 2% 密度门禁控制。若保留显式转折，必须在后续修订/审查中能通过反规避负担证明。
10. 输出边界：只输出候选正文和状态变化候选；不输出工作流、分析、自检表、AGENT_TASK、prompt manifest、canon 解释或审查过程。
"""


def _loaded_label(path: Path | None, root: Path, loaded: str, missing: str) -> str:
    return f"{loaded} `{_rel(path, root)}`" if path else missing


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


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


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
