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
        "一级演员提供角色言行与临场选择的优先素材；你可以取舍、改写，也可以为因果衔接和文学效果亲自补写必要的台词与动作。需要听见该角色进一步自主回应时，可通过 material_requests 请他续演。删选或补写一人的话时，连同下一人的回答检查所回应的那句话是否仍在正文中。让误称、误会或追问有读者能察觉的起因、具体的对话对象与随之变化的关系；前因若由另一人挑起，先让那人的言行在正文里发生。"
        "你负责把推演提升为有因果和审美判断的小说：展开既有设定，决定本场在全书中的剧情位移，提出世界状态变化并如实填写 SceneDelta。"
        "心理、情绪和环境由你写成正文，在关系变化处充分停留。"
        "关键物证、设备结论与精确数值仍以 SceneBrief 和来源为准。"
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

你是本章唯一的主创。依据 SceneBrief.canon_constraints 与 Relevant Sources 中的最新用户方向，写当前场景的完整小说正文，逐字沿用已确定的人名、日期、年份、数量和时间差，再提取正文实际造成的语义变化。直接返回一个 JSON 对象。

## SceneBrief
{json.dumps(brief.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Expression And Voice Context
{expression_context_block or "依照 SceneBrief 的人物与压力自行组织语言。"}

## Relevant Sources
{source_evidence or "无额外资料；使用 SceneBrief。"}\n\n## Style Reference Priority\n{style_reference_block or "若资料中有文风参考，借用与本场相关的表达机制；Canon、人物和用户方向优先。"}

{material_section}## Allowed Existing Refs
{json.dumps(reference_contract, ensure_ascii=False, separators=(",", ":"))}

## Length Contract
prose 的目标为 {brief.length.target_hanzi} 个中文正文字符，建议范围 {brief.length.soft_min}-{brief.length.soft_max}。把现有事件分成开场压力、行动阻力、关系反应、选择代价和余波，给各段分配足够篇幅；首轮直接写足完整场景。一次响应不足时，创作阶段会要求在结尾之前补足有因果作用的段落。
{material_length_priority}
本场实现 SceneBrief 的 objective、participants、scene_function 与 incoming_handoff。章级义务提供方向；Relevant Sources 含上一场正文时，承接其已发生后果。
句群长度随意义与压力变化。白描只是可用底色之一，语言可随关系、认识和压力变调。写对白前根据人物背景、欲望、身份和关系压力辨认不同声音；speech_style 未填写时从已知事实推导。保留角色 Agent 的不齐整选择，让不同人物有各自语势。当前视角可充分经历情绪。使用中文引号与标点。

## Literary Rendering
情绪主轴：EMOTION_ARC / EMOTION_CONTRADICTION / EMOTION_RESIDUE。辨认此刻谁的欲望最烫、谁把感受藏在话里、哪一次回应改变了亲疏；让情绪在对白语势、身体感受、注意力和空间中展开，并让选择后的余温进入场景结尾。情绪强弱由人物与事件决定，允许热烈、失控、温柔、羞怯或复杂矛盾的表达。
主创决定情绪表达的力度与位置。开篇抓住正在改变关系的一瞬，让环境从人物知觉里逐渐展开；背景与规则随着选择显形。让当前视角的误读、欲望与记忆在中段的空间里变化，允许有意义地停留和渲染。对白可绕路、说错或沉默，服务眼前的关系。把推演当作人物间正在发生的关系与事件，抓住谁向谁说话、为何此时开口、听者怎样改变。灵活使用直接引语、转述、自由间接引语、连续的心理与空间描写；说话人已清楚时，让声音自然接续。避免反复套用“引号台词—某某说或做—下一句台词”的排列。SceneBrief.rhythm、reflection_ratio 和 description_ratio 是全场软建议；最新用户方向和阅读效果决定心理、环境与语言起伏的篇幅。
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

## Final Prose Pass\n挂载参考样例时，确认至少两项可观察技法体现在 prose 中。通读整场破折号，按语义改动重复承担同一种转折的句法；最后重审数词与量化单位。{material_final_pass}{_QUANTITATIVE_DETAIL_RULE}
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

你是本场景原主创，亲自写出下一版完整正文。依据 Deterministic Issues 与 Review Instructions 的具体证据修订；修订一处后通读全场。可保留有效情节与语言，也可重组句法、人物声音、心理和环境。
情绪修订轴：EMOTION_ARC / EMOTION_CONTRADICTION / EMOTION_RESIDUE。核对人物在关键话语前后的感受如何变化，心理、对白、环境和选择后果能否让读者经历这次变化；必要时让情绪充分停留、升温或反转。
一级角色 entries 是可取舍的发言与行为素材。主创可改写已有台词，也可在必要时补写言行或请角色续演。删选一人的话时，连同下一人的回答检查其具体所指，让问答因果在正文中连续。误称、误会和追问应让读者看见其起因、对话对象和关系后果；若前因缺失，由你重排已有言行或补写可信的衔接。当前视角的私念和情绪由你展开；中段允许空间与视角变化。对白在改变关系时重提事实。让发言、转述、感知和情绪在段落中重新编排，使人物关系的变化决定引语出现的位置。避免反复套用“引号台词—某某说或做—下一句台词”的排列。
检查本场在全书中的情节位移、设定和世界状态的展开，并让持久变化准确进入 SceneDelta。
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
