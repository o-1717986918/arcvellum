"""Pi Worker adapter for lean scene create and conditional review calls."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable

from literary_engineering_studio_engine.public.literary import (
    CreativeResult,
    ReviewResult,
    SceneBrief,
    VerificationReport,
    select_active_style_references,
    recent_formal_reference_ids,
    active_style_mount_snapshot_payload,
    render_style_reference_selection,
    project_brief_expression_context,
)
from ..runtime.prompt_recipes import lean_scene_prompt_recipe
from ..runtime.role_conversation import RoleConversationGateway
from ..infrastructure.project_scene_transactions import known_scene_refs
from .scene_length_completion import complete_first_draft_length
from .pi_scene_payload import _answer_payload, creative_result_from_payload, review_result_from_payload
from .pi_scene_style_history import projection_digest as _projection_digest, recent_lean_reference_ids, scene_reference_context
from .scene_performance import scene_creative_cache_digest, scene_performance_materials
from .scene_performance_ownership import repair_actor_dialogue
from .scene_source_evidence import scene_source_evidence
from .pi_scene_prompt_rules import QUANTITATIVE_DETAIL_RULE as _QUANTITATIVE_DETAIL_RULE
from .pi_scene_review_prompt import render_scene_review_prompt

@dataclass(frozen=True)
class PiSceneRuntimeMetrics:
    provider_calls: int
    cache_hits: int

class PiSceneTransactionRuntime:
    """Use the embedded Pi conversation transport behind K2 runtime ports."""

    def __init__(
        self,
        config: dict[str, Any],
        *,
        project_root: Path,
        data_root: Path,
        gateway: RoleConversationGateway | None = None,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
        timeout: int = 900,
    ):
        self._config = config
        self._project_root = project_root.resolve()
        self._data_root = data_root.resolve()
        self._gateway = gateway or RoleConversationGateway(
            config,
            data_root=self._data_root / "pi-conversations",
        )
        self._event_sink = event_sink
        self._timeout = max(30, min(900, int(timeout)))
        self._provider_calls = 0
        self._cache_hits = 0

    @property
    def metrics(self) -> PiSceneRuntimeMetrics:
        return PiSceneRuntimeMetrics(self._provider_calls, self._cache_hits)

    def create_scene(self, transaction_id: str, brief: SceneBrief) -> CreativeResult:
        selection = self._style_projection(brief, transaction_id)
        expression = self._expression_projection(brief)
        projection_digest = _projection_digest(selection, expression)
        initial_sources = self._source_evidence(brief, purpose="create")
        style_reference = render_style_reference_selection(selection)
        creative_digest = scene_creative_cache_digest(projection_digest, brief.to_dict(), initial_sources, self._config)
        cache = self._cache_path(transaction_id, f"creative_result_{creative_digest}.json")
        materials_cache = self._cache_path(transaction_id, f"performance_materials_{creative_digest}.json")
        cached = _read_json(cache)
        if cached is not None:
            self._cache_hits += 1
            return creative_result_from_payload(cached)
        if self._event_sink is not None:
            self._event_sink("style.projection.selected", {
                "scene_transaction_id": transaction_id,
                "scene_id": brief.scene_id,
                "style_version_id": selection.get("style_mount_snapshot", {}).get("version_id", ""),
                "selection_status": selection.get("status", ""),
                "selector_version": selection.get("selector_version", ""),
                "selection_digest": selection.get("digest", ""),
                "reference_ids": [item["unit_id"] for item in selection.get("references", [])],
                "technique_axes": [axis for item in selection.get("references", []) for axis in item["technique_axes"]],
                "expression_plan_digest": hashlib.sha256(json.dumps(expression.get("expression_plan"), ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                "voice_digest": hashlib.sha256(json.dumps(expression.get("dialogue_intents"), ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                "message": "本场文风参考与表达策略已确定。",
            })
        materials = scene_performance_materials(
            brief=brief.to_dict(),
            expression=expression,
            sources=initial_sources,
            style_reference=style_reference,
            cache_root=cache.parent,
            config=self._config,
            invoke=lambda prompt, role: self._run(prompt, role=role, transaction_id=transaction_id),
            emit=(lambda event, data: self._event_sink(event, {**data, "scene_transaction_id": transaction_id}))
            if self._event_sink is not None else None,
        )
        _atomic_json(materials_cache, {"materials": materials})
        prompt = render_scene_create_prompt(
            brief,
            source_evidence=self._source_evidence(brief, purpose="create", reserve_chars=len(materials)),
            allowed_refs=known_scene_refs(brief),
            style_reference_block=style_reference,
            expression_context_block=json.dumps(expression, ensure_ascii=False, separators=(",", ":")),
            performance_material_block=materials,
        )
        answer = self._run(prompt, role="worker", transaction_id=transaction_id)
        result = creative_result_from_payload(_answer_payload(answer))
        result = complete_first_draft_length(
            brief, result,
            lambda prompt: _answer_payload(self._run(prompt, role="worker", transaction_id=transaction_id)),
            actor_owned=bool(materials),
            performance_material_block=materials,
        )
        result = self._repair_actor_dialogue(
            transaction_id, brief, result, materials, style_reference,
            json.dumps(expression, ensure_ascii=False, separators=(",", ":")),
        )
        _atomic_json(cache, result.to_dict())
        return result

    def review_scene(
        self,
        transaction_id: str,
        brief: SceneBrief,
        result: CreativeResult,
        verification: VerificationReport,
    ) -> ReviewResult:
        selection = self._style_projection(brief, transaction_id)
        expression = self._expression_projection(brief)
        projection_digest = _projection_digest(selection, expression)
        candidate_digest = hashlib.sha256(result.prose.encode("utf-8")).hexdigest()[:16]
        initial_sources = self._source_evidence(brief, purpose="create")
        creative_digest = scene_creative_cache_digest(projection_digest, brief.to_dict(), initial_sources, self._config)
        material_record = _read_json(self._cache_path(transaction_id, f"performance_materials_{creative_digest}.json"))
        if _scene_performance_enabled(self._config) and material_record is None:
            raise RuntimeError("scene review requires the original first-level performance materials")
        materials = str(material_record.get("materials") or "") if material_record else ""
        materials_digest = hashlib.sha256(materials.encode("utf-8")).hexdigest()[:10]
        cache = self._cache_path(transaction_id, f"review_result_{candidate_digest}_{projection_digest}_{materials_digest}.json")
        cached = _read_json(cache)
        if cached is not None:
            self._cache_hits += 1
            return review_result_from_payload(cached)
        prompt = render_scene_review_prompt(
            brief,
            result,
            verification,
            source_evidence=self._source_evidence(brief, purpose="review", reserve_chars=len(materials)),
            revision_attempts=len(tuple(cache.parent.glob(f"revision_result_*_{projection_digest}.json"))),
            expression_context_block=json.dumps(expression, ensure_ascii=False, separators=(",", ":")),
            performance_material_block=materials,
        )
        answer = self._run(prompt, role="reviewer", transaction_id=transaction_id)
        review = review_result_from_payload(_answer_payload(answer))
        _atomic_json(
            cache,
            {
                "decision": review.decision.value,
                "summary": review.summary,
                "revision_instructions": list(review.revision_instructions),
                "evidence": list(review.evidence),
            },
        )
        return review

    def revise_scene(
        self,
        transaction_id: str,
        brief: SceneBrief,
        result: CreativeResult,
        verification: VerificationReport,
        review: ReviewResult | None,
        *,
        attempt: int,
    ) -> CreativeResult:
        selection = self._style_projection(brief, transaction_id)
        expression = self._expression_projection(brief)
        projection_digest = _projection_digest(selection, expression)
        initial_sources = self._source_evidence(brief, purpose="create")
        creative_digest = scene_creative_cache_digest(projection_digest, brief.to_dict(), initial_sources, self._config)
        materials_cache = self._cache_path(transaction_id, f"performance_materials_{creative_digest}.json")
        material_record = _read_json(materials_cache)
        if _scene_performance_enabled(self._config) and material_record is None:
            raise RuntimeError("scene revision requires the original first-level performance materials")
        materials = str(material_record.get("materials") or "") if material_record else ""
        cache = self._cache_path(transaction_id, f"revision_result_{attempt}_{projection_digest}.json")
        cached = _read_json(cache)
        if cached is not None:
            self._cache_hits += 1
            return creative_result_from_payload(cached)
        prompt = render_scene_revision_prompt(
            brief,
            result,
            verification,
            review,
            source_evidence=self._source_evidence(brief, purpose="revise", reserve_chars=len(materials)),
            allowed_refs=known_scene_refs(brief),
            style_reference_block=render_style_reference_selection(selection),
            expression_context_block=json.dumps(expression, ensure_ascii=False, separators=(",", ":")),
            performance_material_block=materials,
        )
        answer = self._run(prompt, role="worker", transaction_id=transaction_id)
        revised = creative_result_from_payload(_answer_payload(answer))
        revised = self._repair_actor_dialogue(
            transaction_id, brief, revised, materials, render_style_reference_selection(selection),
            json.dumps(expression, ensure_ascii=False, separators=(",", ":")),
        )
        _atomic_json(cache, revised.to_dict())
        return revised

    def _repair_actor_dialogue(
        self, transaction_id: str, brief: SceneBrief, result: CreativeResult, materials: str,
        style_reference: str, expression_context: str,
    ) -> CreativeResult:
        def revise(candidate: CreativeResult, missing: list[str]) -> CreativeResult:
            review = review_result_from_payload({
                "decision": "revise", "summary": "有台词不来自一级角色。",
                "revision_instructions": [
                    "删除以下不在任何角色 spoken 中的引号内台词，不得改写成另一句主创代说的话；"
                    "保留已获授权的角色言行及有效心理和环境。若因此缺少场景表演，在 escalation_reasons 请求原角色续演："
                    + json.dumps(missing[:8], ensure_ascii=False),
                ], "evidence": missing[:8],
            })
            prompt = render_scene_revision_prompt(
                brief, candidate, VerificationReport(brief.scene_id, len(candidate.prose)), review,
                source_evidence=self._source_evidence(brief, purpose="revise", reserve_chars=len(materials)),
                allowed_refs=known_scene_refs(brief), style_reference_block=style_reference,
                expression_context_block=expression_context, performance_material_block=materials,
            )
            return creative_result_from_payload(_answer_payload(self._run(prompt, role="worker", transaction_id=transaction_id)))
        return repair_actor_dialogue(result, materials, revise)

    def _run(self, prompt: str, *, role: str, transaction_id: str) -> str:
        self._provider_calls += 1

        def observe(event: str, data: dict[str, Any]) -> None:
            if self._event_sink is not None:
                self._event_sink(event, {**data, "scene_transaction_id": transaction_id})

        response = self._gateway.run(
            self._project_root,
            prompt,
            role=role,
            timeout=self._timeout,
            event_sink=observe,
        )
        return response.answer

    def _cache_path(self, transaction_id: str, name: str) -> Path:
        safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", transaction_id).strip("._")
        if not safe_id:
            raise ValueError("transaction_id cannot be normalized for runtime storage")
        return self._data_root / "scene-transactions" / safe_id / name

    def _style_projection(self, brief: SceneBrief, transaction_id: str = "") -> dict[str, Any]:
        scene_text = scene_reference_context(self._project_root, brief.scene_id, brief.to_dict())
        brief_digest = hashlib.sha256(scene_text.encode("utf-8")).hexdigest()
        mount = active_style_mount_snapshot_payload(self._project_root)
        if transaction_id:
            cache = self._cache_path(transaction_id, "style_selection.json")
            saved = _read_json(cache)
            if saved and saved.get("brief_digest") == brief_digest and saved.get("style_mount_snapshot") == mount:
                return saved["selection"]
        recent = (*recent_formal_reference_ids(self._project_root, exclude_scene_id=brief.scene_id),
                  *recent_lean_reference_ids(self._data_root, brief.scene_id, mount))
        selection = select_active_style_references(self._project_root, scene_text, recent_unit_ids=recent)
        if transaction_id:
            _atomic_json(cache, {"scene_id": brief.scene_id, "brief_digest": brief_digest,
                                 "style_mount_snapshot": mount, "selection": selection})
        return selection

    def _expression_projection(self, brief: SceneBrief) -> dict[str, Any]:
        return project_brief_expression_context(self._project_root, brief.to_dict())

    def _source_evidence(self, brief: SceneBrief, *, purpose: str, reserve_chars: int = 0) -> str:
        indexed_style = self._style_projection(brief).get("status") in {"selected", "no-scene-match"}
        return scene_source_evidence(
            self._project_root, brief, purpose=purpose,
            indexed_style=indexed_style, reserve_chars=reserve_chars,
        )


def render_scene_create_prompt(
    brief: SceneBrief,
    *,
    source_evidence: str = "",
    allowed_refs: Any = (),
    style_reference_block: str = "",
    expression_context_block: str = "",
    performance_material_block: str = "",
) -> str:
    recipe = lean_scene_prompt_recipe("create")
    reference_contract = _reference_contract(brief, allowed_refs)
    material_section = (
        f"## Character And Environment Candidate Materials\n{performance_material_block}\n\n"
        if performance_material_block else ""
    )
    material_final_pass = (
        "启用角色表演素材时，本段规则优先于上文通用‘写对白’和字数建议：所有实际对白和人物可见行为须先由该人物的一级 Agent 在 entries 中给出；不要自行补对白、提问、回答、转身、触碰、离场等任何新动作，也不要把演员句子润平为同一种声音。"
        "心理与情绪的文学叙述不等于新增人物言行：依据整个推演及当前视角，可让未出口的欲望、犹疑和误读在感知、句法、联想里展开；不要把私念照抄成台词或全知解释。"
        "把每条 entry 当作人物外显言行的全集，而不是待续写的开头；正文可以只使用其中一部分并重新安排观察距离，但任何新增外显内容都要先请求原角色续演。也不必把每条 entry 都录进正文：几轮若只换说法重复同一追问或防御，保留真正改变关系的一次，给未说出口的经验与空间余韵留位置；删选不等于把场景压成摘要。"
        "若环境候选合乎视角与已确认事实，可保留它的观察次序和句群呼吸，也可重组、延展，不必逐句移植。"
        "逐项核对候选里的物件、技术结论和精确数值，来源未确认且无必要的不用。候选的后台解释绝不进入正文。"
        if performance_material_block else ""
    )
    material_length_priority = (
        "启用一级角色素材时，字数服从素材归属：素材不足以自然支撑目标长度，就保留真实的短场景，"
        "在 escalation_reasons 说明需要原角色续演；绝不为了凑字数让主创代人物说话或做事。"
        if performance_material_block else ""
    )
    material_literary_guidance = (
        "不要把 private_impulse 压成心理标签或一段履历。择取真正承压的时刻，让当前视角的念头随对方原话变化："
        "注意、误读、记忆、自辩与迟来的理解可以在句法和身体感知中展开，不必齐全，也不设心理段落配额。"
        "环境候选可随人物理解变化而回返，不只供开头报景；不作象征解说，不新增演员言行或未确认的证据。"
        if performance_material_block else ""
    )
    prompt = f"""# Scene Create

你是本章唯一的主创。SceneBrief.canon_constraints 与 Relevant Sources 中的最新用户方向是本场硬约束；依据它们写当前场景的完整小说正文，并逐字沿用其中已确定的人名、日期、年份、数量和时间差。保留差值不代表可以改动构成差值的绝对值，同一对象或事件已有精确测量时不得另造替代数值；人物白名单或禁止新专名等限制同样不得用登记 new_asset_candidates 绕过。再提取正文实际造成的语义变化。
直接返回一个 JSON 对象，不要 Markdown 代码围栏、解释、任务回执、路径或哈希。

## SceneBrief
{json.dumps(brief.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Expression And Voice Context
{expression_context_block or "依照 SceneBrief 的人物与压力自行组织语言；不编造未给定身份。"}

## Relevant Sources
{source_evidence or "无额外资料；严格使用 SceneBrief。"}\n\n## Style Reference Priority\n{style_reference_block or "若资料中有文风参考，借用与本场相关的表达机制，不复制原句、专名或连续措辞；Canon、人物和用户方向优先。"}

{material_section}## Allowed Existing Refs
{json.dumps(reference_contract, ensure_ascii=False, separators=(",", ":"))}

## Length Contract
prose 的目标为 {brief.length.target_hanzi} 个中文正文字符，建议范围 {brief.length.soft_min}-{brief.length.soft_max}。先在心中把现有事件分成开场压力、行动阻力、关系反应、选择代价和余波，给各段分配足够篇幅；首轮直接写足完整场景，不得用梗概、节拍清单或压缩叙述代替正文。如果一次响应不足，创作阶段会要求在结尾之前补足有因果作用的段落，不要提前把情节收束成短稿。
{material_length_priority}
本场只实现 SceneBrief 的 objective、participants、scene_function 与 incoming_handoff。章级义务提供方向，不授权提前演出后续场景；未列入 participants 的主要人物不得登场、发言或完成关键动作。若 Relevant Sources 含上一场正文，只承接其已发生后果，不得重演首次见面、同一调取/发现/交付、同一问答或同一决定。
句群不设恒定默认长度：短句只落在真正的发现、选择或后果上；较长句承载连续动作、观察层次、摇摆或复杂因果；连续短句若只是在逐项报动作，就重组为有呼吸和层级的句群。白描只是可用底色之一，承压段落可选扎根人物经验的自由间接引语、反讽、借代、通感、复沓、意象回返或长句推进，让修辞参与认识和关系变化。细节也可积蓄气氛、显露趣味或延长审美时间，不要求每段都即时推进事件。不要让连续场景都套用“核对—追问—停顿—留悬念”的程序。写对白前根据人物背景、欲望、身份和关系压力，为主要说话者区分词域、句形、主动发问或回避方式、礼貌边界与幽默方式；speech_style 未填写时从已知事实推导，不编造方言、口头禅或新身世。让换掉说话者姓名后的关键台词仍可辨认，不把所有人压成同一种平直短句。情绪通过避让、选择代价、自由间接感知和说话方式显影，不用抽象总结代替。段尾和场尾执行“证据之后停笔”：动作、意象、对白、沉默或物证已经传意时，删去随后翻译潜台词、概括人物感受、宣布主题或解释其意义的句子。使用中文引号与标点，不输出写作流程痕迹。

## Literary Rendering
主创依据整个场景推演自行决定情绪表达的力度与位置：关系承压处可以让人物把话说完、说错、绕开再回来，也可以让当前视角进入未出口的经验，使身体感知、欲望、自我辩解和联想出现层次。不要把心理缩成“他犹豫了”，把对话压成情节摘要，或把环境压成地点标签。证据成立后不追加解释性尾句，不等于证据形成之前要惜字如金；允许有意义地停留和渲染，不靠重复说明灌篇幅。若启用角色素材，新的外显台词和动作仍须由一级角色提供。
{material_literary_guidance}
SceneBrief.rhythm 与来源中的 reflection_ratio、description_ratio 是全场节奏的软建议，不是逐段上限；即使既有模板写着 low，也不能因此删去关键心理、环境停留或人物语言的起伏。旧挂载文风若要求“只有行为无法承载才简短直述”心理，也不是本轮心理叙述的硬上限；最新用户方向和当前场景实际阅读效果决定取舍。

## Output
{{"prose":"完整正文","decision_summary":"不超过三句","scene_delta":{{"character_changes":[],"canon_candidates":[],"continuity_changes":[],"promise_updates":[],"reader_question_updates":[],"next_handoff":[],"new_asset_candidates":[]}},"decision_trace":[],"escalation_reasons":[]}}

既有对象变化项使用 {{"target_ref":"Allowed Existing Refs 中的精确字符串","summary":"变化","evidence":"正文证据","operation":"update","attributes":{{}}}}。
character_changes、canon_candidates、continuity_changes、promise_updates、reader_question_updates 的 target_ref 只能逐字选自 Allowed Existing Refs，禁止自造同义 ID。
若不能确定精确 ref，就不要填写该组；不要为了让变化看起来完整而创造 target_ref。
上一场文件只是来源，不能把未列入 Allowed Existing Refs 的 `scenes/上一场.yaml` 自造为 continuity_changes 目标；承接结果可写进 next_handoff。
正文出现的新人物、新地点、新组织或尚无精确引用的新事实，只能放入 new_asset_candidates，operation 使用 create；不得塞进既有对象变化组。
若正文给“幸存者”“旧搭档”等角色占位符新增专名、亲属关系或可持续身份，也必须在 new_asset_candidates 登记该身份。仅沿用 SceneBrief 中的通用角色称谓不算新增身份。
空组必须返回 []，禁止用空对象占位。next_handoff 只能是字符串数组，不得返回对象。
只提出正文确实发生的变化；无法确认的内容放进 escalation_reasons。
若 SceneBrief.risk.level 为 high，decision_trace 必须用少量条目记录关键创作取舍。

## Final Prose Pass\n若已挂载参考样例，返回 JSON 前确认所选样例至少两项可观察技法已在 prose 中实际体现，并删去动作、意象、对白或物证后面重复解释其含义的尾句；随后对阿拉伯数字、中文数词、序数和量化单位完成最后一遍语义重写。{material_final_pass}{_QUANTITATIVE_DETAIL_RULE}
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
) -> str:
    recipe = lean_scene_prompt_recipe("revise")
    instructions = list(review.revision_instructions) if review is not None else []
    reference_contract = _reference_contract(brief, allowed_refs)
    material_section = (
        f"## Original First-Level Character And Environment Materials\n{performance_material_block}\n\n"
        if performance_material_block else ""
    )
    prompt = f"""# Scene Revision

你是本场景原主创。只修复列出的硬失败或文学问题，保留有效情节、人物声音和已有细节。SceneBrief.canon_constraints 与 Relevant Sources 中的最新用户方向仍是硬约束；每轮返修都必须重新核对既定人名、人物白名单、日期、年份、绝对数值、差值与时间间隔，不得在修复一个问题时重新引入已消失的冲突，也不得用 new_asset_candidates 绕过禁止新增专名的方向。
不得用另一种模板化转折替换问题表达。修改后的正文仍须满足同一 SceneBrief，并重新提取实际 SceneDelta。
修订长句、逗号或标点问题时应重组句内层级，不能把原句机械拆成一串结构相同的短句；句群长度随动作、观察与压力变化，并保护原有的长短句落差。修订对白时保留人物各自的词域、句形、礼貌边界、幽默方式、回避和争取策略；不要把所有台词统一磨成平直短句，也不要凭空加口头禅。若原文已由动作、意象、对白、沉默或物证传意，删除随后重复解释其含义的段尾、场尾句，不用另一条金句替换。
若审查指出文风或情节损害，主创可以重新选择叙述距离、心理层次、环境停留、句群节奏与已有场景材料的交错顺序，使情绪有蓄积和转折；不要把修订理解为只改错字或增加几句解释。惜字造成的空白与重复灌水都不是目标。启用一级角色素材时，外显台词和动作仍只来自原角色 entries；主创可改写当前视角中的心理体验，但不能代角色补说、补做。若情节修复确实需要新增角色言行，放入 escalation_reasons 明确请求原角色续演，不用正文越权填补。
如果审查意见叫你“把某句角色台词改成另一句”，这条指令越过了人物归属：只可从演员已给出的条目中删选或调整叙述位置，不能重写该角色的具体发言。删选导致既定场景结果失去支持时，不提交伪完成稿，说明需要重新组织场景压力并请原角色续演。
角色推演不是逐字实录：若连续几轮只是同一追问、防御或不拿信的姿态换词重演，主创可删去不产生位移的条目，保留改变人物理解与关系的言行；把腾出的空间交给视角中的复杂经验，而不是再补一轮同义对白。
若问题在心理与环境过薄，回到角色 private_impulse 和已发生的对话，把沉默前后的误读、抵抗、自我辩解或记忆的迟到写成正在变化的视角经验；同一环境细节可在不同压力下再被感到。保留人物未说出口与已说出口之间的落差，不给读者补一段情绪结论，也不拿环境意象替人物决定。
既有项目的 reflection_ratio、description_ratio 即使写 low，也只是全场软建议，不是删减心理和环境的硬上限；旧挂载文风的“只有行为无法承载才简短直述”同样不得压掉需要展开的视角经验。修订须服从最新用户方向与具体阅读损害。
直接返回与 Scene Create 完全相同的 JSON 对象，不要 Markdown、工作流说明、路径或哈希。

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
{source_evidence or "无额外资料。"}\n\n## Style Reference Priority\n{style_reference_block or "保留候选中有效的语言运动；若资料中有文风参考，只借用表达机制，不搬运原句。"}

{material_section}

## Allowed Existing Refs
{json.dumps(reference_contract, ensure_ascii=False, separators=(",", ":"))}

## Length Contract
prose 的目标为 {brief.length.target_hanzi} 个中文正文字符，建议范围 {brief.length.soft_min}-{brief.length.soft_max}。若审查要求扩写，必须补充有效行动、信息、关系压力或选择代价，不得用重复解释凑字数。

## Output
{{"prose":"修订后的完整正文","decision_summary":"不超过三句","scene_delta":{{"character_changes":[],"canon_candidates":[],"continuity_changes":[],"promise_updates":[],"reader_question_updates":[],"next_handoff":[],"new_asset_candidates":[]}},"decision_trace":[],"escalation_reasons":[]}}

修订 SceneDelta 时删除无效条目，不得保留空对象或把字段改成空字符串来占位。
既有变化组的 target_ref 只能逐字选自 Allowed Existing Refs；找不到精确既有引用的新事实改放 new_asset_candidates，operation 使用 create。
不要为本场承接另造 `scenes/上一场.yaml` 之类目标；若该路径不在 Allowed Existing Refs，删除那条 continuity_changes，把有效后果放在 next_handoff。
角色占位符在正文中获得新专名、亲属关系或可持续身份时，须补入 new_asset_candidates；通用角色称谓和普通设备名不登记。
空组返回 []。next_handoff 只能是字符串数组。
若 SceneBrief.risk.level 为 high，decision_trace 必须保留关键创作取舍，不得清空。

## Final Prose Pass\n若已挂载参考样例，返回 JSON 前确认修订没有抹平所选样例的叙述节奏、修辞发动和细节组织；检查段尾、场尾是否在证据已经成立后又补了解释句并删除；随后对 prose 中的阿拉伯数字、中文数词、序数和量化单位重新完成语义重写。{_QUANTITATIVE_DETAIL_RULE}
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


def _scene_performance_enabled(config: dict[str, Any]) -> bool:
    application = config.get("application")
    settings = application.get("scene_performance_agents") if isinstance(application, dict) else None
    return isinstance(settings, dict) and settings.get("enabled") is True


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid Pi scene cache: {path.name}")
    return value


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


__all__ = [
    "PiSceneRuntimeMetrics",
    "PiSceneTransactionRuntime",
    "creative_result_from_payload",
    "render_scene_create_prompt",
    "render_scene_revision_prompt",
    "render_scene_review_prompt",
    "review_result_from_payload",
]
