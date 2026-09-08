"""Pi Worker adapter for lean scene create and conditional review calls."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Callable

from literary_engineering_studio_engine.literary.scene.transaction import (
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
        cache = self._cache_path(transaction_id, "review_result.json")
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


def render_scene_create_prompt(brief: SceneBrief, *, source_evidence: str = "") -> str:
    recipe = lean_scene_prompt_recipe("create")
    prompt = f"""# Scene Create

你是本章唯一的主创。依据 SceneBrief 写当前场景的完整小说正文，并提取正文实际造成的语义变化。
直接返回一个 JSON 对象，不要 Markdown 代码围栏、解释、任务回执、路径或哈希。

## SceneBrief
{json.dumps(brief.to_dict(), ensure_ascii=False, separators=(",", ":"))}

## Relevant Sources
{source_evidence or "无额外资料；严格使用 SceneBrief。"}

## Output
{{"prose":"完整正文","decision_summary":"不超过三句","scene_delta":{{"character_changes":[],"canon_candidates":[],"continuity_changes":[],"promise_updates":[],"reader_question_updates":[],"next_handoff":[],"new_asset_candidates":[]}},"decision_trace":[],"escalation_reasons":[]}}

每个变化项使用 {{"target_ref":"已有引用或候选名","summary":"变化","evidence":"正文证据","operation":"update","attributes":{{}}}}。
只提出正文确实发生的变化；无法确认的内容放进 escalation_reasons。
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
            new_asset_candidates=_proposals(values.get("new_asset_candidates")),
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


def _proposals(value: Any) -> tuple[ChangeProposal, ...]:
    if not isinstance(value, list):
        return ()
    proposals: list[ChangeProposal] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        attributes = item.get("attributes")
        if isinstance(attributes, dict):
            pairs = tuple((str(key), str(entry)) for key, entry in attributes.items())
        elif isinstance(attributes, list):
            pairs = tuple(
                (str(pair[0]), str(pair[1]))
                for pair in attributes
                if isinstance(pair, list) and len(pair) == 2
            )
        else:
            pairs = ()
        proposals.append(
            ChangeProposal(
                target_ref=str(item.get("target_ref") or "").strip(),
                summary=str(item.get("summary") or "").strip(),
                evidence=str(item.get("evidence") or "").strip(),
                operation=str(item.get("operation") or "update").strip(),
                attributes=pairs,
            )
        )
    return tuple(proposals)


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


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
    "render_scene_review_prompt",
    "review_result_from_payload",
]
