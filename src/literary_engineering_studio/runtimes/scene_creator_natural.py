"""Natural creator turns and post-processing over the existing v2 transaction."""
from __future__ import annotations

import json
from hashlib import sha256
from copy import deepcopy
from typing import Any

from literary_engineering_studio_engine.public.literary import (
    parse_creator_material_plan, parse_scene_material_requests_v4,
    verify_creative_result,
    derive_scene_policy, SceneExecutionMode,
)
from .pi_scene_payload import creative_result_from_payload, review_result_from_payload
from .scene_creator_memory import SceneCreatorMemoryV1
from .scene_creator_material_policy import material_selection_error
from .scene_material_library import SceneMaterialLibrary
from .scene_natural_output import NaturalOutputProcessor, creator_style, render_style
from .natural_turn_store import NaturalTurnStore
from .scene_review_continuity import formal_review_payload, record_review, review_continuity
from ..infrastructure.project_scene_transactions import known_scene_refs


class NaturalCreatorMixin:
    def _natural_processor(self, transaction_id: str, layers: dict[str, str], brief=None) -> NaturalOutputProcessor:
        return NaturalOutputProcessor(self._cache_path(transaction_id, "v2"),
            layers["scene.v2.transport.extractor"],
            lambda system, prompt: self._run_natural_text(system, prompt, transaction_id, "reviewer"),
            validate_payload=(lambda payload: _validate_transport_delta(payload, brief)) if brief else None)

    def _run_natural_text(self, system: str, prompt: str, transaction_id: str, role: str) -> str:
        envelope = json.dumps({"schema": "arcvellum/default-conversation/v1",
                              "system_prompt": system, "prompt": prompt}, ensure_ascii=False)
        return self._run(envelope, role=role, transaction_id=transaction_id)

    def _ask_natural_creator(self, transaction_id, brief, layers, briefing, workspace,
                             coordinator, *, mode, revision_context=None):
        memory_path = self._cache_path(transaction_id, "scene_creator_memory.json")
        memory = SceneCreatorMemoryV1.load(memory_path, brief.scene_id, request_limit_chars=160_000)
        processor = self._natural_processor(transaction_id, layers, brief)
        journal = NaturalTurnStore(self._cache_path(transaction_id, "v2/literary-originals"), "creator")
        failures = 0
        replay = journal.feedback()
        for _ in range(16):
            self._fulfill_v2_pending(
                memory, memory_path, brief, coordinator, transaction_id, request_version=4,
            )
            context = _creator_context(memory, coordinator, briefing, revision_context)
            context["actor_system_template"] = layers["scene.v2.material.actor"]
            if journal.feedback():
                context["delivery_feedback"] = journal.feedback()
            prompt = _creator_guidance(layers, mode) + "\n\n本次创作资料：\n" + json.dumps(context, ensure_ascii=False)
            reused = bool(replay)
            answer = replay["previous_answer"] if replay else self._preserved_natural_answer(transaction_id, "creator", prompt, lambda:
                self._run_v2_creator(prompt, transaction_id, layers, briefing, workspace, coordinator))
            replay = None
            try:
                payload = processor.process(answer, kind="creator", context=context, reuse_only=reused)
                next_memory = deepcopy(memory)
                next_memory.record_creator(payload, brief, prompt=prompt, request_limit_chars=160_000)
                requests = self._accept_natural_turn(payload, brief, coordinator, memory)
                memory = next_memory
            except ValueError as error:
                if reused:
                    continue
                journal.reject(prompt, error)
                failures += 1
                if failures >= 2:
                    raise
                continue
            memory.save(memory_path)
            journal.accept()
            if not requests:
                return creative_result_from_payload(payload)
        raise RuntimeError("natural scene creator exceeded its material turns")
    def _accept_natural_turn(self, payload, brief, coordinator, memory):
        requests = parse_scene_material_requests_v4(payload, list(brief.participants))
        if requests:
            if str(payload.get("prose") or "").strip():
                raise ValueError("creator offered prose while requesting new materials")
            coordinator.validate_request_archives(requests)
            if payload.get("material_plan") and coordinator.plan_context() is None:
                coordinator.save_plan(parse_creator_material_plan(payload))
            return requests
        if not str(payload.get("prose") or "").strip():
            raise ValueError("creator response needs actionable invitations or completed prose")
        coordinator.assert_ready_for_prose()
        entries = json.loads((coordinator.root / "materials" / "index.json").read_text(encoding="utf-8"))
        issue = material_selection_error(payload, [item["candidate_id"] for item in entries["entries"]],
                                         memory.material_decisions)
        if issue:
            raise ValueError(issue)
        return ()

    def _review_natural(self, transaction_id, layers, briefing, brief, result, verification, index):
        memory_path = self._cache_path(transaction_id, "scene_creator_memory.json")
        memory = SceneCreatorMemoryV1.load(memory_path,
            brief.scene_id, request_limit_chars=160_000)
        context = {"briefing": briefing, "prose": result.prose,
                   "scene_delta": result.scene_delta.to_dict(), "verification": verification.to_dict(),
                   "material_index": index, "creator_memory": memory.to_dict(),
                   "review_continuity": review_continuity(memory_path.parent, result.prose)}
        journal = NaturalTurnStore(self._cache_path(transaction_id, "v2/literary-originals"), "review")
        if journal.feedback():
            context["delivery_feedback"] = journal.feedback()
        system = render_style(layers["scene.v2.review"], creator_style(briefing))
        prompt = layers["scene.v2.review.protocol"] + "\n\n本次审读资料：\n" + json.dumps(context, ensure_ascii=False)
        answer = self._preserved_natural_answer(transaction_id, "review", system + prompt, lambda:
            self._run_natural_text(system, prompt, transaction_id, "reviewer"))
        try:
            extracted = self._natural_processor(transaction_id, layers).process(
                answer, kind="review", context=context)
            review_payload = formal_review_payload(extracted)
            review = review_result_from_payload(review_payload)
        except ValueError as error:
            journal.reject(system + prompt, error)
            raise
        journal.accept()
        path = self._cache_path(transaction_id,"review_original_v2_"+sha256(result.prose.encode('utf-8')).hexdigest()+'.md')
        path.write_text(answer,encoding='utf-8')
        record_review(memory_path.parent, result.prose, extracted, review_payload, path.name)
        return review

    def _preserved_natural_answer(self, transaction_id, phase, prompt, invoke):
        journal = NaturalTurnStore(self._cache_path(transaction_id, "v2/literary-originals"), phase)
        answer, cached = journal.answer(prompt, invoke)
        if cached:
            self._cache_hits += 1
        return answer


def _creator_context(memory, coordinator, briefing, revision_context) -> dict[str, Any]:
    remembered = memory.to_dict()
    remembered.pop("public_stage", None)
    return {"briefing": briefing, "creator_memory": remembered,
            "material_index": SceneMaterialLibrary(coordinator.root / "materials").index_prompt(),
            "frozen_material_plan": coordinator.plan_context(),
            "revision_context": revision_context, "actor_card_context": coordinator.creator_card_context()}


def _creator_guidance(layers, mode):
    return "\n\n".join(layers[key] for key in (
        "scene.v2.creator.bootstrap", f"scene.v2.creator.{mode}",
        "scene.v2.creator.delegation", "scene.v2.creator.actor-card",
        "scene.v2.creator.archive", "scene.v2.creator.sandbox", "scene.v2.creator.selection"))


def _validate_transport_delta(payload, brief):
    if not payload.get('prose') or not payload.get('decision_summary'):
        return
    policy = derive_scene_policy(mode=SceneExecutionMode.STANDARD, risk=brief.risk)
    report = verify_creative_result(brief, creative_result_from_payload(payload), policy, known_refs=known_scene_refs(brief))
    invalid = [issue.message for issue in report.issues if issue.code=='unknown-delta-target']
    if invalid:
        raise ValueError('；'.join(invalid) + '。未来交接写入 scene_delta.next_handoff；实际改变采用本场已有目标：'
            + ', '.join(sorted(known_scene_refs(brief))))

