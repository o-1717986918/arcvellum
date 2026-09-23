"""Literary review prompt, separate from the Pi scene transaction adapter."""

from __future__ import annotations

import json

from literary_engineering_studio_engine.public.literary import CreativeResult, SceneBrief, VerificationReport

from ..runtime.prompt_recipes import lean_scene_prompt_recipe
from .pi_scene_prompt_rules import QUANTITATIVE_DETAIL_RULE


def render_scene_review_prompt(
    brief: SceneBrief,
    result: CreativeResult,
    verification: VerificationReport,
    *,
    source_evidence: str = "",
    revision_attempts: int = 0,
    expression_context_block: str = "",
    performance_material_block: str = "",
) -> str:
    recipe = lean_scene_prompt_recipe("review")
    convergence = f"本场已完成 {revision_attempts} 轮返修；此时只有硬事实冲突、明确场景义务缺失或能指出具体读者损害的问题才可继续 revise，孤立句式、局部动作相似或可选润色一律判 pass 并写入 summary。" if revision_attempts >= 2 else "本场尚在前两轮审读，可对有明确证据的实质文学问题提出最小返修。"
    prompt = f"""# Scene Review

你是独立文学审查者。只判断人物可信度、场景变化、文风落实、节奏详略、前后衔接、读者问题和承诺推进；SceneBrief.canon_constraints 与 Relevant Sources 中的最新用户方向优先于候选正文。先逐项核对同一对象或事件的绝对测量值与差值，保留差值不能掩盖绝对值漂移；若候选正文与这些来源在人名、人物白名单、日期、年份、数量或时间差上形成硬冲突，必须判 revise 并指出冲突两端。把新专名登记进 new_asset_candidates 只表示可追踪，不表示在用户禁止新增人物时获得授权。若重复上一场“核对—追问—停顿—留悬念”的程序而实质损害人物声音、情绪因果或场景质感，也应判 revise，并指出重复结构及可保留的有效内容；共享调查题材、档案动作或孤立句式相似本身不是退回理由。
若来源内部详略不同，按“硬 canon 与最新用户方向 > 当前场 scene_goal/objective、scene_turn、outgoing_hook、revealed_info > 章级 dramatic_turn、chapter_ending_policy、payoff_or_delay”的顺序判断；下位概括不能推翻上位且更具体的本场承接。当前场明确要求的核对、登记、追问或离场动作不得仅因动作名称与上一场相似而退回，只有三个以上关键节拍以相同顺序重复且造成可说明的阅读损害，才属于实质同构。检查关键对白是否都像同一人说话；只有持续混同已损害人物可信度或关系张力时才要求修订，孤立平实回答不是退回理由。市、县、区等行政范围加通用机构类别的称谓不是独特专名；未获得独特名称且不承担持续身份时，无需登记新资产。
{convergence}
确定性检查已经由程序完成，不复查路径、哈希、回执或任务流程。
直接返回 JSON：{{"decision":"pass|revise|escalate","summary":"结论","revision_instructions":[],"evidence":[]}}。
需要改动时必须选择 revise 并给出具体片段证据；轻微建议仍判 pass。
程序的 warning 是提醒，不是自动退回理由。软字数偏差只作建议，不得单独退回；只有人物行为、场景义务、行动层次、选择代价或阅读效果出现可举证损害时才判 revise。不能仅凭 warning 标签本身要求改稿。一次审读最多列三个有原文证据的高影响问题，给出最小指令、修改跨度并保留有效段落；先前问题已消失时不得另开与硬约束、场景义务或明确阅读损害无关的新审美议题。
检查正文中新出现的专名或稳定身份是否已进入 new_asset_candidates；仅沿用 SceneBrief 的通用角色称谓、普通设备名或场所类别无需登记。真正遗漏会影响后续场景时判 revise。
也检查关键选择前后是否只剩动作和信息转述、心理完全缺席，环境是否被压成地点标签，情绪压力是否始终维持同一低音量；若造成可举证的阅读损害，可要求主创修订心理、叙述距离和场景渲染。不要以修辞数量、心理段落数量或字数密度作门禁。若启用一级角色素材，对白、动作本身确实不足时，应指出需要原角色续演，不能要求主创代写。
若有角色私念素材，留意正文是否只把它译成一个心理标签或一段静态履历，而未让当前视角随言语、空间和记忆发生可感的变化；只有这确实削弱了本场关系压力或读者体验时，给出具体引文与可保留的有效部分，再提出修订。不是要求机械增加心理篇幅、修辞或环境回环。
若下方有一级角色素材，逐段核对候选正文中每一处实际说出口的台词、提问和可见人物行为是否能回指同一角色的 entries。主创新增的角色言行是归属错误，即使它写得精彩、填满目标字数也必须判 revise：引用至少一个候选正文片段和素材缺口，要求删除越权言行并保留有效心理、环境、句群；确实缺少情节表演则请求原角色续演。不要把环境候选的观察句误判为角色动作，也不要要求对白逐字照抄。
若问题出在演员自己提出的旁逸剧情或不合人物的话，主创可以删选这一整条或保留已获素材中别处的有效言行，再修订叙事；审查指令不得叫主创替演员“改成另一句”或发明新的角色回应。删选后若核心情节不能成立，判 escalate 并说明需要主创重构处境、再请原角色表演；不要用主创代写来掩盖素材缺口。
一级角色给出候选不等于正文必须全收。若主创按轮次照录造成同一问题、回避或姿态重复，而人物理解没有变化，引用至少两处原文说明阅读损害，要求删选冗余条目并保护有效转折；不要把“对白多”本身当问题，也不要要求演员减少自主发挥。

## SceneBrief
{json.dumps(brief.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Expression And Voice Context
{expression_context_block or "以场景职责和人物事实为准。"}

## Deterministic Report
{json.dumps(verification.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Candidate
{result.prose}

## Original First-Level Character And Environment Materials
{performance_material_block or "未启用一级角色素材。"}

## Relevant Sources
{source_evidence or "无额外资料。"}

## Quantitative Detail Review\n逐处判断候选正文中的数词是否真的给出精确数量，再核对其当前语境。{QUANTITATIVE_DETAIL_RULE} 对明确无关的精确计数，引用具体片段及“删去精度不损失什么”的理由判 revise；对虚指反复、当场问答或改变人物理解的数值，不得仅因数词存在或没有后续兑现而退回。
"""
    if len(prompt) > recipe.hard_character_limit:
        raise ValueError("lean scene review prompt exceeds hard character limit")
    return prompt


__all__ = ["render_scene_review_prompt"]
