"""Pi Worker adapter for lean scene create and conditional review calls."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable

from literary_engineering_studio_engine.public.literary import (
    ChangeProposal,
    CreativeResult,
    ReviewDecision,
    ReviewResult,
    SceneBrief,
    SceneDelta,
    VerificationReport,
)

from ..runtime.prompt_recipes import lean_scene_prompt_recipe
from ..runtime.role_conversation import RoleConversationGateway
from ..infrastructure.project_scene_transactions import known_scene_refs

_MACHINE_FIELDS = frozenset({
    "task_id", "transaction_id", "project_root", "expected_outputs", "completion_marker", "sha256",
})

_QUANTITATIVE_DETAIL_RULE = "新增精确数字默认不用。只有以下五项同时成立才保留动态精确值：人物在当前处境中确实需要这份精度；该值会改变眼前选择；改成感知范围会破坏因果；后文会核验或兑现同一精确值；同一压力尚未被别的数字量化。任一项不成立，就按动作、状态变化、后果或人物可感范围逐句重写；不得批量删数字或机械换成模糊量词。仪表读数、倒计时、时长、距离、尺寸、次数、编号、比例和轮次没有题材豁免；年龄、日期、规则编号也只在身份或连续性确有需要时保留。量词中的数词也必须逐项通过，不得把普通陈设或日常动作写成账目；“一张桌、两把椅子、拧两下、试两回、敲两下、看几秒、一支手电”这类计件、计次、计时若不改变选择，应直接写陈设状态、动作受阻、反复无果、停顿或取用结果。读起来具体、有画面或显得专业，都不能替代五项因果证明。"


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
        cache = self._cache_path(transaction_id, "creative_result.json")
        cached = _read_json(cache)
        if cached is not None:
            self._cache_hits += 1
            return creative_result_from_payload(cached)
        prompt = render_scene_create_prompt(
            brief,
            source_evidence=self._source_evidence(brief, purpose="create"),
            allowed_refs=known_scene_refs(brief),
        )
        answer = self._run(prompt, role="worker", transaction_id=transaction_id)
        result = creative_result_from_payload(_answer_payload(answer))
        _atomic_json(cache, result.to_dict())
        return result

    def review_scene(
        self,
        transaction_id: str,
        brief: SceneBrief,
        result: CreativeResult,
        verification: VerificationReport,
    ) -> ReviewResult:
        candidate_digest = hashlib.sha256(result.prose.encode("utf-8")).hexdigest()[:16]
        cache = self._cache_path(transaction_id, f"review_result_{candidate_digest}.json")
        cached = _read_json(cache)
        if cached is not None:
            self._cache_hits += 1
            return review_result_from_payload(cached)
        prompt = render_scene_review_prompt(
            brief,
            result,
            verification,
            source_evidence=self._source_evidence(brief, purpose="review"),
            revision_attempts=len(tuple(cache.parent.glob("revision_result_*.json"))),
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
        cache = self._cache_path(transaction_id, f"revision_result_{attempt}.json")
        cached = _read_json(cache)
        if cached is not None:
            self._cache_hits += 1
            return creative_result_from_payload(cached)
        prompt = render_scene_revision_prompt(
            brief,
            result,
            verification,
            review,
            source_evidence=self._source_evidence(brief, purpose="revise"),
            allowed_refs=known_scene_refs(brief),
        )
        answer = self._run(prompt, role="worker", transaction_id=transaction_id)
        revised = creative_result_from_payload(_answer_payload(answer))
        _atomic_json(cache, revised.to_dict())
        return revised

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

    def _source_evidence(self, brief: SceneBrief, *, purpose: str) -> str:
        recipe = lean_scene_prompt_recipe(purpose)
        remaining = max(0, recipe.soft_character_limit - 8_000)
        blocks: list[str] = []
        for reference in brief.source_refs:
            path = (self._project_root / Path(reference)).resolve()
            if not path.is_relative_to(self._project_root) or not path.is_file():
                continue
            body = path.read_text(encoding="utf-8", errors="replace").strip()
            if not body:
                continue
            excerpt = body[:remaining]
            blocks.append(f"### {reference}\n{excerpt}")
            remaining -= len(excerpt)
            if remaining <= 0:
                break
        return "\n\n".join(blocks)


def render_scene_create_prompt(
    brief: SceneBrief,
    *,
    source_evidence: str = "",
    allowed_refs: Any = (),
) -> str:
    recipe = lean_scene_prompt_recipe("create")
    reference_contract = _reference_contract(brief, allowed_refs)
    prompt = f"""# Scene Create

你是本章唯一的主创。SceneBrief.canon_constraints 与 Relevant Sources 中的最新用户方向是本场硬约束；依据它们写当前场景的完整小说正文，并逐字沿用其中已确定的人名、日期、年份、数量和时间差。保留差值不代表可以改动构成差值的绝对值，同一对象或事件已有精确测量时不得另造替代数值；人物白名单或禁止新专名等限制同样不得用登记 new_asset_candidates 绕过。再提取正文实际造成的语义变化。
直接返回一个 JSON 对象，不要 Markdown 代码围栏、解释、任务回执、路径或哈希。

## SceneBrief
{json.dumps(brief.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Relevant Sources
{source_evidence or "无额外资料；严格使用 SceneBrief。"}

## Allowed Existing Refs
{json.dumps(reference_contract, ensure_ascii=False, separators=(",", ":"))}

## Length Contract
prose 的目标为 {brief.length.target_hanzi} 个中文正文字符，建议范围 {brief.length.soft_min}-{brief.length.soft_max}。必须写成完整场景，不得用梗概、节拍清单或压缩叙述代替正文。
本场只实现 SceneBrief 的 objective、participants、scene_function 与 incoming_handoff。章级义务提供方向，不授权提前演出后续场景；未列入 participants 的主要人物不得登场、发言或完成关键动作。若 Relevant Sources 含上一场正文，只承接其已发生后果，不得重演首次见面、同一调取/发现/交付、同一问答或同一决定。
句群以中等长度句承担主要叙述：短句只落在真正的发现、选择或后果上，较长句可以承载同一动作链、观察层次或复杂因果。逗号服务尚未完成的语义关系；逗号较多时先重组层级，只有关系松散或重复才拆分，禁止按数量机械拆成一串同构短句。不要让连续场景都套用“核对—追问—停顿—留悬念”的程序；用本场独有的动作、关系压力和感官材料组织段落，并让不同人物按各自欲望、回避方式、知识边界和说话习惯作出反应。情绪通过身体反应、记忆触点、避让与选择代价显影，不用抽象总结或心理说明代替。使用中文引号与标点，不输出写作流程痕迹。

## Output
{{"prose":"完整正文","decision_summary":"不超过三句","scene_delta":{{"character_changes":[],"canon_candidates":[],"continuity_changes":[],"promise_updates":[],"reader_question_updates":[],"next_handoff":[],"new_asset_candidates":[]}},"decision_trace":[],"escalation_reasons":[]}}

既有对象变化项使用 {{"target_ref":"Allowed Existing Refs 中的精确字符串","summary":"变化","evidence":"正文证据","operation":"update","attributes":{{}}}}。
character_changes、canon_candidates、continuity_changes、promise_updates、reader_question_updates 的 target_ref 只能逐字选自 Allowed Existing Refs，禁止自造同义 ID。
若不能确定精确 ref，就不要填写该组；不要为了让变化看起来完整而创造 target_ref。
正文出现的新人物、新地点、新组织或尚无精确引用的新事实，只能放入 new_asset_candidates，operation 使用 create；不得塞进既有对象变化组。
若正文给“幸存者”“旧搭档”等角色占位符新增专名、亲属关系或可持续身份，也必须在 new_asset_candidates 登记该身份。仅沿用 SceneBrief 中的通用角色称谓不算新增身份。
空组必须返回 []，禁止用空对象占位。next_handoff 只能是字符串数组，不得返回对象。
只提出正文确实发生的变化；无法确认的内容放进 escalation_reasons。
若 SceneBrief.risk.level 为 high，decision_trace 必须用少量条目记录关键创作取舍。

## Final Prose Pass\n返回 JSON 前，对 prose 中的阿拉伯数字、中文数词、序数和量化单位完成最后一遍语义重写。{_QUANTITATIVE_DETAIL_RULE}
"""
    if len(prompt) > recipe.hard_character_limit:
        raise ValueError("lean scene create prompt exceeds hard character limit")
    return prompt


def render_scene_review_prompt(
    brief: SceneBrief,
    result: CreativeResult,
    verification: VerificationReport,
    *,
    source_evidence: str = "",
    revision_attempts: int = 0,
) -> str:
    recipe = lean_scene_prompt_recipe("review")
    convergence = f"本场已完成 {revision_attempts} 轮返修；此时只有硬事实冲突、明确场景义务缺失或能指出具体读者损害的问题才可继续 revise，孤立句式、局部动作相似或可选润色一律判 pass 并写入 summary。" if revision_attempts >= 2 else "本场尚在前两轮审读，可对有明确证据的实质文学问题提出最小返修。"
    prompt = f"""# Scene Review

你是独立文学审查者。只判断人物可信度、场景变化、文风落实、节奏详略、前后衔接、读者问题和承诺推进；SceneBrief.canon_constraints 与 Relevant Sources 中的最新用户方向优先于候选正文。先逐项核对同一对象或事件的绝对测量值与差值，保留差值不能掩盖绝对值漂移；若候选正文与这些来源在人名、人物白名单、日期、年份、数量或时间差上形成硬冲突，必须判 revise 并指出冲突两端。把新专名登记进 new_asset_candidates 只表示可追踪，不表示在用户禁止新增人物时获得授权。若重复上一场“核对—追问—停顿—留悬念”的程序而实质损害人物声音、情绪因果或场景质感，也应判 revise，并指出重复结构及可保留的有效内容；共享调查题材、档案动作或孤立句式相似本身不是退回理由。
若来源内部详略不同，按“硬 canon 与最新用户方向 > 当前场 scene_goal/objective、scene_turn、outgoing_hook、revealed_info > 章级 dramatic_turn、chapter_ending_policy、payoff_or_delay”的顺序判断；下位概括不能推翻上位且更具体的本场承接。当前场明确要求的核对、登记、追问或离场动作不得仅因动作名称与上一场相似而退回，只有三个以上关键节拍以相同顺序重复且造成可说明的阅读损害，才属于实质同构。市、县、区等行政范围加通用机构类别的称谓不是独特专名；未获得独特名称且不承担持续身份时，无需登记新资产。
{convergence}
确定性检查已经由程序完成，不复查路径、哈希、回执或任务流程。
直接返回 JSON：{{"decision":"pass|revise|escalate","summary":"结论","revision_instructions":[],"evidence":[]}}。
需要改动时必须选择 revise 并给出具体片段证据；轻微建议仍判 pass。
程序的 warning 是提醒，不是自动退回理由。软字数偏差只作建议，不得单独退回；只有人物行为、场景义务、行动层次、选择代价或阅读效果出现可举证损害时才判 revise。不能仅凭 warning 标签本身要求改稿。一次审读只列修复当前可举证实质问题所需的最小指令；先前问题已消失时不得另开与硬约束、场景义务或明确阅读损害无关的新审美议题。
检查正文中新出现的专名或稳定身份是否已进入 new_asset_candidates；仅沿用 SceneBrief 的通用角色称谓、普通设备名或场所类别无需登记。真正遗漏会影响后续场景时判 revise。

## SceneBrief
{json.dumps(brief.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Deterministic Report
{json.dumps(verification.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Candidate
{result.prose}

## Relevant Sources
{source_evidence or "无额外资料。"}

## Quantitative Detail Review\n逐处检查候选正文中的精确时间、时长、距离、尺寸、次数、件数、编号、比例、读数和轮次。{_QUANTITATIVE_DETAIL_RULE} 不能因为表达自然、具体或有画面就放过；任何一处明显不满足五项条件的精确值都会制造记账感或仪表盘式伪真实感，须引用具体片段判 revise；不要按数字密度或数量阈值裁决。
"""
    if len(prompt) > recipe.hard_character_limit:
        raise ValueError("lean scene review prompt exceeds hard character limit")
    return prompt


def render_scene_revision_prompt(
    brief: SceneBrief,
    result: CreativeResult,
    verification: VerificationReport,
    review: ReviewResult | None,
    *,
    source_evidence: str = "",
    allowed_refs: Any = (),
) -> str:
    recipe = lean_scene_prompt_recipe("revise")
    instructions = list(review.revision_instructions) if review is not None else []
    reference_contract = _reference_contract(brief, allowed_refs)
    prompt = f"""# Scene Revision

你是本场景原主创。只修复列出的硬失败或文学问题，保留有效情节、人物声音和已有细节。SceneBrief.canon_constraints 与 Relevant Sources 中的最新用户方向仍是硬约束；每轮返修都必须重新核对既定人名、人物白名单、日期、年份、绝对数值、差值与时间间隔，不得在修复一个问题时重新引入已消失的冲突，也不得用 new_asset_candidates 绕过禁止新增专名的方向。
不得用另一种模板化转折替换问题表达。修改后的正文仍须满足同一 SceneBrief，并重新提取实际 SceneDelta。
修订长句、逗号或标点问题时应重组句内层级，不能把原句机械拆成一串结构相同的短句；保持中等长度句为叙述主体，并保护原有的长短句落差。
直接返回与 Scene Create 完全相同的 JSON 对象，不要 Markdown、工作流说明、路径或哈希。

## SceneBrief
{json.dumps(brief.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Candidate
{result.prose}

## Existing SceneDelta
{json.dumps(result.scene_delta.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Deterministic Issues
{json.dumps(verification.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Review Instructions
{json.dumps(instructions, ensure_ascii=False, separators=(",", ":"))}

## Relevant Sources
{source_evidence or "无额外资料。"}

## Allowed Existing Refs
{json.dumps(reference_contract, ensure_ascii=False, separators=(",", ":"))}

## Length Contract
prose 的目标为 {brief.length.target_hanzi} 个中文正文字符，建议范围 {brief.length.soft_min}-{brief.length.soft_max}。若审查要求扩写，必须补充有效行动、信息、关系压力或选择代价，不得用重复解释凑字数。

## Output
{{"prose":"修订后的完整正文","decision_summary":"不超过三句","scene_delta":{{"character_changes":[],"canon_candidates":[],"continuity_changes":[],"promise_updates":[],"reader_question_updates":[],"next_handoff":[],"new_asset_candidates":[]}},"decision_trace":[],"escalation_reasons":[]}}

修订 SceneDelta 时删除无效条目，不得保留空对象或把字段改成空字符串来占位。
既有变化组的 target_ref 只能逐字选自 Allowed Existing Refs；找不到精确既有引用的新事实改放 new_asset_candidates，operation 使用 create。
角色占位符在正文中获得新专名、亲属关系或可持续身份时，须补入 new_asset_candidates；通用角色称谓和普通设备名不登记。
空组返回 []。next_handoff 只能是字符串数组。
若 SceneBrief.risk.level 为 high，decision_trace 必须保留关键创作取舍，不得清空。

## Final Prose Pass\n返回 JSON 前，对 prose 中的阿拉伯数字、中文数词、序数和量化单位重新完成语义重写。{_QUANTITATIVE_DETAIL_RULE}
"""
    if len(prompt) > recipe.hard_character_limit:
        raise ValueError("lean scene revision prompt exceeds hard character limit")
    return prompt


def creative_result_from_payload(payload: dict[str, Any]) -> CreativeResult:
    _reject_machine_fields(payload)
    prose = str(payload.get("prose") or "").strip()
    summary = str(payload.get("decision_summary") or "").strip()
    if not prose or not summary:
        raise ValueError("Pi scene result requires prose and decision_summary")
    delta = payload.get("scene_delta")
    values = delta if isinstance(delta, dict) else {}
    return CreativeResult(
        prose=prose,
        decision_summary=summary,
        scene_delta=SceneDelta(
            character_changes=_proposals(values.get("character_changes")),
            canon_candidates=_proposals(values.get("canon_candidates")),
            continuity_changes=_proposals(values.get("continuity_changes")),
            promise_updates=_proposals(values.get("promise_updates")),
            reader_question_updates=_proposals(values.get("reader_question_updates")),
            next_handoff=_strings(values.get("next_handoff")),
            new_asset_candidates=_proposals(
                values.get("new_asset_candidates"),
                default_operation="create",
            ),
        ),
        decision_trace=_strings(payload.get("decision_trace")),
        escalation_reasons=_strings(payload.get("escalation_reasons")),
    )


def review_result_from_payload(payload: dict[str, Any]) -> ReviewResult:
    _reject_machine_fields(payload)
    try:
        decision = ReviewDecision(str(payload.get("decision") or "").strip().lower())
    except ValueError as exc:
        raise ValueError("Pi scene review decision must be pass, revise, or escalate") from exc
    return ReviewResult(
        decision=decision,
        summary=str(payload.get("summary") or "").strip(),
        revision_instructions=_strings(payload.get("revision_instructions")),
        evidence=_strings(payload.get("evidence")),
    )


def _proposals(
    value: Any,
    *,
    default_operation: str = "update",
) -> tuple[ChangeProposal, ...]:
    if not isinstance(value, list):
        return ()
    proposals: list[ChangeProposal] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        pairs = _proposal_attributes(item.get("attributes"))
        target_ref = str(item.get("target_ref") or "").strip()
        summary = str(item.get("summary") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        if not target_ref and not summary and not evidence and not pairs:
            continue
        proposals.append(
            ChangeProposal(
                target_ref=target_ref,
                summary=summary,
                evidence=evidence,
                operation=str(item.get("operation") or default_operation).strip(),
                attributes=pairs,
            )
        )
    return tuple(proposals)


def _proposal_attributes(value: Any) -> tuple[tuple[str, str], ...]:
    if isinstance(value, dict):
        return tuple((str(key), str(entry)) for key, entry in value.items())
    if isinstance(value, list):
        return tuple(
            (str(pair[0]), str(pair[1]))
            for pair in value
            if isinstance(pair, list) and len(pair) == 2
        )
    return ()


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    strings: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = next(
                (
                    str(item.get(key) or "").strip()
                    for key in ("handoff", "summary", "content", "text", "description")
                    if str(item.get(key) or "").strip()
                ),
                "",
            )
        else:
            text = ""
        if text:
            strings.append(text)
    return tuple(strings)


def _reference_contract(brief: SceneBrief, allowed_refs: Any) -> list[str]:
    supplied = {str(item).strip() for item in allowed_refs if str(item).strip()}
    if not supplied:
        supplied.update(brief.source_refs)
        supplied.update(brief.canon_constraints)
        supplied.update(brief.chapter_obligations)
        supplied.update(brief.participants)
    return sorted(item for item in supplied if item)


def _reject_machine_fields(payload: dict[str, Any]) -> None:
    unexpected = sorted(_MACHINE_FIELDS.intersection(payload))
    if unexpected:
        raise ValueError("Pi response contains Studio-owned fields: " + ", ".join(unexpected))


def _answer_payload(answer: str) -> dict[str, Any]:
    text = answer.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip() if len(lines) >= 3 else text
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise ValueError("Pi scene response is not a JSON object")
        try:
            value, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError as exc:
            raise ValueError("Pi scene response is not a JSON object") from exc
    if not isinstance(value, dict):
        raise ValueError("Pi scene response must be a JSON object")
    return value


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
