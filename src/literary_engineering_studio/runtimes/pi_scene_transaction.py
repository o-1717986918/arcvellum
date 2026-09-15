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


_MACHINE_FIELDS = frozenset(
    {
        "task_id",
        "transaction_id",
        "project_root",
        "expected_outputs",
        "completion_marker",
        "sha256",
    }
)


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
        cache = self._cache_path(
            transaction_id,
            f"review_result_{candidate_digest}.json",
        )
        cached = _read_json(cache)
        if cached is not None:
            self._cache_hits += 1
            return review_result_from_payload(cached)
        prompt = render_scene_review_prompt(
            brief,
            result,
            verification,
            source_evidence=self._source_evidence(brief, purpose="review"),
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

你是本章唯一的主创。依据 SceneBrief 写当前场景的完整小说正文，并提取正文实际造成的语义变化。
直接返回一个 JSON 对象，不要 Markdown 代码围栏、解释、任务回执、路径或哈希。

## SceneBrief
{json.dumps(brief.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Relevant Sources
{source_evidence or "无额外资料；严格使用 SceneBrief。"}

## Allowed Existing Refs
{json.dumps(reference_contract, ensure_ascii=False, separators=(",", ":"))}

## Length Contract
prose 的目标为 {brief.length.target_hanzi} 个中文正文字符，建议范围 {brief.length.soft_min}-{brief.length.soft_max}。必须写成完整场景，不得用梗概、节拍清单或压缩叙述代替正文。

## Output
{{"prose":"完整正文","decision_summary":"不超过三句","scene_delta":{{"character_changes":[],"canon_candidates":[],"continuity_changes":[],"promise_updates":[],"reader_question_updates":[],"next_handoff":[],"new_asset_candidates":[]}},"decision_trace":[],"escalation_reasons":[]}}

既有对象变化项使用 {{"target_ref":"Allowed Existing Refs 中的精确字符串","summary":"变化","evidence":"正文证据","operation":"update","attributes":{{}}}}。
character_changes、canon_candidates、continuity_changes、promise_updates、reader_question_updates 的 target_ref 只能逐字选自 Allowed Existing Refs，禁止自造同义 ID。
正文出现的新人物、新地点、新组织或尚无精确引用的新事实，只能放入 new_asset_candidates，operation 使用 create；不得塞进既有对象变化组。
若正文给“幸存者”“旧搭档”等角色占位符新增专名、亲属关系或可持续身份，也必须在 new_asset_candidates 登记该身份。仅沿用 SceneBrief 中的通用角色称谓不算新增身份。
空组必须返回 []，禁止用空对象占位。next_handoff 只能是字符串数组，不得返回对象。
只提出正文确实发生的变化；无法确认的内容放进 escalation_reasons。
若 SceneBrief.risk.level 为 high，decision_trace 必须用少量条目记录关键创作取舍。
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
) -> str:
    recipe = lean_scene_prompt_recipe("review")
    prompt = f"""# Scene Review

你是独立文学审查者。只判断人物可信度、场景变化、文风落实、节奏详略、前后衔接、读者问题和承诺推进。
确定性检查已经由程序完成，不复查路径、哈希、回执或任务流程。
直接返回 JSON：{{"decision":"pass|revise|escalate","summary":"结论","revision_instructions":[],"evidence":[]}}。
需要改动时必须选择 revise 并给出具体片段证据；轻微建议仍判 pass。
检查正文中新出现的专名或稳定身份是否已进入 new_asset_candidates；仅沿用 SceneBrief 的通用角色称谓、普通设备名或场所类别无需登记。真正遗漏会影响后续场景时判 revise。

## SceneBrief
{json.dumps(brief.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Deterministic Report
{json.dumps(verification.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Candidate
{result.prose}

## Relevant Sources
{source_evidence or "无额外资料。"}
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

你是本场景原主创。只修复列出的硬失败或文学问题，保留有效情节、人物声音和已有细节。
不得用另一种模板化转折替换问题表达。修改后的正文仍须满足同一 SceneBrief，并重新提取实际 SceneDelta。
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
    supplied = {
        str(item).strip()
        for item in allowed_refs
        if str(item).strip()
    }
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
