"""Dormant scene creator v2 transaction adapter, isolated from the v1 route."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.public.prompting import (
    list_prompt_layer_specs, prompt_assembly_manifest, prompt_layer_spec, resolve_prompt_layer,
)
from literary_engineering_studio_engine.public.literary import (
    CreativeResult, ReviewResult, SceneBrief, VerificationReport,
    parse_creator_material_plan, parse_scene_material_requests_v3,
    parse_scene_material_requests_v4,
)

from ..application.creator_persona import CreatorPersonaStore
from .pi_scene_payload import _answer_payload, creative_result_from_payload, review_result_from_payload
from .transaction_style_selection import _work_material_scope
from .scene_prompt_record import record_scene_prompt
from .scene_conversation_invocation import invoke_role
from .scene_creator_briefing import build_scene_creator_briefing
from .scene_creator_material_policy import material_selection_error
from .scene_creator_memory import SceneCreatorMemoryV1
from .scene_creator_v2_materials import (
    MaterialInvocationV2, SceneCreatorV2MaterialCoordinator, assert_v2_prompts_ready,
)
from .scene_creator_workspace import SceneCreatorWorkspace
from .scene_creator_delivery_source import combine_creator_delivery
from .creator_body_boundary import detach_creator_notes
from .scene_material_library import SceneMaterialLibrary
from .scene_creator_natural import NaturalCreatorMixin
from .scene_natural_output import NATURAL_RESPONSE_MODE, creator_style, render_style
from .scene_review_continuity import review_continuity
from .semantic_cache import semantic_cache_digest, prior_review_context
from .scene_material_cache import material_source_digests, material_source_bindings, cached_scene_result
from .natural_creator_prompt import STABLE_PREFIX_LAYOUT, LEGACY_STABLE_PREFIX_LAYOUT
from .scene_cache_layout import cached_layout, book_style, scene_session, source_scope, CONTEXT_RULE, validate_frozen_sources
from .runtime_model_identity import runtime_model_identity
from literary_engineering_studio_engine.public.literary import CONSISTENCY_CONTRACT
from .scene_integrity import checked_creation_cache, read_consistency_record


class SceneCreatorV2Mixin(NaturalCreatorMixin):
    """Keep the versioned opt-in path separate from the committed scene pipeline."""


    def _uses_creator_v2(self, transaction_id: str) -> bool:
        if (self._cache_path(transaction_id, "scene_creator_v2_mode.json").is_file()
                or self._cache_path(transaction_id, "prompt_assembly_v2.json").is_file()):
            return True
        if self._cache_path(transaction_id, "prompt_assembly_v1.json").is_file():
            return False  # An unfinished v1 transaction keeps its original prompt contract.
        application = self._config.get("application")
        settings = application.get("scene_creator_v2") if isinstance(application, dict) else None
        return isinstance(settings, dict) and settings.get("enabled") is True

    def _v2_prompt_snapshot(self, transaction_id: str) -> dict[str, Any]:
        path = self._cache_path(transaction_id, "prompt_assembly_v2.json")
        saved = _validated_prompt_assembly(path)
        if saved is not None:
            return saved
        ids = tuple(spec.layer_id for spec in list_prompt_layer_specs()
                    if spec.layer_id.startswith("scene.v2.") and spec.layer_id not in {
                        "scene.v2.material.shared.protocol", "scene.v2.material.output.protocol"}) + ("project_agent.creator_persona.v2",)
        if self._prompt_snapshot_provider is not None:
            snapshot = self._prompt_snapshot_provider(ids, self._project_root)
        else:
            layers = [resolve_prompt_layer(prompt_layer_spec(layer_id)) for layer_id in ids]
            snapshot = {**prompt_assembly_manifest(layers),
                        "texts": {layer.layer_id: layer.text for layer in layers}}
        snapshot["response_mode"] = NATURAL_RESPONSE_MODE
        snapshot["runtime_contract"] = "creative-literary/2.2-cost-v4"
        layout = (self._config.get("agent_runners", {}).get("pi-worker", {}) or {}).get("conversation_cache_layout", STABLE_PREFIX_LAYOUT)
        if layout not in {STABLE_PREFIX_LAYOUT, LEGACY_STABLE_PREFIX_LAYOUT}:
            raise ValueError("unsupported new creator prompt layout")
        snapshot["creator_prompt_layout"] = layout
        snapshot["runtime_model_binding"] = runtime_model_identity(self._config)
        if self._config.get('application', {}).get('creation_integrity', {}).get('enabled') is True:
            snapshot['creation_integrity_contract'] = CONSISTENCY_CONTRACT
        snapshot["material_scope"] = _work_material_scope(self._project_root)
        _atomic_json(path, snapshot)
        return snapshot

    def _v2_context(self, transaction_id: str, brief: SceneBrief) -> tuple[dict[str, Any], dict[str, Any], SceneCreatorWorkspace]:
        snapshot = self._v2_prompt_snapshot(transaction_id)
        binding = snapshot.get('runtime_model_binding')
        if binding is not None and binding != runtime_model_identity(self._config):
            raise RuntimeError('frozen transaction model binding changed; create a new transaction for the selected model')
        assert_v2_prompts_ready(snapshot["texts"])
        workspace = SceneCreatorWorkspace(self._project_root, self._data_root)
        briefing_path = self._cache_path(transaction_id, "scene_creator_briefing_v2.json")
        briefing = _read_json(briefing_path)
        if briefing is None:
            briefing = build_scene_creator_briefing(brief, workspace, CreatorPersonaStore(self._data_root))
            if briefing["creator_persona"]["status"] != "ready":
                raise RuntimeError("scene creator v2 requires a work-level persona from the top agent")
            self._creator_style_briefing(transaction_id, briefing)
            _atomic_json(briefing_path, briefing)
        if cached_layout(snapshot):
            validate_frozen_sources(briefing, self._project_root, brief)
        _atomic_json(self._cache_path(transaction_id, "scene_creator_v2_mode.json"),
                     {"schema": "arcvellum/scene-creator-mode/v2", "prompt_digest": snapshot["digest"]})
        return snapshot, briefing, workspace

    def _v2_coordinator(
        self, transaction_id: str, brief: SceneBrief,
        layers: dict[str, str], workspace: SceneCreatorWorkspace,
    ) -> SceneCreatorV2MaterialCoordinator:
        expression = self._expression_projection(brief, transaction_id)
        personas = expression.get("actor_personas")
        scope = self._material_scope(transaction_id)
        coordinator = SceneCreatorV2MaterialCoordinator(
            self._cache_path(transaction_id, "v2"), workspace, layers,
            scene_id=brief.scene_id,
            actor_personas={},
            creator_prompt_layout=self._v2_prompt_snapshot(transaction_id).get("creator_prompt_layout", ""),
        )
        coordinator.material_scope = {**scope, "actor_targets": list(dict.fromkeys([*scope.get("actor_targets", []), *brief.participants]))}
        coordinator.integrity_contract = self._v2_prompt_snapshot(transaction_id).get('creation_integrity_contract')
        return coordinator

    def _material_scope(self, transaction_id):
        path = self._cache_path(transaction_id, "transaction_style_bundle.json")
        return ((_read_json(path) or {}).get("material_scope")
                or (_read_json(self._cache_path(transaction_id, "prompt_assembly_v2.json")) or {}).get("material_scope") or {})

    def _create_scene_v2(self, transaction_id: str, brief: SceneBrief) -> CreativeResult:
        snapshot, briefing, workspace = self._v2_context(transaction_id, brief)
        legacy = self._cache_path(transaction_id,"creative_result_v2.json")
        if legacy.is_file():
            self._cache_hits += 1
            return creative_result_from_payload(checked_creation_cache(_read_json(legacy), snapshot,
                                                                       self._cache_path(transaction_id, 'v2')))
        binding = hashlib.sha256(json.dumps({"brief":brief.to_dict(),"briefing":briefing,
            "snapshot":snapshot},ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:24]
        cache = self._cache_path(transaction_id, "creative_result_v3_"+binding+".json")
        saved = _read_json(cache)
        if saved is not None:
            self._cache_hits += 1
            return creative_result_from_payload(checked_creation_cache(saved, snapshot, self._cache_path(transaction_id, 'v2')))
        coordinator = self._v2_coordinator(transaction_id, brief, snapshot["texts"], workspace)
        result = self._ask_creator_v2(transaction_id, brief, snapshot["texts"], briefing,
                                      workspace, coordinator, mode="create")
        _atomic_json(cache, {**result.to_dict(),"cache_binding":{"context_digest":binding,
            "body_sha256":hashlib.sha256(result.prose.encode()).hexdigest()}})
        return result

    def _review_scene_v2(
        self, transaction_id: str, brief: SceneBrief, result: CreativeResult,
        verification: VerificationReport,
    ) -> ReviewResult:
        snapshot, _briefing, workspace = self._v2_context(transaction_id, brief)
        coordinator = self._v2_coordinator(transaction_id, brief, snapshot["texts"], workspace)
        index = SceneMaterialLibrary(coordinator.root / "materials").index_prompt()
        continuity = prior_review_context(review_continuity(self._cache_path(transaction_id,"scene_creator_memory.json").parent,result.prose))
        memory = self._creator_memory(transaction_id,brief)
        material_binding, legacy_material_binding = material_source_bindings(coordinator.root)
        sources = {"materials":material_binding,
                "creator_intent":memory.intent.to_dict() if memory.intent else None,
                "material_decisions":memory.current_decisions(),"unresolved_questions":memory.unresolved_questions}
        if snapshot.get('creation_integrity_contract'):
            sources['consistency_record'] = read_consistency_record(self._cache_path(transaction_id, 'v2'), result.prose)
        binding = dict(brief=brief,result=result,verification=verification,
                       briefing=_briefing,snapshot=snapshot,continuity=continuity)
        digest = semantic_cache_digest("review", **binding, sources=sources)
        legacy_digest = semantic_cache_digest("review", **binding,
            sources={**sources, "materials": legacy_material_binding})
        cache = self._cache_path(transaction_id, f"review_result_v3_{digest}.json")
        saved = cached_scene_result(cache,
            self._cache_path(transaction_id, f"review_result_v3_{legacy_digest}.json"), review_result_from_payload)
        if saved is not None:
            self._cache_hits += 1
            return saved
        prompt = json.dumps({
            "schema": "arcvellum/scene-review-task/v2",
            "protocol": snapshot["texts"]["scene.v2.review.protocol"],
            "guidance": snapshot["texts"]["scene.v2.review"],
            "briefing": _briefing, "prose": result.prose,
            "scene_delta": result.scene_delta.to_dict(),
            "verification": verification.to_dict(),
            "creative_intent": self._creator_memory(transaction_id, brief).render_context(),
            "material_index": index,
        }, ensure_ascii=False)
        if snapshot.get("response_mode") == NATURAL_RESPONSE_MODE:
            review = self._review_natural(transaction_id, snapshot["texts"], _briefing, brief, result, verification, index)
        else:
            review = review_result_from_payload(_answer_payload(
                self._run(prompt, role="reviewer", transaction_id=transaction_id)))
        _atomic_json(cache, {"decision": review.decision.value, "summary": review.summary,
                             "revision_instructions": list(review.revision_instructions),
                             "evidence": list(review.evidence)})
        return review

    def _revise_scene_v2(
        self, transaction_id: str, brief: SceneBrief, result: CreativeResult,
        verification: VerificationReport, review: ReviewResult | None, attempt: int,
    ) -> CreativeResult:
        snapshot, briefing, workspace = self._v2_context(transaction_id, brief)
        boundary=detach_creator_notes(result.to_dict())
        if boundary['prose']!=result.prose:
            _atomic_json(self._cache_path(transaction_id,'body_boundary_recovery_'+hashlib.sha256(result.prose.encode()).hexdigest()[:24]+'.json'),boundary)
            return creative_result_from_payload(boundary)
        review_context = ({"decision":review.decision.value,"summary":review.summary,
            "revision_instructions":list(review.revision_instructions),"evidence":list(review.evidence)} if review else None)
        editor_candidates = self._tone_candidates(transaction_id,result.prose)
        if editor_candidates:
            review_context = {**(review_context or {}),"editor_candidates":editor_candidates}
        continuity = review_continuity(self._cache_path(transaction_id,"scene_creator_memory.json").parent,result.prose)
        material_binding, legacy_material_binding = material_source_bindings(self._cache_path(transaction_id,"v2"))
        digest = semantic_cache_digest("revision",brief=brief,result=result,verification=verification,
            briefing=briefing,snapshot=snapshot,sources=material_binding,
            continuity=continuity,review=review_context,attempt=attempt)
        legacy_digest = semantic_cache_digest("revision",brief=brief,result=result,verification=verification,
            briefing=briefing,snapshot=snapshot,
            sources=legacy_material_binding,
            continuity=continuity,review=review_context,attempt=attempt)
        cache = self._cache_path(transaction_id, f"revision_result_v3_{attempt}_{digest}.json")
        saved = cached_scene_result(cache,
            self._cache_path(transaction_id, f"revision_result_v3_{attempt}_{legacy_digest}.json"),
            lambda payload: creative_result_from_payload(checked_creation_cache(payload, snapshot,
                                                                                self._cache_path(transaction_id, 'v2'))))
        if saved is not None:
            self._cache_hits += 1
            return saved
        coordinator = self._v2_coordinator(transaction_id, brief, snapshot["texts"], workspace)
        context = {"previous_prose": result.prose, "previous_scene_delta": result.scene_delta.to_dict(),
                   "editor_candidates":editor_candidates,
                   "verification": verification.to_dict(),
                   "review_continuity": review_continuity(
                       self._cache_path(transaction_id, "scene_creator_memory.json").parent, result.prose),
                   "review": ({"decision": review.decision.value, "summary": review.summary,
                               "revision_instructions": list(review.revision_instructions)}
                              if review is not None else None)}
        if review is not None:
            source = self._review_original(transaction_id,result.prose)
            if source:
                context['review_original'] = source
        revised = self._ask_creator_v2(transaction_id, brief, snapshot["texts"], briefing,
                                       workspace, coordinator, mode="revise", revision_context=context)
        _atomic_json(cache, revised.to_dict())
        completed_digest = semantic_cache_digest("revision",brief=brief,result=result,verification=verification,
            briefing=briefing,snapshot=snapshot,sources=_material_sources(coordinator.root),
            continuity=continuity,review=review_context,attempt=attempt)
        if completed_digest != digest:
            _atomic_json(self._cache_path(transaction_id,f"revision_result_v3_{attempt}_{completed_digest}.json"),
                revised.to_dict())
        return revised

    def _review_original(self,transaction_id,prose):
        digest=hashlib.sha256(prose.encode('utf-8')).hexdigest()
        paths = sorted(self._cache_path(transaction_id,'').glob('review_original_v3_'+digest+'_*.md'),
                       key=lambda path:path.stat().st_mtime,reverse=True)
        path=paths[0] if paths else self._cache_path(transaction_id,'review_original_v2_'+digest+'.md')
        if not path.is_file():
            return None
        return {'content':path.read_text(encoding='utf-8'),'source':path.name,'prose_sha256':digest}

    def _ask_creator_v2(
        self, transaction_id: str, brief: SceneBrief, layers: dict[str, str],
        briefing: dict[str, Any], workspace: SceneCreatorWorkspace,
        coordinator: SceneCreatorV2MaterialCoordinator, *, mode: str,
        revision_context: dict[str, Any] | None = None,
    ) -> CreativeResult:
        if "scene.v2.transport.extractor" in layers:
            return self._ask_natural_creator(transaction_id, brief, layers, briefing, workspace,
                coordinator, mode=mode, revision_context=revision_context)
        memory_path = self._cache_path(transaction_id, "scene_creator_memory.json")
        memory = SceneCreatorMemoryV1.load(memory_path, brief.scene_id, request_limit_chars=160_000)
        for _ in range(16):
            self._fulfill_v2_pending(memory, memory_path, brief, coordinator, transaction_id)
            index = SceneMaterialLibrary(coordinator.root / "materials").index_prompt()
            prompt = json.dumps({
                "schema": "arcvellum/scene-creator-task/v2", "mode": mode,
                "briefing": briefing, "creator_memory": memory.render_context(),
                "material_index": index, "revision_context": revision_context,
                "actor_card_context": coordinator.creator_card_context(),
                "actor_system_template": layers["scene.v2.material.actor"],
                "guidance": "\n\n".join(layers[key] for key in (
                    "scene.v2.creator.bootstrap", f"scene.v2.creator.{mode}",
                    "scene.v2.creator.delegation", "scene.v2.creator.actor-card", "scene.v2.creator.archive",
                    "scene.v2.creator.sandbox", "scene.v2.creator.selection",
                )),
            }, ensure_ascii=False)
            payload = _answer_payload(self._run_v2_creator(prompt, transaction_id, layers,
                                                            briefing, workspace, coordinator))
            if payload.get("material_plan") is not None:
                coordinator.save_plan(parse_creator_material_plan(payload))
            requests = parse_scene_material_requests_v3(payload, list(brief.participants))
            if requests:
                if str(payload.get("prose") or "").strip():
                    raise ValueError("scene creator v2 cannot write prose before requested materials return")
                memory.record_creator(payload, brief, prompt=prompt, request_limit_chars=160_000)
                memory.save(memory_path)
                continue
            if not str(payload.get("prose") or "").strip():
                raise ValueError("scene creator v2 must request material or deliver prose")
            coordinator.assert_ready_for_prose()
            library_index = _read_json(coordinator.root / "materials" / "index.json") or {}
            ids = [str(item.get("candidate_id") or "") for item in library_index.get("entries") or []]
            issue = material_selection_error(payload, ids, memory.material_decisions)
            if issue:
                raise ValueError(issue)
            memory.record_creator(payload, brief, prompt=prompt, request_limit_chars=160_000)
            memory.save(memory_path)
            return creative_result_from_payload(payload)
        raise RuntimeError("scene creator v2 exceeded its bounded material turns")

    def _fulfill_v2_pending(
        self, memory: SceneCreatorMemoryV1, memory_path: Path, brief: SceneBrief,
        coordinator: SceneCreatorV2MaterialCoordinator, transaction_id: str,
        *, request_version: int = 3,
    ) -> None:
        if memory.pending_request is None:
            return
        parser = parse_scene_material_requests_v4 if request_version == 4 else parse_scene_material_requests_v3
        scope = coordinator.material_scope
        pending = parser(memory.pending_request, scope.get("actor_targets", list(brief.participants)),
            **({"free_character_subjects": scope.get("version") == "work-v1"} if request_version == 4 else {}))
        adopted_candidate_ids = {
            item["candidate_id"] for item in memory.current_decisions() if item["decision"] in {"use","adapt"}
        }
        for request in pending:
            coordinator.execute(
                request, lambda call: self._invoke_v2_material(call, transaction_id),
                adopted_candidate_ids=adopted_candidate_ids,
                adopted_decisions={row["candidate_id"]:row for row in memory.current_decisions()
                                   if row["candidate_id"] in adopted_candidate_ids},
            )
        memory.pending_request = None
        memory.candidate_ids = list(SceneMaterialLibrary(coordinator.root / 'materials').candidate_ids())
        memory.phase = "material-ready"
        memory.save(memory_path)

    def _run_v2_creator(
        self, prompt: str, transaction_id: str, layers: dict[str, str],
        briefing: dict[str, Any], workspace: SceneCreatorWorkspace,
        coordinator: SceneCreatorV2MaterialCoordinator,
        *, purpose: str = "creator", tool_policy: str = "full", metadata_repair: bool = False,
    ) -> str:
        literary_identity = layers["scene.v2.creator.identity"]
        cached = cached_layout(self._v2_prompt_snapshot(transaction_id))
        if "scene.v2.transport.extractor" in layers:
            literary_identity = render_style(literary_identity, book_style(briefing) if cached else creator_style(briefing))
        identity = "\n\n".join((
            layers["scene.v2.creator.protocol"],
            literary_identity, briefing["creator_persona"]["text"],
        ))
        if cached:
            identity += "\n" + CONTEXT_RULE
        if metadata_repair and not cached:
            identity += '\n\n当前仅补交指定元数据。请按本次 response_contract 直接交付 JSON patches 对象；对象与列表保持结构，knowledge 仅用 known/reference。正文、其余判断和未授权字段继续冻结。'
        envelope = json.dumps({
            "schema": "arcvellum/scene-creator/v2", "system_prompt": identity,
            "call_purpose": purpose, "tool_policy": tool_policy,
            "material_root": str(coordinator.root / "materials"),
            "archive_root": str(workspace.archive_root),
            "scratch_root": str(workspace.scratch_root), "prompt": prompt,
            **({"conversation_session":scene_session(self,transaction_id,"creator-"+tool_policy,
                source_scope(self,transaction_id,prompt) if tool_policy != "full" else "")} if cached else {}),
        }, ensure_ascii=False)
        self._provider_calls += 1
        record_scene_prompt(self, transaction_id, "worker", envelope)
        messages=[]
        def observe(event,data):
            if event=='agent.message.completed' and isinstance(data.get('text'),str):
                messages.append(data['text'])
            if self._event_sink:
                self._event_sink(event,data)
        answer=invoke_role(self._gateway,self._project_root,self._timeout,observe,
                           transaction_id,envelope,'worker')
        return combine_creator_delivery(answer,messages) if purpose in {'creator','revision'} else answer

    def _invoke_v2_material(self, call: MaterialInvocationV2, transaction_id: str) -> dict[str, Any]:
        answer, initialized = self._material_original(call, transaction_id)
        if call.response_mode == NATURAL_RESPONSE_MODE:
            layers = self._v2_prompt_snapshot(transaction_id)["texts"]
            payload = self._natural_processor(transaction_id, layers).process(answer, kind="material",
                context={"role": call.role, "request": call.request_context,
                         "invitation": call.prompt, "attachment_manifest": call.attachment_manifest})
        else:
            payload = _answer_payload(answer)
        return {**payload, "__answer": answer,
                "__initialization_answer": initialized}

    def _material_original(self, call: MaterialInvocationV2, transaction_id: str) -> tuple[str, str]:
        path = self._cache_path(transaction_id, f"v2/material-originals/{call.request_id}.json")
        saved = _read_json(path) if call.response_mode == NATURAL_RESPONSE_MODE else None
        if saved is not None:
            self._cache_hits += 1
            return saved["answer"], saved["initialized"]
        if call.role == "character-actor":
            answer, initialized = self._run_actor_turn(
                call.initialization, call.initialization_answer, call.history,
                call.prompt, transaction_id=transaction_id,
            )
        else:
            answer, initialized = self._run_initialized_role_turn(
                call.role, call.initialization, call.history, call.prompt,
                transaction_id=transaction_id,
            )
        if call.response_mode == NATURAL_RESPONSE_MODE:
            _atomic_json(path, {"answer": answer, "initialized": initialized})
        return answer, initialized

def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid Pi scene cache: {path.name}")
    return value


def _material_sources(root):
    return material_source_digests(root)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _validated_prompt_assembly(path: Path) -> dict[str, Any] | None:
    saved = _read_json(path)
    if saved is not None and (
        saved.get("schema") != "arcvellum/prompt-assembly/v1"
        or not isinstance(saved.get("texts"), dict)
    ):
        raise ValueError("scene prompt assembly cache is invalid")
    return saved
