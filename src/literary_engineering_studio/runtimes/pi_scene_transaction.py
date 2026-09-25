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
    active_style_prompt_text,
    render_style_reference_selection,
)
from ..runtime.role_conversation import RoleConversationGateway
from ..application.style.owner_directive import read_owner_style_directive
from ..infrastructure.project_scene_transactions import known_scene_refs
from .scene_length_completion import complete_first_draft_length
from .scene_conversation_invocation import invoke_actor_turn, invoke_role
from .pi_scene_payload import _answer_payload, creative_result_from_payload, review_result_from_payload
from .pi_scene_author_prompt import render_scene_create_prompt, render_scene_revision_prompt
from .pi_scene_style_history import projection_digest as _projection_digest, recent_lean_reference_ids, scene_reference_context
from .scene_performance import (
    fulfill_scene_material_requests, scene_creative_cache_digest,
    scene_expression_snapshot, scene_performance_materials,
)
from .scene_performance_ownership import author_handoff_materials, compact_performance_materials, has_actor_entries
from ..runtime.prompt_recipes import lean_scene_prompt_recipe
from .scene_source_evidence import scene_source_evidence
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
        expression = self._expression_projection(brief, transaction_id)
        projection_digest = self._creative_projection_digest(selection, expression)
        initial_sources = self._source_evidence(brief, purpose="create")
        style_reference = self._style_reference(selection)
        author_style = self._author_style_reference(style_reference)
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
        saved_materials = _read_json(materials_cache)
        if saved_materials and isinstance(saved_materials.get("materials"), str) and saved_materials["materials"]:
            materials = saved_materials["materials"]
            self._cache_hits += 1
        else:
            materials = scene_performance_materials(
                brief=brief.to_dict(), expression=expression, sources=initial_sources,
                style_reference=style_reference, cache_root=cache.parent, config=self._config,
                project_root=self._project_root,
                invoke=lambda prompt, role: self._run(prompt, role=role, transaction_id=transaction_id),
                invoke_actor_turn=lambda initialization, initialization_answer, history, prompt: self._run_actor_turn(
                    initialization, initialization_answer, history, prompt, transaction_id=transaction_id),
                emit=(lambda event, data: self._event_sink(event, {**data, "scene_transaction_id": transaction_id}))
                if self._event_sink is not None else None,
            )
            _atomic_json(materials_cache, {"materials": materials})
        expression_context = _expression_context_for_prompt(expression, actor_owned=has_actor_entries(materials))
        result, materials = self._ask_creator_with_materials(
            transaction_id, brief, expression, initial_sources, style_reference, materials_cache, materials,
            lambda current: render_scene_create_prompt(
                brief, source_evidence=self._source_evidence(
                    brief, purpose="create", reserve_chars=len(author_handoff_materials(current)) + len(author_style)),
                allowed_refs=known_scene_refs(brief), style_reference_block=author_style,
                expression_context_block=expression_context,
                performance_material_block=author_handoff_materials(current),
                allow_material_requests=_scene_performance_enabled(self._config),
            ),
        )
        result = complete_first_draft_length(
            brief, result,
            lambda prompt: _answer_payload(self._run(prompt, role="worker", transaction_id=transaction_id)),
            actor_owned=has_actor_entries(materials),
            performance_material_block=materials,
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
        expression = self._expression_projection(brief, transaction_id)
        projection_digest = self._creative_projection_digest(selection, expression)
        candidate_digest = hashlib.sha256(result.prose.encode("utf-8")).hexdigest()[:16]
        initial_sources = self._source_evidence(brief, purpose="create")
        creative_digest = scene_creative_cache_digest(projection_digest, brief.to_dict(), initial_sources, self._config)
        _, material_record = _original_performance_materials(
            self._cache_path(transaction_id, f"performance_materials_{creative_digest}.json"))
        if _scene_performance_enabled(self._config) and material_record is None:
            raise RuntimeError("scene review requires the original first-level performance materials")
        materials = str(material_record.get("materials") or "") if material_record else ""
        materials_digest = hashlib.sha256(materials.encode("utf-8")).hexdigest()[:10]
        cache = self._cache_path(transaction_id, f"review_result_v3_{candidate_digest}_{projection_digest}_{materials_digest}.json")
        cached = _read_json(cache)
        if cached is not None:
            self._cache_hits += 1
            return review_result_from_payload(cached)
        revision_attempts = len(tuple(cache.parent.glob(f"revision_result_*_{projection_digest}.json")))
        expression_context = _expression_context_for_prompt(expression, review=True, actor_owned=has_actor_entries(materials))
        compact_materials = compact_performance_materials(materials)
        empty_sources = "无额外资料。"
        base_prompt = render_scene_review_prompt(
            brief, result, verification, source_evidence=empty_sources,
            revision_attempts=revision_attempts, expression_context_block=expression_context,
            performance_material_block=compact_materials,
        )
        source_budget = max(0, lean_scene_prompt_recipe("review").soft_character_limit
                            - len(base_prompt) + len(empty_sources) - 256)
        prompt = render_scene_review_prompt(
            brief, result, verification,
            source_evidence=self._source_evidence(brief, purpose="review", max_chars=source_budget),
            revision_attempts=revision_attempts, expression_context_block=expression_context,
            performance_material_block=compact_materials,
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
        expression = self._expression_projection(brief, transaction_id)
        projection_digest = self._creative_projection_digest(selection, expression)
        initial_sources = self._source_evidence(brief, purpose="create")
        creative_digest = scene_creative_cache_digest(projection_digest, brief.to_dict(), initial_sources, self._config)
        materials_cache, material_record = _original_performance_materials(
            self._cache_path(transaction_id, f"performance_materials_{creative_digest}.json"))
        if _scene_performance_enabled(self._config) and material_record is None:
            raise RuntimeError("scene revision requires the original first-level performance materials")
        materials = str(material_record.get("materials") or "") if material_record else ""
        ownership_tag = "_director_v1" if materials else "_prompt_v5"
        cache = self._cache_path(transaction_id, f"revision_result_{attempt}{ownership_tag}_{projection_digest}.json")
        cached = _read_json(cache)
        if cached is not None:
            self._cache_hits += 1
            return creative_result_from_payload(cached)
        style_reference = self._style_reference(selection)
        author_style = self._author_style_reference(style_reference)
        expression_context = _expression_context_for_prompt(expression, actor_owned=has_actor_entries(materials))
        revised, materials = self._ask_creator_with_materials(
            transaction_id, brief, expression, initial_sources, style_reference, materials_cache, materials,
            lambda current: render_scene_revision_prompt(
                brief, result, verification, review,
                source_evidence=self._source_evidence(
                    brief, purpose="revise", reserve_chars=len(current) + len(author_style)),
                allowed_refs=known_scene_refs(brief), style_reference_block=author_style,
                expression_context_block=expression_context,
                performance_material_block=compact_performance_materials(current) if current else "",
                allow_material_requests=_scene_performance_enabled(self._config),
            ),
        )
        _atomic_json(cache, revised.to_dict())
        return revised

    def _ask_creator_with_materials(
        self, transaction_id: str, brief: SceneBrief, expression: dict[str, Any], sources: str,
        style_reference: str, materials_cache: Path, materials: str,
        render_prompt: Callable[[str], str],
    ) -> tuple[CreativeResult, str]:
        for _ in range(16):
            payload = _answer_payload(self._run(render_prompt(materials), role="worker", transaction_id=transaction_id))
            if not payload.get("material_requests"):
                return creative_result_from_payload(payload), materials
            updated = fulfill_scene_material_requests(
                brief=brief.to_dict(), expression=expression, sources=sources,
                style_reference=style_reference, payload=payload, cache_root=materials_cache.parent,
                config=self._config, project_root=self._project_root,
                invoke=lambda prompt, role: self._run(prompt, role=role, transaction_id=transaction_id),
                invoke_actor_turn=lambda initialization, initialization_answer, history, prompt: self._run_actor_turn(
                    initialization, initialization_answer, history, prompt, transaction_id=transaction_id),
                emit=(lambda event, data: self._event_sink(event, {**data, "scene_transaction_id": transaction_id}))
                if self._event_sink is not None else None,
            )
            if updated == materials:
                raise RuntimeError("scene material request produced no new candidate")
            materials = updated
            _atomic_json(materials_cache, {"materials": materials})
        raise RuntimeError("scene creator continued requesting materials without completing prose")

    def _run(self, prompt: str, *, role: str, transaction_id: str) -> str:
        self._provider_calls += 2 if role == "environment-writer" else 1
        return invoke_role(self._gateway, self._project_root, self._timeout, self._event_sink,
                           transaction_id, prompt, role)

    def _run_actor_turn(
        self, initialization: str, initialization_answer: str,
        history: tuple[tuple[str, str], ...], prompt: str, *, transaction_id: str,
    ) -> tuple[str, str]:
        self._provider_calls += 1 if history else 2
        return invoke_actor_turn(self._gateway, self._project_root, self._timeout, self._event_sink,
                                 transaction_id, initialization, initialization_answer, history, prompt)

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

    def _expression_projection(self, brief: SceneBrief, transaction_id: str) -> dict[str, Any]:
        return scene_expression_snapshot(self._cache_path(transaction_id, "expression_projection.json"),
                                         self._project_root, brief.to_dict())

    def _creative_projection_digest(self, selection: dict[str, Any], expression: dict[str, Any]) -> str:
        owner = read_owner_style_directive(self._project_root)
        basis = _projection_digest(selection, expression) + str(owner["revision"])
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]

    def _style_reference(self, selection: dict[str, Any]) -> str:
        owner = read_owner_style_directive(self._project_root)
        prefix = (
            "## 作者自写文风指令（表达层，沿用项目事实与正式审查）\n" + str(owner["content"]) + "\n\n"
            if owner["active"] else ""
        )
        return prefix + render_style_reference_selection(selection)

    def _author_style_reference(self, selected_reference: str) -> str:
        mounted = active_style_prompt_text(self._project_root)
        if not mounted:
            return selected_reference
        return (
            "### 项目已挂载文风（约束 prose 表达；交付格式由本场 Output 决定）\n"
            + mounted + "\n\n" + selected_reference
        )

    def _source_evidence(self, brief: SceneBrief, *, purpose: str, reserve_chars: int = 0,
                         max_chars: int | None = None) -> str:
        indexed_style = self._style_projection(brief).get("status") in {"selected", "no-scene-match"}
        return scene_source_evidence(
            self._project_root, brief, purpose=purpose,
            indexed_style=indexed_style, reserve_chars=reserve_chars, max_chars=max_chars,
        )


def _expression_context_for_prompt(
    expression: dict[str, Any], *, review: bool = False, actor_owned: bool = False,
) -> str:
    """Pass voice decisions without repeating complete character dossiers in every model call."""

    voices = []
    for item in expression.get("dialogue_intents") or []:
        if not isinstance(item, dict):
            continue
        keys = (("speaker", "wants", "avoids") if actor_owned else
                ("speaker", "wants", "speech_strategy") if review else
                ("speaker", "wants", "avoids", "speech_strategy", "stable_voice"))
        voices.append({key: item[key] for key in keys if key in item})
    compact = {"expression_plan": expression.get("expression_plan") or {}, "voices": voices}
    return json.dumps(compact, ensure_ascii=False, separators=(",", ":"))


def _original_performance_materials(expected: Path) -> tuple[Path, dict[str, Any] | None]:
    """Keep a scene's original rehearsal attached when prompt inputs change mid-transaction."""

    record = _read_json(expected)
    if record is not None:
        return expected, record
    alternatives = [path for path in expected.parent.glob("performance_materials_*.json")
                    if (expected.parent / path.name.replace("performance_materials_", "creative_result_", 1)).is_file()]
    if len(alternatives) == 1:
        return alternatives[0], _read_json(alternatives[0])
    return expected, None


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
