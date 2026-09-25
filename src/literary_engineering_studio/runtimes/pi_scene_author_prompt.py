"""Pure create/revision prompt rendering for a lean scene author."""

from __future__ import annotations

import json
from typing import Any

from literary_engineering_studio_engine.public.literary import CreativeResult, ReviewResult, SceneBrief, VerificationReport
from ..runtime.prompt_recipes import lean_scene_prompt_recipe
from .pi_scene_prompt_rules import QUANTITATIVE_DETAIL_RULE as _QUANTITATIVE_DETAIL_RULE

def render_scene_create_prompt(
    brief: SceneBrief,
    *,
    source_evidence: str = "",
    allowed_refs: Any = (),
    style_reference_block: str = "",
    expression_context_block: str = "",
    performance_material_block: str = "",
    allow_material_requests: bool = False,
) -> str:
    recipe = lean_scene_prompt_recipe("create")
    reference_contract = _reference_contract(brief, allowed_refs)
    material_section = (
        f"## Character And Environment Candidate Materials\n{performance_material_block}\n\n"
        if performance_material_block else ""
    )
    material_final_pass = (
        "演员素材是人物可能说出、做出的第一手选择；你决定哪些成为小说、如何改写、转述或补写。"
        "需要角色进一步自主回应时可请求续演。让对话对象、回应的前因及关系后果在正文中自然清楚。"
        if performance_material_block else ""
    )
    material_length_priority = (
        "角色素材较少时，可让视角经验、关系余波和空间感知充分展开；必要的言行由你补写或请原角色续演。"
        if performance_material_block else ""
    )
    request_guidance = (
        '需要一级素材时，可先返回请求 JSON，再在收到候选后亲自完成正文。'
        '每轮都可按新发展重新选择角色，并在 scene_change 写本轮进入的外部变化、cue 写角色当下可知的情况与补充信息；同一角色可连续续演。角色续演示例：'
        '{"material_requests":[{"kind":"actor","speaker":"SceneBrief.participants 中的精确名字",'
        '"beat_id":"已知节拍 ID","scene_change":"本轮新发生的事，可为空",'
        '"cue":"此人刚感受到的关系压力、误解或新信息；说法与动作由他自己决定"}]}。'
        '环境补写示例：{"material_requests":[{"kind":"environment","cue":"需要观察的空间变化"}]}。'
        '一次可请求多项。\n'
        if allow_material_requests or performance_material_block else ""
    )
    prompt = f"""# Scene Create

你是本场小说的主创。先看清本场在全书里要改变什么，再选择让读者从谁的感受进入：人物正在渴望、回避或误解什么，眼前的交锋会怎样改变他们和世界。写一场有情绪温度、叙事起伏和人物声音的完整小说，而不是把资料逐项翻译成正文。设定展开、宏观情节推进、世界状态变化、视角心理和场景语言都由你决定。

SceneBrief、已确认来源和最新用户方向规定事实边界；逐字沿用已确定的人名、日期、年份、数量和时间差。最后以 JSON 交付正文和正文实际造成的变化。

## SceneBrief
{json.dumps(brief.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Expression And Voice Context
{expression_context_block or "依照 SceneBrief 的人物与压力自行组织语言。"}

## Relevant Sources
{source_evidence or "无额外资料；使用 SceneBrief。"}\n\n## Style Reference Priority\n{style_reference_block or "若资料中有文风参考，借用与本场相关的表达机制；Canon、人物和用户方向优先。"}

{material_section}## Allowed Existing Refs
{json.dumps(reference_contract, ensure_ascii=False, separators=(",", ":"))}

## Length Contract
prose 的目标为 {brief.length.target_hanzi} 个中文正文字符，建议范围 {brief.length.soft_min}-{brief.length.soft_max}。按这场戏自身的呼吸安排详略：冲突可以骤起，情绪、记忆与环境也可以占据足够篇幅。首轮写出完整场景；一次响应不足时，创作阶段会要求在结尾之前补足有因果作用的段落。
{material_length_priority}
本场实现 SceneBrief 的 objective、participants、scene_function 与 incoming_handoff。章级义务提供方向；上一场已发生的后果进入此场。使用中文引号与标点。

## Literary Rendering
情绪主轴：EMOTION_ARC / EMOTION_CONTRADICTION / EMOTION_RESIDUE。此刻谁最想得到什么，谁在掩饰，哪句话令亲疏发生变化？让欲望、身体感受、误读与记忆进入句子，也让选择留下余温。人物可以热烈、失控、羞怯、幽默或自相矛盾；不同的人在不同关系里会换声调。对白可以绕路，叙述也可转述、贴近内心或长久停留在空间里。让引语、心理和环境跟着人物的注意力自然交织，句群长短随意义和压力变化。
SceneBrief.rhythm、reflection_ratio 和 description_ratio 是全场软建议；以眼前小说的阅读效果决定篇幅和次序。
## Output
{request_guidance}{{"prose":"完整正文","decision_summary":"不超过三句","scene_delta":{{"character_changes":[],"canon_candidates":[],"continuity_changes":[],"promise_updates":[],"reader_question_updates":[],"next_handoff":[],"new_asset_candidates":[]}},"decision_trace":[],"escalation_reasons":[],"material_requests":[]}}

既有对象变化项使用 {{"target_ref":"Allowed Existing Refs 中的精确字符串","summary":"变化","evidence":"正文证据","operation":"update","attributes":{{}}}}。
character_changes、canon_candidates、continuity_changes、promise_updates、reader_question_updates 的 target_ref 只能逐字选自 Allowed Existing Refs，禁止自造同义 ID。
若不能确定精确 ref，就不要填写该组；不要为了让变化看起来完整而创造 target_ref。
上一场文件只是来源，不能把未列入 Allowed Existing Refs 的 `scenes/上一场.yaml` 自造为 continuity_changes 目标；承接结果可写进 next_handoff。
正文出现的新人物、新地点、新组织或尚无精确引用的新事实，只能放入 new_asset_candidates，operation 使用 create；不得塞进既有对象变化组。
若正文给“幸存者”“旧搭档”等角色占位符新增专名、亲属关系或可持续身份，也必须在 new_asset_candidates 登记该身份。仅沿用 SceneBrief 中的通用角色称谓不算新增身份。
空组必须返回 []，禁止用空对象占位。next_handoff 只能是字符串数组，不得返回对象。
只提出正文确实发生的变化；无法确认、需要人工判断的内容放进 escalation_reasons。
若 SceneBrief.risk.level 为 high，decision_trace 必须用少量条目记录关键创作取舍。

## Final Prose Pass\n通读正文，听人物声音和段落节奏；参考样例挂载时，让适合本场的表达技法进入正文。核对破折号、数词和量化单位的实际语义。{material_final_pass}{_QUANTITATIVE_DETAIL_RULE}
"""
    if len(prompt) > recipe.hard_character_limit:
        raise ValueError("lean scene create prompt exceeds hard character limit")
    return prompt


def render_scene_revision_prompt(
    brief: SceneBrief,
    result: CreativeResult,
    verification: VerificationReport,
    review: ReviewResult | None,
    *,
    source_evidence: str = "",
    allowed_refs: Any = (),
    style_reference_block: str = "",
    expression_context_block: str = "",
    performance_material_block: str = "",
    allow_material_requests: bool = False,
) -> str:
    recipe = lean_scene_prompt_recipe("revise")
    instructions = list(review.revision_instructions) if review is not None else []
    reference_contract = _reference_contract(brief, allowed_refs)
    material_section = (
        f"## Original First-Level Character And Environment Materials\n{performance_material_block}\n\n"
        if performance_material_block else ""
    )
    request_guidance = (
        '修订需要一级素材时，可先返回请求 JSON。每轮可重新给角色补充新信息，'
        '用 scene_change 写新发生的外部变化、cue 写角色当下可知的处境。角色续演示例：'
        '{"material_requests":[{"kind":"actor","speaker":"SceneBrief.participants 中的精确名字",'
        '"beat_id":"已知节拍 ID","scene_change":"本轮新变化，可为空",'
        '"cue":"新的具体处境与信息"}]}。环境补写示例：'
        '{"material_requests":[{"kind":"environment","cue":"需要观察的空间变化"}]}。'
        '补充候选会交回给你继续修订。\n'
        if allow_material_requests or performance_material_block else ""
    )
    prompt = f"""# Scene Revision

你是本场景原主创。读完现有正文和具体审查证据，亲自写出下一版完整小说；让修订首先服务人物、情绪和整场叙事的生长。可以保留有力的片段，也可以重排场景、拓展心理与环境、改写对白的走向。
情绪修订轴：EMOTION_ARC / EMOTION_CONTRADICTION / EMOTION_RESIDUE。让读者经历人物在关键话语前后的感受变化；情绪可以停留、升温或反转。一级角色 entries 是可取舍的第一手素材，主创可改写和补写言行，也可请角色续演。人物问答应有可辨认的对象与前因。将本场在全书中的情节位移、设定展开和世界变化写进正文，并让 SceneDelta 与之相符。
SceneBrief、已确认来源和最新用户方向规定人物、事实、时间与数值。修订完成后更新与正文一致的 SceneDelta。直接返回与 Scene Create 相同的 JSON 对象。

## SceneBrief
{json.dumps(brief.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Expression And Voice Context
{expression_context_block or "保留候选中有效的人物声音与表达选择。"}

## Candidate
{result.prose}

## Existing SceneDelta
{json.dumps(result.scene_delta.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Deterministic Issues
{json.dumps(verification.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Review Instructions
{json.dumps(instructions, ensure_ascii=False, separators=(",", ":"))}

## Relevant Sources
{source_evidence or "无额外资料。"}\n\n## Style Reference Priority\n{style_reference_block or "保留候选中有效的语言运动；若资料中有文风参考，借用其表达机制。"}

{material_section}

## Allowed Existing Refs
{json.dumps(reference_contract, ensure_ascii=False, separators=(",", ":"))}

## Length Contract
prose 的目标为 {brief.length.target_hanzi} 个中文正文字符，建议范围 {brief.length.soft_min}-{brief.length.soft_max}。若审查要求扩写，补充有效行动、信息、关系压力或选择代价。
## Output
{request_guidance}{{"prose":"修订后的完整正文","decision_summary":"不超过三句","scene_delta":{{"character_changes":[],"canon_candidates":[],"continuity_changes":[],"promise_updates":[],"reader_question_updates":[],"next_handoff":[],"new_asset_candidates":[]}},"decision_trace":[],"escalation_reasons":[],"material_requests":[]}}

修订 SceneDelta 时删除无效条目，不得保留空对象或把字段改成空字符串来占位。
既有变化组的 target_ref 只能逐字选自 Allowed Existing Refs；找不到精确既有引用的新事实改放 new_asset_candidates，operation 使用 create。
不要为本场承接另造 `scenes/上一场.yaml` 之类目标；若该路径不在 Allowed Existing Refs，删除那条 continuity_changes，把有效后果放在 next_handoff。
角色占位符在正文中获得新专名、亲属关系或可持续身份时，须补入 new_asset_candidates；通用角色称谓和普通设备名不登记。
空组返回 []。next_handoff 只能是字符串数组。
若 SceneBrief.risk.level 为 high，decision_trace 必须保留关键创作取舍，不得清空。
## Final Prose Pass\n若已挂载参考样例，保留其可用的表达技法；逐项复核数词语义。{_QUANTITATIVE_DETAIL_RULE}
"""
    if len(prompt) > recipe.hard_character_limit:
        raise ValueError("lean scene revision prompt exceeds hard character limit")
    return prompt


def _reference_contract(brief: SceneBrief, allowed_refs: Any) -> list[str]:
    supplied = {str(item).strip() for item in allowed_refs if str(item).strip()}
    if not supplied:
        supplied.update(brief.source_refs)
        supplied.update(brief.canon_constraints)
        supplied.update(brief.chapter_obligations)
        supplied.update(brief.participants)
    return sorted(item for item in supplied if item)


__all__ = ["render_scene_create_prompt", "render_scene_revision_prompt"]
