"""Task contracts for the tool-layer platform agent.

These helpers do not call a local model, dry-run provider, or HTTP endpoint.
They write explicit task sidecars for the Codex/Claude layer that loaded this
skill, then downstream gates validate the artifacts that platform agent writes.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re

from .agent_tasks import write_agent_tasks
from .anti_ai_style import ANTI_EVASION_REVISION_PROTOCOL, ANTI_EVASION_SHORT_RULE, render_ai_style_lint_block
from .asset_workshop import ASSET_CANDIDATE_DIRS, ASSET_SCHEMA_NAMES, ASSET_TYPES
from .asset_context import compact_asset_context_paths
from .context_broker import default_context_trace_path
from .creative_quality import (
    creative_quality_profile_exists,
    creative_quality_profile_path,
    load_creative_quality_profile,
    render_creative_quality_prompt,
)
from .draft_text import count_delivery_chars, final_body_from_workbench_text
from .narrative_rhythm import narrative_rhythm_contract, render_narrative_rhythm_contract
from .new_character_register import render_new_character_register_contract
from .punctuation_standard import PUNCTUATION_STANDARD_SHORT_RULE
from .reader_experience import reader_experience_adherence_for_body, reader_experience_contract, scene_chapter_obligation_id
from .resources import engine_path
from .style_prompt import STYLE_PROMPT_LENGTH_RULE, STYLE_PROMPT_QUALITY_RULE
from .word_budget import scene_word_budget_contract, word_budget_adherence_for_body


@dataclass(frozen=True)
class PlatformAgentTaskResult:
    task_path: Path
    expected_report_path: Path
    expected_json_path: Path


def write_platform_scene_review_task(
    root: Path,
    *,
    scene_path: Path,
    draft_path: Path,
    report_path: Path | None = None,
    json_path: Path | None = None,
    materialization_scope: str = "full",
) -> PlatformAgentTaskResult:
    scene_id = scene_path.stem
    report = report_path or root / "reviews" / "agent" / f"{scene_id}_scene_review.md"
    json_output = json_path or root / "reviews" / "agent" / f"{scene_id}_scene_review.json"
    context_path = root / "memory" / "context_packets" / f"{scene_id}.md"
    context_trace_path = default_context_trace_path(context_path)
    source_paths = [scene_path, draft_path]
    if context_path.exists():
        source_paths.append(context_path)
    if context_trace_path.exists():
        source_paths.append(context_trace_path)
    composition_json = root / "drafts" / "compositions" / f"{scene_id}_composition.json"
    if composition_json.exists():
        source_paths.append(composition_json)
    obligation_path = root / "plot" / "chapter_obligations" / f"{scene_chapter_obligation_id(root, scene_path)}.json"
    if obligation_path.exists():
        source_paths.append(obligation_path)
    _extend_unique(source_paths, _style_source_paths(root))
    quality_profile = load_creative_quality_profile(root)
    if creative_quality_profile_exists(root):
        source_paths.append(creative_quality_profile_path(root))
    draft_text = _read_optional(draft_path)
    candidate_sha256 = hashlib.sha256(draft_path.read_bytes()).hexdigest()
    body = final_body_from_workbench_text(draft_text)
    style_lint_block = render_ai_style_lint_block(body or draft_text, profile=quality_profile, scope=scene_id)
    word_budget_adherence = word_budget_adherence_for_body(
        root,
        scene_path,
        body,
        materialization_scope=materialization_scope,
    )
    reader_adherence = reader_experience_adherence_for_body(root, scene_path, body)
    rhythm_contract_text = render_narrative_rhythm_contract(root, scene_path, composition_json if composition_json.exists() else None)
    new_character_contract = render_new_character_register_contract()
    task_path = json_output.with_suffix(".agent_tasks.md")
    write_agent_tasks(
        task_path,
        title=f"formal scene review {scene_id}",
        root=root,
        source_paths=source_paths,
        notes=[
            "这是正式发布门禁任务：由装载本 Skill 的平台 agent 完成。",
            "不要调用本地 dry-run、http-chat、外部 agent 服务或隐藏 provider。",
            f"完成后写入 JSON：{_rel(json_output, root)}",
            f"完成后写入 Markdown 报告：{_rel(report, root)}",
            f"本次审查正文 SHA-256：{candidate_sha256}；JSON 必须原样写入 candidate_sha256。",
        ],
        tasks=[
            (
                "读取审查材料",
                """读取 scene.yaml、draft markdown、context packet、context trace 和已挂载 style prompt/profile。先用 context trace 核对本次上下文实际加载了哪些 canon、character、style、plot、word-budget 和 retrieval 文件；若 trace 缺失或显示 required context 未加载，审查不得给出 clean pass。确认本场景的 canon 约束、人物 BDI、hidden background_story、场景目标、输出状态和用户约束。""",
            ),
            (
                "进行语义审查",
                f"""以平台 agent 的文学判断审查人物行为逻辑、背景故事隐性因果、canon 风险、剧情推进、新角色登记、文风执行、套路化/同质化风险、标点规范和需要修订的动作。若正文出现 scene.yaml 与正式 characters 中没有的人物，不得默认放过；先按新角色登记契约分类。标点审查规则：{PUNCTUATION_STANDARD_SHORT_RULE}""",
            ),
            (
                "执行新角色登记门禁",
                f"""{new_character_contract}

审查时必须填写 JSON 的 `new_character_register`。若只有一次性路人，`status=ephemeral_only` 且写 `waiver_reason`；若有命名、复用、掌握线索、改变关系或推动主线的新角色，必须有 candidate asset、review、用户 approval 或 promotion。`needs_candidate` / `needs_review` / `needs_approval` 不得 clean pass。""",
            ),
            (
                "处理确定性 Style Lint 证据",
                f"""{render_creative_quality_prompt(quality_profile, scope=scene_id)}

{style_lint_block}

以上 Style Lint 是审查前由代码自动检出的证据。若存在 medium 或更高风险，必须在 JSON 的 blocking_issues、warnings、revision_actions 或 style_notes 中处理，不得仅用“整体可读”“属于合理修辞”带过。若认为某个 low 风险可保留，必须在 Markdown 报告说明语义理由。禁止用批量脚本直接删除否定、破折号或心理表达。{ANTI_EVASION_SHORT_RULE}""",
            ),
            (
                "执行反规避审查",
                f"""{ANTI_EVASION_REVISION_PROTOCOL}

若本次审查对象是修订候选，必须对照上一轮 review notes、Style Lint 证据和原草稿，检查是否把生硬对照换成另一种显式转折。若发现换皮转折，`conclusion` 不得为 `pass`；应写入 `revision_actions`，要求改为动作、事实顺序、信息差或直接陈述。若确有转折必须保留，必须在 Markdown 报告写“反规避负担证明”，并从不合理角度提出反驳。""",
            ),
            (
                "执行挂载文风门禁",
                """若项目存在 `style/active_style_skill.json` 或已挂载 style prompt/profile，必须正式判断文风是否已经塑造正文表达，而不是只作为参考材料出现。对照挂载文风审查叙述距离、视角稳定性、句法和段落节奏、意象/感官路由、心理呈现、对白语气、标点停顿节奏、AI 腔规避和禁止倾向。`style_adherence.status` 只能取 `pass`、`pass_with_notes`、`revise_required` 或 `not_applicable`；有挂载文风时不得使用 `not_applicable`。若正文基本忽略挂载文风，必须用 `revise_required` 并给出可执行重写动作。""",
            ),
            (
                "执行字数预算硬门禁",
                f"""使用清洗后的可交付正文做字数判断，不得统计状态变化候选、canon 说明、workflow 痕迹、scene 编号或文件路径。本次确定性计数：
{json.dumps(word_budget_adherence, ensure_ascii=False, indent=2)}
若 `status` 为 under_target、over_target、revise_required、missing 或 needs_expansion，`conclusion` 不得为 pass。若字数在区间内，还要判断 narrative_load 是否真实完成；不能靠空泛描写、重复心理解释或流程文本填字数。""",
            ),
            (
                "执行读者体验硬门禁",
                f"""使用章节义务和读者体验契约审查正文是否真正推进读者期待，而不是只完成事件摘要。本次结构门禁：
{json.dumps(reader_adherence, ensure_ascii=False, indent=2)}
若 `status` 不是 pass 或 not_required，`conclusion` 不得为 pass。即使结构通过，也必须语义判断 reader_question、promised_reward、withheld_information、payoff_or_delay、emotional_curve、tension_source、curiosity_hook、freshness_requirement、anti_summary_requirement、reader_aftertaste 是否在正文中得到执行。""",
            ),
            (
                "执行叙事节奏与场景桥接门禁",
                f"""{rhythm_contract_text}

审查正文是否接住入场压力、完成本场 scene_turn、在过场/高潮之间形成详略差异，并把 outgoing_hook 交给下一场。若全场只是平均叙述、段落功能重复、场景之间缺少承接，`conclusion` 不得为 pass；JSON 必须填写 `narrative_rhythm_adherence`。

审查还必须判断 Scene Function Gate：本场是否推进主线、改变关系、制造误判、兑现/设置问题、改变人物选择、扩大代价或转移读者认知之一。检查 Reader Question / Promise-Payoff：本场提出、延迟、兑现或加压了哪些读者问题和承诺。检查 Narrative Distance：是否一直贴脸解释心理，还是按场景功能调整远近。检查 Texture Variety：本场和相邻场景是否全是同一种材料。若这些关键项缺失，不能 clean pass。""",
            ),
            (
                "写入正式 JSON",
                f"""创建或覆盖 `{_rel(json_output, root)}`，JSON 必须符合 `scene_review.v1`：
{{
  "schema": "literary-engineering-workbench/scene-review-agent/v1",
  "scene_id": "{scene_id}",
  "candidate_sha256": "{candidate_sha256}",
  "conclusion": "pass | pass_with_notes | revise_required | reject",
  "summary": "...",
  "blocking_issues": [],
  "warnings": [],
  "revision_actions": [],
  "character_logic": [],
  "canon_risks": [],
  "style_notes": [],
  "style_adherence": {{
    "status": "pass | pass_with_notes | revise_required | not_applicable",
    "style_profile": "style/active_style_skill.json 或 n/a",
    "evidence": [],
    "deviations": [],
    "revision_actions": []
  }},
  "creative_quality_profile": {{
    "path": "{_rel(creative_quality_profile_path(root), root) if creative_quality_profile_exists(root) else 'implicit-default'}",
    "revision": {quality_profile.get('revision', 1)},
    "digest": "{quality_profile.get('digest', '')}",
    "name": "{quality_profile.get('name', '')}"
  }},
  "revision_integrity": {{
    "status": "pass | revise_required | not_applicable",
    "anti_evasion_checked": true,
    "evasion_risks": [],
    "evasion_risks_unresolved": [],
    "retained_transitions": [],
    "burden_of_proof": [],
    "message": ""
  }},
  "word_budget_adherence": {{
    "status": "pass | not_required | under_target | over_target | revise_required",
    "formal_count_policy": "pass/fail uses clean_body_chinese_chars against target_chinese_chars/min_chinese_chars/max_chinese_chars; target_words/min_words/max_words are legacy aliases only",
    "target_words": {word_budget_adherence.get("target_words", 0)},
    "min_words": {word_budget_adherence.get("min_words", 0)},
    "max_words": {word_budget_adherence.get("max_words", 0)},
    "clean_body_words": {word_budget_adherence.get("clean_body_words", 0)},
    "target_chinese_chars": {word_budget_adherence.get("target_chinese_chars", 0)},
    "min_chinese_chars": {word_budget_adherence.get("min_chinese_chars", 0)},
    "max_chinese_chars": {word_budget_adherence.get("max_chinese_chars", 0)},
    "clean_body_chinese_chars": {word_budget_adherence.get("clean_body_chinese_chars", 0)},
    "clean_body_machine_chars": {word_budget_adherence.get("clean_body_machine_chars", 0)},
    "narrative_load_satisfied": true,
    "message": "{str(word_budget_adherence.get("message") or "").replace('"', "'")}"
  }},
  "reader_experience_adherence": {{
    "status": "{reader_adherence.get("status", "")}",
    "message": "{str(reader_adherence.get("message") or "").replace('"', "'")}",
    "reader_promise_satisfied": true,
    "semantic_review_required": true
  }},
  "narrative_rhythm_adherence": {{
    "status": "pass | pass_with_notes | revise_required | not_applicable",
    "rhythm_executed": true,
    "bridge_executed": true,
    "flatness_risks": [],
    "revision_actions": []
  }},
  "canon_writeback": {{
    "status": "pass | not_required | pending_canon_evolve | unknown",
    "canon_change": true | false | "unknown",
    "no_canon_change_reason": "",
    "candidate_patch": "canon/patches/{scene_id}_canon_patch.json 或空"
  }},
  "new_character_register": {{
    "schema": "literary-engineering-workbench/new-character-register/v0.1",
    "status": "none | existing_only | ephemeral_only | resolved | needs_candidate | needs_review | needs_approval",
    "introduced": [],
    "ephemeral_waivers": [],
    "blocking_issues": []
  }},
  "source_paths": []
}}
`conclusion=pass` 且 warnings / revision_actions / style_notes / style_adherence 偏差为空，且 word_budget_adherence.status 为 pass 或 not_required、narrative_load_satisfied=true，reader_experience_adherence.status 为 pass 或 not_required、reader_promise_satisfied=true，narrative_rhythm_adherence.status 为 pass 或 not_applicable，且 new_character_register.status 为 none / existing_only / ephemeral_only / resolved，才可进入 clean ready。`pass_with_notes` 必须先进入 revise-scene 或记录明确 waiver，不能直接章节装配或导出；新增事实仍保持候选。若正文产生持续世界事实，canon_writeback.canon_change 必须为 true，并在 promote/state 后继续运行 canon-evolve。若无持续世界事实，必须写 no_canon_change_reason。""",
            ),
            (
                "处理 pass_with_notes 语义",
                """如果 conclusion=`pass_with_notes`，必须满足三条：1）warnings 或 revision_actions 至少有一项具体、可执行、局部的小修；2）revision_actions 必须说明写作 agent 应改哪类文字、信息、语气、标点或结构；3）next_gate 使用 `minor_revision_required` 或明确说明需要人工接受 notes 后才可装配。不得用 pass_with_notes 掩盖需要重写的问题；需要重写时用 revise_required。""",
            ),
            (
                "写入正式 Markdown 报告",
                f"""创建或覆盖 `{_rel(report, root)}`，说明结论、阻塞问题、修订动作、人物逻辑、canon 风险和风格备注。必须新增“新角色登记门禁”段落：列出正文是否出现新角色、哪些是一次性路人、哪些需要候选资产/审查/approval/promotion。必须新增“文风执行门禁”段落：写明 style_adherence.status、证据、偏差和修订动作。必须新增“字数预算门禁”段落：写明目标/最低/最高/清洗后正文中文内容字符、机器非空白字符诊断、叙事负载是否满足、是否存在灌水或摘要化。必须新增“读者体验门禁”段落：写明读者问题、承诺回报、暂扣信息、兑现/延迟、张力来源、反摘要要求和读后余味是否被正文执行。必须新增“叙事节奏与场景桥接门禁”段落：写明入场压力、本场转折、详略节奏和出场钩子是否执行。必须新增“Canon 写回判断”段落：说明是否有持续世界事实，若无写理由，若有列候选 patch 路径。必须新增“反规避负担证明”段落：列出是否存在换皮转折、保留显式转折的理由、批判性反驳和最终判断。若结论为 pass_with_notes，必须新增“小修闭环”段落：列出 writing agent 必须执行的小修项、可接受的最小改动、需要人工确认的 notes。不要写入 `[AGENT_TASK: ...]`。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, report, json_output)


def write_platform_scene_generation_task(
    root: Path,
    *,
    scene_path: Path,
    context_path: Path,
    composition_path: Path | None = None,
    prompt_manifest_path: Path | None = None,
    candidate_path: Path | None = None,
    manifest_path: Path | None = None,
) -> PlatformAgentTaskResult:
    scene_id = scene_path.stem
    candidate = candidate_path or root / "drafts" / "candidates" / f"{scene_id}-platform-agent.md"
    manifest = manifest_path or candidate.with_suffix(".json")
    context_trace_path = default_context_trace_path(context_path)
    source_paths = [scene_path, context_path]
    if context_trace_path.exists():
        source_paths.append(context_trace_path)
    if composition_path and composition_path.exists():
        source_paths.append(composition_path)
    if prompt_manifest_path and prompt_manifest_path.exists():
        source_paths.append(prompt_manifest_path)
    obligation_path = root / "plot" / "chapter_obligations" / f"{scene_chapter_obligation_id(root, scene_path)}.json"
    if obligation_path.exists():
        source_paths.append(obligation_path)
    _extend_unique(source_paths, _style_source_paths(root))
    quality_profile = load_creative_quality_profile(root)
    if creative_quality_profile_exists(root):
        source_paths.append(creative_quality_profile_path(root))
    word_budget_contract = scene_word_budget_contract(root, scene_path)
    reader_contract = reader_experience_contract(root, scene_path)
    rhythm_contract = narrative_rhythm_contract(root, scene_path, composition_path)
    rhythm_contract_text = render_narrative_rhythm_contract(root, scene_path, composition_path)
    new_character_contract = render_new_character_register_contract()
    task_path = candidate.with_suffix(".agent_tasks.md")
    write_agent_tasks(
        task_path,
        title=f"platform scene generation {scene_id}",
        root=root,
        source_paths=source_paths,
        notes=[
            "由平台 agent 创作候选正文；不要调用本地 dry-run、http-chat 或外部 agent。",
            "prompt manifest 是给平台 agent 的审计和提示词材料，不是外部 provider 调用记录。",
            f"完成后写入候选 Markdown：{_rel(candidate, root)}",
            f"完成后写入候选 manifest JSON：{_rel(manifest, root)}",
        ],
        tasks=[
            (
                "确认正式路线 provenance",
                """在写正文前，先确认本任务来自 `generate-scene`，并且 source artifacts 中存在 prompt manifest、context packet、context trace、composition packet。composition JSON 必须包含 `formal_cli_provenance.created_by=compose-scene`，且本候选的 `.agent_tasks.md`、`.prompt.json`、预期 candidate manifest 路径齐全。若缺失，停止正文生成，把本轮标记为 formal route blocked，不得手写文件冒充正式候选。""",
            ),
            (
                "读取创作材料",
                f"""读取 scene.yaml、context packet、context trace、composition packet、prompt manifest、style prompt/profile、长篇字数预算、章节义务/读者体验契约、上一轮 AgentReview 小修约束、生成前最终硬约束摘要、标点规范和相关 canon/character 文件。用 context trace 复核上下文实际来源：若 trace 缺少 scene/project required context，或没有加载本场参与角色、必要 canon、已挂载文风、场景字数预算或 reader_experience_contract，停止正文生成并先修复 context。确认人物 BDI、hidden background_story、scene goal、output_state、用户约束、文风生成标准、长篇字数预算标准、读者体验硬属性、pass_with_notes 小修项和标点边界。标点规则：{PUNCTUATION_STANDARD_SHORT_RULE}""",
            ),
            (
                "执行生成前最终硬约束摘要",
                f"""先读取 prompt manifest 的 generation_standards.hard_constraints 和 creative_quality_profile，把 canon、场景编排、人物逻辑、文风、字数预算、AgentReview notes、标点和输出边界压缩成内部执行顺序。该摘要必须指导正文生成，但不得作为分析、自检表或工作流痕迹输出。

{render_creative_quality_prompt(quality_profile, scope=scene_id)}""",
            ),
            (
                "执行反规避与朴素叙述禁区",
                f"""读取 prompt manifest 的 generation_standards.anti_evasion，并执行以下约束：{ANTI_EVASION_SHORT_RULE}
正文中不要先制造生硬转折再期待后续审查修掉。若场景确实需要信息反转、误判修正或因果揭示，优先用动作、事实顺序、信息差、物证、对话错位或人物选择完成，而不是用显式对照句。该判断只指导写作，不得作为分析或自检表输出。""",
            ),
            (
                "执行生成前文风标准",
                """在写候选正文前，先根据 prompt manifest 的 generation_standards.style 和已挂载 style prompt/profile，内部建立本场景的文风执行策略：叙述距离、句法/段落节奏、意象/感官系统、心理呈现、对白密度与语气、标点停顿节奏。该策略只用于指导写作，不得作为分析、自检表或工作流痕迹写入候选正文。""",
            ),
            (
                "执行生成前字数预算标准",
                f"""在写候选正文前，检查 prompt manifest 的 generation_standards.word_budget 和 scene_word_budget_contract。本场景预算硬属性如下：
{json.dumps(word_budget_contract, ensure_ascii=False, indent=2)}
若 status 不是 pass 或 not_required，停止正文生成并回到 longform-planning。若 status=pass，正文清洗后的可交付部分必须落在 min_chinese_chars 到 max_chinese_chars 之间；计入汉字和中文标点，机器非空白字符只作为诊断映射。同时满足 narrative_load；不得靠水化描写拉长，也不得把预算需要的剧情量压缩为摘要。""",
            ),
            (
                "执行生成前读者体验硬属性",
                f"""在写候选正文前，检查 prompt manifest 的 generation_standards.reader_experience_contract 和章节义务文件。本场景读者体验硬属性如下：
{json.dumps(reader_contract, ensure_ascii=False, indent=2)}
若 status 不是 pass 或 not_required，停止正文生成并先运行 chapter-obligation。若 status=pass，正文必须执行 reader_question、promised_reward、withheld_information、payoff_or_delay、emotional_curve、tension_source、curiosity_hook、freshness_requirement、anti_summary_requirement 和 reader_aftertaste。不能只写“发生了什么”，还要让读者知道为什么继续读、期待被怎样兑现或延迟。""",
            ),
            (
                "执行生成前叙事节奏与场景桥接",
                f"""{rhythm_contract_text}

写正文时必须按 tension_curve 的 entry / peak / exit（1-5）执行张力变化，让开头接住 incoming_pressure，中段完成 scene_turn，结尾交出 outgoing_hook。过场不要恋战，高潮不要靠堆形容词撑长；用动作、信息差、人物选择和代价调整节奏。候选 manifest 必须记录 narrative_rhythm_contract 和 narrative_rhythm_standard_applied=true。

同时执行 Scene Function Gate、Reader Question Ledger、Promise / Payoff Ledger、Narrative Distance Control 和 Texture Variety Pass：确认本场功能不是“补设定/聊天”，读者问题和承诺有管理，叙述距离不会持续贴脸解释心理，本场材料与上下场形成变化。""",
            ),
            (
                "执行 AgentReview 小修约束",
                """若 prompt manifest 中 generation_standards.review_notes_loaded=true，尤其上一轮结论为 pass_with_notes，必须执行 revision_actions / warnings / style_notes 中的局部小修。候选 manifest 记录 pass_with_notes_actions_applied=true；若任何小修无法执行，写入“需要人工确认”，不得静默忽略。""",
            ),
            (
                "生成候选正文",
                f"""创建或覆盖 `{_rel(candidate, root)}`。正文必须包含 `## 正文候选`、`## 状态变化候选` 和 `## 新角色候选登记`，不得写入 `[AGENT_TASK: ...]`，不得把新增事实写成已确认 canon。背景故事只通过选择、回避、误判、语气或关系压力间接影响行动。正文必须先执行文风生成标准、读者体验硬属性、字数预算标准、反规避协议和新角色登记契约，再通过标准标点和降低 AI 腔自检。""",
            ),
            (
                "生成候选 manifest",
                f"""创建或覆盖 `{_rel(manifest, root)}`，记录 schema、scene_id、candidate、prompt_manifest、source_paths、generated_by=`platform-agent`、created_at、style_profile/context/composition 引用、creative_quality_profile_digest=`{quality_profile.get('digest', '')}`、style_generation_standard_applied=true、reader_experience_contract、reader_experience_standard_applied=true/false、word_budget_standard_applied=true/false、narrative_rhythm_contract、narrative_rhythm_standard_applied=true/false、hard_constraints_applied=true、anti_evasion_protocol_applied=true、pass_with_notes_actions_applied=true/false、word_budget_contract、clean_body_chinese_chars、clean_body_machine_chars、word_budget_adherence.status、new_character_register、canon_change、no_canon_change_reason 和待审查事项。

本场叙事节奏契约：
{json.dumps(rhythm_contract, ensure_ascii=False, indent=2)}

{new_character_contract}

若正文没有新角色，写 status=none。若只有一次性路人，写 status=ephemeral_only 并列明 waiver_reason。若引入会复用、掌握线索、推动关系或改变世界状态的新角色，先用 `agent-create-character` / `asset-create --asset-type character` 生成候选资产，再把 candidate_path 写入 register；未完成时 status 必须是 needs_candidate/needs_review/needs_approval，不能伪装为 clean。

Canon 声明不得留空：如果正文产生会跨场景持续约束未来创作的世界事实，写 `canon_change=true`；如果没有，写 `canon_change=false` 且给出 `no_canon_change_reason`；如果无法判断，写 `canon_change=\"unknown\"`，后续 route 会强制运行 canon-evolve，不得静默跳过。""",
            ),
            (
                "后续门禁",
                """候选生成后不得直接 promote。平台 agent 或用户需要审查候选，再进入 promote-candidate、review-scene、平台 Agent 场景审查和 state-evolve。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, candidate, manifest)


def write_platform_asset_creation_task(
    root: Path,
    *,
    asset_type: str,
    brief: str = "",
    target_id: str = "",
    source: Path | None = None,
    candidate_path: Path | None = None,
    report_path: Path | None = None,
) -> PlatformAgentTaskResult:
    normalized = _normalize_asset_type(asset_type)
    schema_name = ASSET_SCHEMA_NAMES[normalized]
    schema_path = engine_path("schemas", "agent_outputs", f"{schema_name}.schema.json")
    schema_contract = json.loads(schema_path.read_text(encoding="utf-8"))
    schema_summary = json.dumps(
        {
            "schema_value": schema_contract.get("schema_value"),
            "required": schema_contract.get("required", []),
            "types": schema_contract.get("types", {}),
        },
        ensure_ascii=False,
        indent=2,
    )
    candidate_id = _asset_candidate_id(normalized, target_id or brief)
    candidate = candidate_path or root / ASSET_CANDIDATE_DIRS[normalized] / f"{candidate_id}.json"
    report = report_path or candidate.with_suffix(".md")
    source_paths = [*compact_asset_context_paths(root), schema_path]
    resolved_source = _resolve_optional(root, source)
    if resolved_source:
        source_paths.append(resolved_source)
    task_path = candidate.with_suffix(".agent_tasks.md")
    write_agent_tasks(
        task_path,
        title=f"platform asset creation {normalized}",
        root=root,
        source_paths=source_paths,
        notes=[
            "由平台 agent 创建候选资产；不要调用本地 dry-run、http-chat 或外部 agent。",
            f"资产类型：{normalized}",
            f"目标 schema：{schema_name}",
            "候选 JSON 必须是该 schema 的单个根对象；不要自创 `characters`、`items` 等外层数组包装。",
            f"完成后写入候选 JSON：{_rel(candidate, root)}",
            f"完成后写入候选 Markdown 报告：{_rel(report, root)}",
        ],
        tasks=[
            (
                "读取项目约束",
                """读取 project.yaml、canon、characters、plot、style 挂载和对应 schema。确认新增内容只能是候选，不能覆盖正式 canon、characters 或 plot。""",
            ),
            (
                "生成候选资产",
                f"""按 `{schema_name}` 创建或覆盖 `{_rel(candidate, root)}`。候选必须是一个根对象，字段和值严格满足下面的机器合同；不要把角色放进 `characters` 数组，不要把 `promotion_notes` 写成对象：

```json
{schema_summary}
```

必须包含 `schema`、`candidate_id`、`risks`、`source_paths` 和 `promotion_notes`；如为角色相关资产，必须让 background_story 只作为隐性行为因果。创作简述：{brief or "使用项目 premise 与现有材料。"} 目标 ID：{target_id or "n/a"}。""",
            ),
            (
                "写入候选说明",
                f"""创建或覆盖 `{_rel(report, root)}`，说明候选摘要、风险、需要用户确认的事项、后续审查步骤和不得自动晋升的边界。不要写入 `[AGENT_TASK: ...]`。""",
            ),
            (
                "后续门禁",
                """候选资产生成后，平台 agent 需要进行 schema/语义审查，再由用户或审批记录决定是否 promote。不得直接写入正式项目文件。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, report, candidate)


def write_project_seed_asset_tasks(root: Path) -> list[PlatformAgentTaskResult]:
    """Create stable world and protagonist task sidecars for a new project."""

    project_root = root.resolve()
    if not (project_root / "project.yaml").is_file():
        raise FileNotFoundError(f"project.yaml not found: {project_root}")
    shared_brief = (
        "基于 project.yaml、用户方向记忆、已经确认的长篇预算与候选大纲，建立足以约束后续创作的基础资产。"
        "不要重复大纲；只提取会持续影响人物选择、冲突、代价和场景因果的设定。"
    )
    specs = (
        (
            "world",
            "world-foundation",
            project_root / ASSET_CANDIDATE_DIRS["world"] / "world-foundation.json",
            shared_brief + "世界资产必须给出可执行规则、限制、代价与不可破坏的边界。",
        ),
        (
            "character",
            "protagonist-foundation",
            project_root / ASSET_CANDIDATE_DIRS["character"] / "protagonist-foundation.json",
            shared_brief + "角色资产聚焦主角，必须包含动机、恐惧、道德边界与隐性的 background_story 行为因果。",
        ),
    )
    return [
        write_platform_asset_creation_task(
            project_root,
            asset_type=asset_type,
            brief=brief,
            target_id=target_id,
            candidate_path=candidate_path,
        )
        for asset_type, target_id, candidate_path, brief in specs
    ]


def write_platform_asset_review_task(
    root: Path,
    *,
    candidate_path: Path,
    report_path: Path | None = None,
    json_path: Path | None = None,
) -> PlatformAgentTaskResult:
    candidate = candidate_path if candidate_path.is_absolute() else root / candidate_path
    candidate_id = candidate.stem
    report = report_path or root / "reviews" / "assets" / f"{candidate_id}_review.md"
    json_output = json_path or report.with_suffix(".json")
    task_path = json_output.with_suffix(".agent_tasks.md")
    source_paths = [candidate, *compact_asset_context_paths(root)]
    write_agent_tasks(
        task_path,
        title=f"platform asset review {candidate_id}",
        root=root,
        source_paths=source_paths,
        notes=[
            "由平台 agent 审查候选资产；不要调用本地 dry-run、http-chat 或外部 agent。",
            "本任务只负责审查，不修改候选；pass、failed、revise_required 都是可正式提交的审查结论。",
            "如需修订，必须如实写 revise_required；后续独立 revision task 会修改候选并触发新一轮复审。",
            "revision_actions 只能要求修改当前 candidate 文件及其说明。新增其他角色、世界规则或场景等跨任务依赖只能写入 warnings / promotion_risks，不能阻塞当前候选。",
            f"完成后写入 JSON：{_rel(json_output, root)}",
            f"完成后写入 Markdown 报告：{_rel(report, root)}",
        ],
        tasks=[
            (
                "审查候选资产",
                """读取候选 JSON，对照对应 schema、项目 canon、角色事实、文风挂载和用户约束。检查新增事实是否仍是候选、角色背景故事是否只作为行为因果、世界规则是否引入万能解法、剧情大纲是否破坏既有伏笔。""",
            ),
            (
                "写入审查 JSON",
                f"""创建或覆盖 `{_rel(json_output, root)}`。schema 必须精确为 `literary-engineering-workbench/candidate-asset-review/v0.1`，并至少包含 candidate、candidate_id、asset_type、status(pass|failed|revise_required)、blocking_issues、warnings、revision_actions、promotion_risks、reviewed_at。非通过结论必须给出可执行的 blocking_issues 或 revision_actions；revision_actions 的 target 必须精确指向当前候选 `{_rel(candidate, root)}` 或其字段锚点，不能要求本任务创建其他资产。不要为了推进流程伪造 pass。""",
            ),
            (
                "写入审查报告",
                f"""创建或覆盖 `{_rel(report, root)}`，说明是否可进入用户审批、必须修订项和不得自动晋升的原因。不要写入 `[AGENT_TASK: ...]`。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, report, json_output)


def write_platform_canon_review_task(root: Path) -> PlatformAgentTaskResult:
    report = root / "reviews" / "agent" / "canon_review.md"
    json_output = root / "reviews" / "agent" / "canon_review.json"
    sources = [
        root / "reviews" / "canon_lint.md",
        root / "reviews" / "canon_lint.json",
        root / "canon",
        root / "characters",
        root / "scenes",
        root / "plot",
    ]
    task_path = json_output.with_suffix(".agent_tasks.md")
    write_agent_tasks(
        task_path,
        title="formal canon and continuity review",
        root=root,
        source_paths=sources,
        notes=[
            "由平台 agent 审查 canon、角色、场景、章节和伏笔连续性。",
            "本任务不调用本地 dry-run、http-chat 或外部 agent。",
            "非通过结论可以正式提交；每条需要修复的 recommendation 必须包含精确 target_path、action 和 verification，供隔离修复任务限定写入范围。",
            f"完成后写入 JSON：{_rel(json_output, root)}",
            f"完成后写入 Markdown 报告：{_rel(report, root)}",
        ],
        tasks=[
            (
                "审查 canon lint 与项目状态",
                """读取 canon-lint 输出和项目目录，判断 blocking、warning、未确认事实、时间线风险、角色状态断裂和伏笔债务。""",
            ),
            (
                "写入正式 canon review",
                """按 `canon_review.v1` 写入 JSON，并在 Markdown 报告中给出需要修复、保留候选或请求用户确认的事项。pass_with_notes / revise_required / reject 都是合法结论，不得伪造 pass；非通过结论的 recommendations 必须为对象数组，每项包含位于 canon/、characters/、plot/、scenes/ 或 drafts/candidates/ 下的单个文本文件 target_path，以及 action、verification。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, report, json_output)


def write_platform_committee_task(
    root: Path,
    *,
    subject: str,
    source: Path | None = None,
) -> PlatformAgentTaskResult:
    safe_subject = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in subject).strip("-") or "subject"
    report = root / "reviews" / "agent" / f"committee_{safe_subject}.md"
    json_output = root / "reviews" / "agent" / f"committee_{safe_subject}.json"
    source_paths = [source] if source else []
    task_path = json_output.with_suffix(".agent_tasks.md")
    write_agent_tasks(
        task_path,
        title=f"formal review committee {subject}",
        root=root,
        source_paths=source_paths,
        notes=[
            "由平台 agent 扮演多个审稿视角完成综合判断。",
            "不要调用本地 dry-run、http-chat 或外部 agent。",
            "非通过建议可以正式提交；每个 action_item 或需要修复的 disagreement 必须携带精确 target_path、action 和 verification。",
            f"完成后写入 JSON：{_rel(json_output, root)}",
            f"完成后写入 Markdown 报告：{_rel(report, root)}",
        ],
        tasks=[
            (
                "多视角审查",
                """分别从总编辑、人物心理、canon、文风、可读性和反同质化角度审查 source artifact。""",
            ),
            (
                "形成综合建议",
                """按 `committee_review.v1` 写出最终建议、分歧、行动项和少数意见。approve_with_notes / revise / reject 均可如实提交；需要修复的 action_items / disagreements 必须写成对象并包含单个允许项目文本文件的 target_path、action、verification。不要把建议直接晋升为 canon 或发布决定。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, report, json_output)


def write_platform_json_task(
    root: Path,
    *,
    schema_name: str,
    task: str = "build-json",
    source: Path | None = None,
    target: str = "",
    output_dir: Path | None = None,
) -> PlatformAgentTaskResult:
    safe_schema = _safe_label(schema_name.replace(".", "-"))
    safe_task = _safe_label(task)
    out_dir = output_dir or root / "agents" / "platform_tasks" / f"{safe_task}_{safe_schema}_{_stamp()}"
    json_output = out_dir / "parsed_output.json"
    report = out_dir / "report.md"
    task_path = out_dir / "task.agent_tasks.md"
    sources = [engine_path("schemas", "agent_outputs", f"{schema_name}.schema.json")]
    resolved_source = _resolve_optional(root, source)
    if resolved_source:
        sources.append(resolved_source)
    write_agent_tasks(
        task_path,
        title=f"platform JSON task {task}",
        root=root,
        source_paths=sources,
        notes=[
            "由平台 agent 生成 JSON；不要调用本地 dry-run、http-chat 或外部 agent。",
            f"目标 schema：{schema_name}",
            f"目标对象：{target or 'n/a'}",
            f"完成后写入 JSON：{_rel(json_output, root)}",
            f"完成后写入 Markdown 报告：{_rel(report, root)}",
        ],
        tasks=[
            (
                "读取 schema 和材料",
                """读取 schema、source artifact 和 target 说明，确认输出只是候选 JSON，不得直接写入 canon、characters、plot、drafts 或 release。""",
            ),
            (
                "写入 JSON",
                f"""创建或覆盖 `{_rel(json_output, root)}`。JSON 必须符合 `{schema_name}`，并保留 source_paths、risks 或需要确认的字段。""",
            ),
            (
                "写入报告",
                f"""创建或覆盖 `{_rel(report, root)}`，说明生成依据、风险、需要用户确认的事项和后续验证命令。不要写入 `[AGENT_TASK: ...]`。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, report, json_output)


def write_platform_patch_plan_task(
    root: Path,
    *,
    target: str,
    source: Path | None = None,
    report_path: Path | None = None,
    json_path: Path | None = None,
) -> PlatformAgentTaskResult:
    safe_target = _safe_label(target.replace("/", "-").replace("\\", "-"))
    report = report_path or root / "agents" / "patch_plans" / f"{safe_target}_patch_plan.md"
    json_output = json_path or report.with_suffix(".json")
    task_path = json_output.with_suffix(".agent_tasks.md")
    sources = [root / target]
    resolved_source = _resolve_optional(root, source)
    if resolved_source:
        sources.append(resolved_source)
    sources.append(engine_path("schemas", "agent_outputs", "json_patch_plan.v1.schema.json"))
    write_agent_tasks(
        task_path,
        title=f"platform patch plan {target}",
        root=root,
        source_paths=sources,
        notes=[
            "由平台 agent 规划写回补丁；不要调用本地 dry-run、http-chat 或外部 agent。",
            "本任务只生成补丁计划，不直接修改目标文件。",
            f"完成后写入 JSON：{_rel(json_output, root)}",
            f"完成后写入 Markdown 报告：{_rel(report, root)}",
        ],
        tasks=[
            (
                "审查写回边界",
                """读取 target、source 和 json_patch_plan.v1 schema。确认哪些改动是候选、哪些需要用户审批、哪些会影响 canon/character/plot 的硬约束。""",
            ),
            (
                "写入补丁计划 JSON",
                f"""创建或覆盖 `{_rel(json_output, root)}`，按 `json_patch_plan.v1` 记录 operation、path、value、reason、risk 和 approval_required。不得直接应用补丁。""",
            ),
            (
                "写入补丁计划报告",
                f"""创建或覆盖 `{_rel(report, root)}`，给出变更摘要、风险和审批建议。不要写入 `[AGENT_TASK: ...]`。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, report, json_output)


def write_platform_style_prompt_task(
    profile_dir: Path,
    *,
    output: Path | None = None,
    json_path: Path | None = None,
) -> PlatformAgentTaskResult:
    profile = profile_dir.resolve()
    prompt = output if output and output.is_absolute() else profile / (str(output) if output else "style_prompt.md")
    json_output = json_path if json_path and json_path.is_absolute() else profile / (str(json_path) if json_path else "style_prompt.agent.json")
    task_path = prompt.with_suffix(".agent_tasks.md")
    sources = [
        profile / "style-profile.md",
        profile / "style_metrics.json",
        profile / "corpus_manifest.yaml",
        engine_path("schemas", "agent_outputs", "style_prompt.v1.schema.json"),
    ]
    write_agent_tasks(
        task_path,
        title="platform style prompt generation",
        root=profile,
        source_paths=sources,
        notes=[
            "由平台 agent 生成供 LLM 使用的文风约束提示词；不要调用本地 dry-run、http-chat 或外部 agent。",
            STYLE_PROMPT_LENGTH_RULE,
            STYLE_PROMPT_QUALITY_RULE,
            f"完成后写入提示词 Markdown：{_rel(prompt, profile)}",
            f"完成后写入 JSON：{_rel(json_output, profile)}",
        ],
        tasks=[
            (
                "读取文风证据",
                """读取 style-profile.md、style_metrics.json 和 corpus_manifest.yaml。把证据转译为可执行的 LLM 文风约束，而不是评论文章或统计摘要。""",
            ),
            (
                "写入文风提示词",
                f"""创建或覆盖 `{_rel(prompt, profile)}`。必须包含使用身份与适用边界、核心风格机制、叙述距离与视角、句法与节奏、标点节奏与标准标点边界、意象与感官调度、心理呈现与行为因果、对白与语气、禁止倾向、输出自检。正文必须控制在 500-2500 中文内容字符之间：计入汉字和中文标点，不计入 Markdown 标记、英文路径、代码围栏或空白；低于 500 视为文风约束不足，高于 2500 视为过度扩散。每个模块都要写成可执行规则，说明做什么、为什么、何时例外、如何自检；不要使用“优美、克制、文学性强”等空泛形容词替代规则。AI 腔边界必须保留：机械“不是……而是……”及其破折号/句号变体不判断为合理修辞；器官轮岗、万能占位、比喻依赖、抽象总结、模板转折和景物强制同步按约 2% 叙事单元密度门禁控制。标点边界必须保留：{PUNCTUATION_STANDARD_SHORT_RULE}""",
            ),
            (
                "写入 schema JSON",
                f"""创建或覆盖 `{_rel(json_output, profile)}`，按 `style_prompt.v1` 记录 prompt_markdown、constraints、avoid、source_paths、evaluation_plan 和 risk_notes；risk_notes 中注明本提示词已按 500-2500 中文内容字符可靠挂载范围、高质量 prompt 模块完整性和 2% AI 腔密度门禁完成自检。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, prompt, json_output)


def write_platform_style_prompt_eval_task(
    profile_dir: Path,
    *,
    reference: Path,
    task_input: Path,
    mode: str,
    style_prompt: Path | None = None,
    output_dir: Path | None = None,
) -> PlatformAgentTaskResult:
    profile = profile_dir.resolve()
    out_dir = output_dir if output_dir and output_dir.is_absolute() else profile / (str(output_dir) if output_dir else f"evaluation_results/{mode}")
    candidate = out_dir / "platform_agent_candidate.md"
    manifest = out_dir / "platform_agent_candidate.prompt.json"
    task_path = candidate.with_suffix(".agent_tasks.md")
    prompt_path = style_prompt if style_prompt and style_prompt.is_absolute() else profile / (str(style_prompt) if style_prompt else "style_prompt.md")
    sources = [prompt_path, reference, task_input, profile / "style-profile.md", profile / "style_metrics.json"]
    write_agent_tasks(
        task_path,
        title=f"platform style prompt evaluation {mode}",
        root=profile,
        source_paths=sources,
        notes=[
            "由平台 agent 根据 style_prompt.md 生成评测候选；不要调用本地 dry-run、http-chat 或外部 agent。",
            f"完成后写入候选文本：{_rel(candidate, profile)}",
            f"完成后写入 prompt manifest：{_rel(manifest, profile)}",
            "候选写入后，可再运行 deterministic style-eval 对候选和 reference 打分。",
        ],
        tasks=[
            (
                "读取评测材料",
                f"""读取 style_prompt.md、reference、input、profile/metrics 和标点规范。确认本次模式是回译、扩写或盲评，不要把参考原文直接复制到候选。候选必须遵守标准中文标点，除非评测目的明确要求保留原始异常标点。标点规则：{PUNCTUATION_STANDARD_SHORT_RULE}""",
            ),
            (
                "生成评测候选",
                f"""创建或覆盖 `{_rel(candidate, profile)}`，用 style_prompt 的约束处理 input，生成用于评估提示词有效性的候选文本。""",
            ),
            (
                "写入 manifest",
                f"""创建或覆盖 `{_rel(manifest, profile)}`，记录 mode、style_prompt、reference、input、candidate、source_paths 和平台 agent 生成说明。""",
            ),
        ],
    )
    return PlatformAgentTaskResult(task_path, candidate, manifest)


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _extend_unique(target: list[Path], paths: list[Path]) -> None:
    seen = {path.resolve() for path in target if path.exists()}
    for path in paths:
        if not path.exists():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        target.append(path)
        seen.add(resolved)


def _style_source_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    active = root / "style" / "active_style_skill.json"
    if active.exists():
        paths.append(active)
        try:
            payload = json.loads(active.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        for key in ("prompt", "style_skill", "mount_path"):
            value = str(payload.get(key) or "").strip()
            if not value:
                continue
            candidate = root / value
            if candidate.is_dir():
                for name in ("prompt.md", "style_skill.json", "style-profile.md", "style_metrics.json"):
                    child = candidate / name
                    if child.exists():
                        paths.append(child)
            elif candidate.exists():
                paths.append(candidate)
    fallback_candidates = [
        root / "style" / "style_prompt.md",
        root / "style" / "demo-author" / "style_prompt.md",
        root / "style" / "style-profile.md",
    ]
    paths.extend(path for path in fallback_candidates if path.exists())
    unique: list[Path] = []
    _extend_unique(unique, paths)
    return unique


def _normalize_asset_type(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    aliases = {
        "background": "background-story",
        "background_story": "background-story",
        "relationships": "relationship",
        "world-rules": "world",
        "chapter": "chapter-plan",
        "scenes": "scene-list",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in ASSET_TYPES:
        raise ValueError(f"unknown asset type: {value}. valid: {', '.join(ASSET_TYPES)}")
    return normalized


def _asset_candidate_id(asset_type: str, seed: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = _slug(seed)[:28] or "candidate"
    return f"{asset_type}-{slug}-platform-agent-{stamp}"


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", str(value).strip()).strip("-")
    return text or "asset"


def _resolve_optional(root: Path, path: Path | None) -> Path | None:
    if path is None:
        return None
    return path if path.is_absolute() else root / path


def _read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _safe_label(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]+", "-", value.strip()).strip("-") or "task"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
