"""Natural creator turns and post-processing over the existing v2 transaction."""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from literary_engineering_studio_engine.public.literary import (
    parse_creator_material_plan, parse_scene_material_requests_v3,
)
from .pi_scene_payload import creative_result_from_payload, review_result_from_payload
from .scene_creator_memory import SceneCreatorMemoryV1
from .scene_creator_material_policy import material_selection_error
from .scene_material_library import SceneMaterialLibrary
from .scene_natural_output import NaturalOutputProcessor, creator_style, render_style
from .natural_turn_store import NaturalTurnStore


class NaturalCreatorMixin:
    def _natural_processor(self, transaction_id: str, layers: dict[str, str]) -> NaturalOutputProcessor:
        return NaturalOutputProcessor(self._cache_path(transaction_id, "v2"),
            layers["scene.v2.transport.extractor"],
            lambda system, prompt: self._run_natural_text(system, prompt, transaction_id, "reviewer"))

    def _run_natural_text(self, system: str, prompt: str, transaction_id: str, role: str) -> str:
        envelope = json.dumps({"schema": "arcvellum/default-conversation/v1",
                              "system_prompt": system, "prompt": prompt}, ensure_ascii=False)
        return self._run(envelope, role=role, transaction_id=transaction_id)

    def _ask_natural_creator(self, transaction_id, brief, layers, briefing, workspace,
                             coordinator, *, mode, revision_context=None):
        memory_path = self._cache_path(transaction_id, "scene_creator_memory.json")
        memory = SceneCreatorMemoryV1.load(memory_path, brief.scene_id, request_limit_chars=160_000)
        processor = self._natural_processor(transaction_id, layers)
        journal = NaturalTurnStore(self._cache_path(transaction_id, "v2/literary-originals"), "creator")
        failures = 0
        for _ in range(16):
            self._fulfill_v2_pending(memory, memory_path, brief, coordinator, transaction_id)
            context = _creator_context(memory, coordinator, briefing, revision_context)
            context["actor_system_template"] = layers["scene.v2.material.actor"]
            if journal.feedback():
                context["delivery_feedback"] = journal.feedback()
            guidance = "\n\n".join(layers[key] for key in (
                "scene.v2.creator.bootstrap", f"scene.v2.creator.{mode}",
                "scene.v2.creator.delegation", "scene.v2.creator.actor-card",
                "scene.v2.creator.archive", "scene.v2.creator.sandbox", "scene.v2.creator.selection"))
            prompt = guidance + "\n\n本次创作资料：\n" + json.dumps(context, ensure_ascii=False)
            answer = self._preserved_natural_answer(transaction_id, "creator", prompt, lambda:
                self._run_v2_creator(prompt, transaction_id, layers, briefing, workspace, coordinator))
            try:
                payload = processor.process(answer, kind="creator", context=context)
                next_memory = deepcopy(memory)
                next_memory.record_creator(payload, brief, prompt=prompt, request_limit_chars=160_000)
                requests = self._accept_natural_turn(payload, brief, coordinator, memory)
                memory = next_memory
            except ValueError as error:
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
        requests = parse_scene_material_requests_v3(payload, list(brief.participants))
        if requests:
            if str(payload.get("prose") or "").strip():
                raise ValueError("creator offered prose while requesting new materials")
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
        memory = SceneCreatorMemoryV1.load(self._cache_path(transaction_id, "scene_creator_memory.json"),
            brief.scene_id, request_limit_chars=160_000)
        context = {"briefing": briefing, "prose": result.prose,
                   "scene_delta": result.scene_delta.to_dict(), "verification": verification.to_dict(),
                   "material_index": index, "creator_memory": memory.to_dict()}
        journal = NaturalTurnStore(self._cache_path(transaction_id, "v2/literary-originals"), "review")
        if journal.feedback():
            context["delivery_feedback"] = journal.feedback()
        system = render_style(layers["scene.v2.review"], creator_style(briefing))
        prompt = layers["scene.v2.review.protocol"] + "\n\n" + json.dumps(context, ensure_ascii=False)
        answer = self._preserved_natural_answer(transaction_id, "review", system + prompt, lambda:
            self._run_natural_text(system, prompt, transaction_id, "reviewer"))
        try:
            review = review_result_from_payload(self._natural_processor(transaction_id, layers).process(
                answer, kind="review", context=context))
        except ValueError as error:
            journal.reject(system + prompt, error)
            raise
        journal.accept()
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

