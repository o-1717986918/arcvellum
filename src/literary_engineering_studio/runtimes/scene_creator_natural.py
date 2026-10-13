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
    actor_card_schema_for_template,
    CreativeIntentV1,
)
from .pi_scene_payload import _answer_payload, creative_result_from_payload, review_result_from_payload
from .scene_creator_memory import SceneCreatorMemoryV1
from .scene_creator_material_policy import MaterialSelectionError, material_selection_error, repair_material_choice
from .scene_material_library import SceneMaterialLibrary
from .scene_natural_output import (
    NaturalOutputProcessor, briefing_for_natural_context, creator_style, render_style,
)
from .natural_turn_store import NaturalTurnStore
from .natural_transport_repair import NaturalExtractionError, NaturalSourceClarificationError, recovery_issue
from .natural_field_repair import field_repair_task
from .natural_repair_progress import SourceRepairProgress
from .natural_review_recovery import saved_review_answer,review_context_digest
from .scene_creator_delivery_source import recover_saved_creator_delivery
from .material_usage_evidence import annotate_material_usage, save_material_usage_audit
from .material_need import needs_required, record_source_needs,validate_source_needs,repair_candidate_sources
from .semantic_cache import prior_review_context
from .natural_creator_prompt import STABLE_PREFIX_LAYOUT, LEGACY_STABLE_PREFIX_LAYOUT, stable_creator_prompt
from .scene_cache_layout import cached_layout, cached_runtime, cached_context, scene_session, source_scope, review_layout
from .scene_review_continuity import formal_review_payload, record_review, review_continuity
from ..infrastructure.project_scene_transactions import known_scene_refs
from .scene_integrity import (save_consistency_record, read_consistency_record, current_review_context,
                             prior_delta_context, validate_current_material_choices, creator_integrity_context,
                             material_need_version, integrity_review_context, save_review_integrity)


class NaturalCreatorMixin:
    def _natural_processor(self, transaction_id: str, layers: dict[str, str], brief=None,coordinator=None) -> NaturalOutputProcessor:
        return NaturalOutputProcessor(self._cache_path(transaction_id, "v2"),
            layers["scene.v2.transport.extractor"],
            lambda system, prompt: self._run_natural_text(system, prompt, transaction_id, "transport"),
            validate_payload=(lambda payload: _validate_creator_context(payload,brief,coordinator)) if brief else None)

    def _run_natural_text(self, system: str, prompt: str, transaction_id: str, role: str, *, purpose=None) -> str:
        cached = cached_layout(self._v2_prompt_snapshot(transaction_id))
        if purpose=='evidence-repair' and not cached:
            system+='\n当前任务仅修复指定证据字段。严格按 response_contract 交付 JSON patches；value 选择 context.prose_source 中现有段落的 prose_sha256/prose_block 引用，不凭记忆重抄引文，不写评价或新判断。其余判断与正文冻结。'
        envelope = json.dumps({"schema": "arcvellum/default-conversation/v1",
                              "system_prompt": system, "prompt": prompt,
                              "call_purpose": purpose or ("record-repair" if role == "transport" else "review" if role == "reviewer" else "creator"),
                              **({"conversation_session":scene_session(self,transaction_id,role,source_scope(self,transaction_id,prompt))} if cached else {})}, ensure_ascii=False)
        return self._run(envelope, role=role, transaction_id=transaction_id)

    def _source_field_repair(self, transaction_id, processor, answer, kind, context, error, invoke,material_sources=None):
        if cached_runtime(self, transaction_id):
            context = {**context, "request_layout":STABLE_PREFIX_LAYOUT}
        seen=set()
        progress=SourceRepairProgress(processor.root, kind, answer)
        binding=sha256(json.dumps([answer,kind,context,error.payload,error.fields,processor.system_prompt],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        completed=progress.completed(binding)
        if completed:
            return processor.revalidate_record(completed["source"],completed["payload"],kind,context)
        while True:
            if not error.fields or not isinstance(error.payload, dict):
                raise error
            if material_sources is not None:
                selected=repair_candidate_sources(error.payload,error.fields,material_sources,
                    complete_review=context.get('material_need_contract') == 'v2')
                if selected:
                    context={**context,'material_source_evidence':selected}
            if any(path.endswith('/character_card') for path in error.fields):
                layers=self._v2_prompt_snapshot(transaction_id)['texts']
                context={**context,'actor_system_template':layers['scene.v2.material.actor'],
                    'actor_card_design_guidance':layers['scene.v2.creator.actor-card']}
            signature=progress.register(error)
            task = json.dumps({**field_repair_task(answer,error.payload,error.fields,context),
                              "failure":recovery_issue(error,answer),
                              **progress.feedback_fields()},ensure_ascii=False)
            key=sha256(task.encode()).hexdigest()
            if key in seen:
                raise error
            seen.add(key)
            reply = self._preserved_natural_answer(transaction_id,kind+"-field-repair",task,lambda:invoke(task))
            try:
                result=processor.process_field_repair(answer,reply,kind=kind,context=context,
                    payload=error.payload,fields=error.fields)
                progress.complete(binding,answer+'\n\n【原作者指定字段补交】\n'+reply,result)
                return result
            except NaturalSourceClarificationError as next_error:
                answer=progress.advance(answer,next_error,reply,signature)
                error=next_error

    def _ask_natural_creator(self, transaction_id, brief, layers, briefing, workspace,
                             coordinator, *, mode, revision_context=None):
        memory_path = self._cache_path(transaction_id, "scene_creator_memory.json")
        memory = SceneCreatorMemoryV1.load(memory_path, brief.scene_id, request_limit_chars=160_000)
        processor = self._natural_processor(transaction_id, layers, brief,coordinator)
        journal = NaturalTurnStore(self._cache_path(transaction_id, "v2/literary-originals"), "creator")
        replay = journal.feedback()
        for _ in range(16):
            self._recover_pending_material_plan(memory, coordinator, transaction_id, layers, briefing, workspace, processor)
            self._fulfill_v2_pending(
                memory, memory_path, brief, coordinator, transaction_id, request_version=4,
            )
            context = _creator_context(memory, coordinator, briefing, revision_context)
            if getattr(coordinator, "creator_prompt_layout", "") == STABLE_PREFIX_LAYOUT:
                context["briefing"] = cached_context(briefing)
                context["current_style_direction"] = creator_style(briefing)
            context['available_delta_targets'] = sorted(known_scene_refs(brief))
            context['actor_card_schema'] = actor_card_schema_for_template(layers['scene.v2.material.actor'])
            include_actor = _needs_card_design(context, journal.feedback())
            if include_actor:
                context["actor_system_template"] = layers["scene.v2.material.actor"]
            if journal.feedback():
                context["delivery_feedback"] = journal.feedback()
            if getattr(coordinator, "creator_prompt_layout", "") in {STABLE_PREFIX_LAYOUT, LEGACY_STABLE_PREFIX_LAYOUT}:
                prompt = stable_creator_prompt(layers, mode, context, include_actor=include_actor,
                                              layout=coordinator.creator_prompt_layout)
            else:
                prompt = _creator_guidance(layers, mode, include_actor=include_actor) + "\n\n本次创作资料：\n" + json.dumps(context, ensure_ascii=False)
            answer = replay["previous_answer"] if replay else self._preserved_natural_answer(transaction_id, "creator", prompt, lambda:
                self._run_v2_creator(prompt, transaction_id, layers, briefing, workspace, coordinator,
                    purpose="revision" if mode == "revise" else "creator"))
            replay = None
            answer = recover_saved_creator_delivery(answer,prompt,self._data_root,journal.root)
            try:
                try:
                    payload = processor.process(answer, kind="creator", context=context)
                except NaturalSourceClarificationError as error:
                    payload = self._source_field_repair(transaction_id,processor,answer,"creator",context,error,
                        lambda task:self._run_v2_creator(task,transaction_id,layers,briefing,workspace,coordinator,
                            purpose="selection",tool_policy="none",metadata_repair=True),material_sources=coordinator._candidate_lookup())
                payload = _repair_final_selection(payload, prompt, memory, coordinator,
                    invoke=lambda current: self._natural_selection_payload(transaction_id,current,processor,
                        context,workspace,lambda: self._run_v2_creator(
                            current, transaction_id, layers, briefing, workspace, coordinator,
                            purpose="selection",tool_policy="materials")))
                payload, requests = self._accept_creator_with_repairs(
                    payload, brief, coordinator, memory, transaction_id, processor,
                    answer, context, prompt, layers, briefing, workspace)
                next_memory = deepcopy(memory)
                annotate_material_usage(payload,coordinator.root/"materials")
                next_memory.record_creator(payload, brief, prompt=prompt, request_limit_chars=160_000)
                if payload.get("editor_focus") and payload.get("prose"):
                    from .natural_transport_store import save_json
                    save_json(self._cache_path(transaction_id,"editor-focus/"+sha256(payload["prose"].encode()).hexdigest()+".json"),
                        {"source_sha256":sha256(answer.encode()).hexdigest(),"focus":payload["editor_focus"]})
                memory = next_memory
            except ValueError as error:
                if isinstance(error, NaturalExtractionError):
                    journal.reject(prompt, error, technical_only=True, answer=answer)
                    raise
                journal.reject(prompt, error, answer=answer)
                raise
            memory.save(memory_path)
            journal.accept()
            if not requests:
                save_consistency_record(coordinator.root, payload)
                save_material_usage_audit(payload['prose'], coordinator.root / 'materials',
                    memory.current_decisions(), self._cache_path(transaction_id, 'material-usage'))
                return creative_result_from_payload(payload)
        raise RuntimeError("natural scene creator exceeded its material turns")

    def _accept_creator_with_repairs(self, payload, brief, coordinator, memory, transaction_id,
                                     processor, answer, context, prompt, layers, briefing, workspace):
        seen = set()
        for attempt in range(3):
            try:
                return payload, self._accept_natural_turn(payload, brief, coordinator, memory)
            except NaturalSourceClarificationError as error:
                if attempt == 2:
                    raise
                signature = (str(error), error.fields, sha256(json.dumps(payload, ensure_ascii=False,
                    sort_keys=True).encode()).hexdigest())
                if signature in seen:
                    raise
                seen.add(signature)
                error.payload = deepcopy(payload)
                payload = self._source_field_repair(transaction_id, processor, answer, "creator", context, error,
                    lambda task: self._run_v2_creator(task, transaction_id, layers, briefing, workspace, coordinator,
                        purpose="selection", tool_policy="none", metadata_repair=True),
                    material_sources=coordinator._candidate_lookup())
                payload = _repair_final_selection(payload, prompt, memory, coordinator,
                    invoke=lambda current: self._natural_selection_payload(transaction_id, current, processor,
                        context, workspace, lambda: self._run_v2_creator(current, transaction_id,
                            layers, briefing, workspace, coordinator, purpose="selection", tool_policy="materials")))

    def _natural_selection_payload(self, transaction_id, prompt, processor, context, workspace, invoke):
        answer=self._preserved_natural_answer(transaction_id,'creator-selection',prompt,invoke)
        journal=NaturalTurnStore(self._cache_path(transaction_id,'v2/literary-originals'),'creator-selection')
        source=journal.referenced_scratch_source(prompt,answer,workspace.read_scratch)
        return processor.process(source,kind='creator',context={**context,'selection_only':True})

    def _recover_pending_material_plan(self, memory, coordinator, transaction_id, layers, briefing, workspace, processor):
        if not memory.pending_request or coordinator.plan_context() is not None:
            return
        invitations = [{key: row.get(key, '') for key in ('kind', 'target', 'purpose', 'scene_moment')}
                       for row in memory.pending_request.get('material_requests') or []]
        prompt = ('已保存本轮委托，当前补充它们的取材计划。根据文学任务选择至少一类本场必用伙伴，'
                  '以自然文字写明所选标识和文学理由：actor、environment、character-description、event-narration、scene-description。'
                  '\n创作意图：\n' + json.dumps(memory.intent.to_dict() if memory.intent else {}, ensure_ascii=False)
                  + '\n已保存委托：\n' + json.dumps(invitations, ensure_ascii=False))
        answer = self._preserved_natural_answer(transaction_id, 'creator-material-plan', prompt,
            lambda: self._run_v2_creator(prompt, transaction_id, layers, briefing, workspace, coordinator,
                purpose="selection",tool_policy="none"))
        payload = processor.process(answer, kind='material-plan', context={'invitations': invitations})
        coordinator.save_plan(parse_creator_material_plan(payload))

    def _accept_natural_turn(self, payload, brief, coordinator, memory):
        scope = coordinator.material_scope
        requests = parse_scene_material_requests_v4(payload, scope.get("actor_targets", list(brief.participants)),
            free_character_subjects=scope.get("version") == "work-v1")
        if requests:
            if str(payload.get("prose") or "").strip():
                raise ValueError("creator offered prose while requesting new materials")
            self._require_actor_cards(requests, coordinator)
            _validate_request_archive_choices(requests, coordinator)
            record_source_needs(coordinator, requests, payload.get("source_provenance"))
            if payload.get("material_plan") and coordinator.plan_context() is None:
                coordinator.save_plan(parse_creator_material_plan(payload))
            return requests
        if not str(payload.get("prose") or "").strip():
            raise ValueError("creator response needs actionable invitations or completed prose")
        _ensure_final_material_plan(payload, coordinator)
        coordinator.assert_ready_for_prose()
        if not str(payload.get("decision_summary") or "").strip():
            raise NaturalSourceClarificationError("completed creator delivery needs its decision_summary",
                fields=("/decision_summary",),payload=deepcopy(payload))
        if getattr(coordinator, 'integrity_contract', None):
            validate_current_material_choices(payload, coordinator._candidate_lookup())
        entries = json.loads((coordinator.root / "materials" / "index.json").read_text(encoding="utf-8"))
        issue = material_selection_error(payload, [item["candidate_id"] for item in entries["entries"]],
                                         memory.material_decisions)
        if issue:
            raise ValueError(issue)
        return ()

    def _require_actor_cards(self, requests, coordinator):
        from ..application.actor_card_store import ActorCardStore
        frozen = {row['card']['target'] for row in coordinator.creator_card_context()['frozen_scene_cards']}
        original_requests = requests
        requests = [request for request in requests if request.kind == 'actor'
                    and request.character_card is None and request.target not in frozen]
        if not requests:
            return
        schema = actor_card_schema_for_template(coordinator.layers['scene.v2.material.actor'])
        def ready(target):
            stored = ActorCardStore.read(self._project_root, target)
            return stored is not None and stored['card']['schema'] == schema
        missing = [request.target for request in requests if request.kind == "actor" and request.character_card is None
                   and request.target not in frozen and not ready(request.target)]
        if missing:
            raise NaturalSourceClarificationError("为这些角色补充人格卡后即可发起邀请：" + "、".join(missing)
                + "。按当前完整角色卡模板写出人物性情、声音与处境反应。",
                fields=tuple(f"/material_requests/{index}/character_card" for index,request in enumerate(original_requests)
                             if request.target in missing))

    def _review_natural(self, transaction_id, layers, briefing, brief, result, verification, index):
        memory_path = self._cache_path(transaction_id, "scene_creator_memory.json")
        memory = SceneCreatorMemoryV1.load(memory_path,
            brief.scene_id, request_limit_chars=160_000)
        context = {"briefing": briefing_for_natural_context(briefing), "prose": result.prose,
                   "scene_delta": result.scene_delta.to_dict(), "verification": verification.to_dict(),
                   "material_index": index, "creator_memory": memory.to_dict(),
                   "review_continuity": prior_review_context(review_continuity(memory_path.parent, result.prose))}
        context = integrity_review_context(context, self._v2_prompt_snapshot(transaction_id), memory_path.parent / 'v2', result.prose)
        journal = NaturalTurnStore(self._cache_path(transaction_id, "v2/literary-originals"), "review")
        if journal.feedback():
            context["delivery_feedback"] = journal.feedback()
        system, context = review_layout(layers, briefing, context, self._v2_prompt_snapshot(transaction_id))
        prompt = layers["scene.v2.review.protocol"] + "\n\n本次审读资料：\n" + json.dumps(context, ensure_ascii=False)
        context_binding=review_context_digest(system,layers['scene.v2.review.protocol'],context)
        replay=saved_review_answer(journal,system,layers['scene.v2.review.protocol'],context)
        answer = replay if replay is not None else self._preserved_natural_answer(transaction_id, "review", system + prompt, lambda:
            self._run_natural_text(system, prompt, transaction_id, "reviewer"))
        try:
            processor = self._natural_processor(transaction_id, layers)
            try:
                extracted = processor.process(answer, kind="review", context=context)
            except NaturalSourceClarificationError as error:
                purpose = "evidence-repair" if all(path.endswith("/evidence") for path in error.fields) else "review"
                extracted = self._source_field_repair(transaction_id,processor,answer,"review",context,error,
                    lambda task:self._run_natural_text(system,task,transaction_id,"reviewer",purpose=purpose))
            except NaturalExtractionError as error:
                if not _complete_review_evidence_failure(error):
                    raise
                clarification=NaturalSourceClarificationError(str(error),fields=error.fields,payload=error.payload)
                extracted=self._source_field_repair(transaction_id,processor,answer,'review',context,clarification,
                    lambda task:self._run_natural_text(system,task,transaction_id,'reviewer',purpose='evidence-repair'))
            review_payload = formal_review_payload(extracted)
            review = review_result_from_payload(review_payload)
        except ValueError as error:
            if isinstance(error, NaturalExtractionError):
                journal.reject(system+prompt,error,technical_only=True,answer=answer,context_digest=context_binding)
                raise
            journal.reject(system + prompt, error,answer=answer,context_digest=context_binding)
            raise
        journal.accept()
        save_review_integrity(memory_path.parent / 'v2', result.prose, extracted)
        if extracted.get("editor_focus"):
            from .natural_transport_store import save_json
            save_json(self._cache_path(transaction_id,"editor-focus/"+sha256(result.prose.encode()).hexdigest()+".json"),
                {"source_sha256":sha256(answer.encode()).hexdigest(),"focus":extracted["editor_focus"]})
        context_digest = sha256((system+json.dumps({key:value for key,value in context.items()
            if key != "delivery_feedback"},ensure_ascii=False,sort_keys=True)).encode()).hexdigest()
        path = self._cache_path(transaction_id,"review_original_v3_"+sha256(result.prose.encode()).hexdigest()+"_"+context_digest[:24]+'.md')
        review_source = answer
        repair = extracted.get("field_repair_provenance")
        if repair:
            reply_path = processor.root/"natural-answers"/repair["reply_sha256"]/"original.source.txt"
            with reply_path.open(encoding="utf-8",newline="") as handle:
                review_source += "\n\n【原审读者指定字段补交】\n"+handle.read()
        if not path.exists():
            path.write_text(review_source,encoding='utf-8')
        record_review(memory_path.parent, result.prose, extracted, review_payload, path.name,context_digest=context_digest)
        return review

    def _preserved_natural_answer(self, transaction_id, phase, prompt, invoke, *, store_root="v2/literary-originals"):
        journal = NaturalTurnStore(self._cache_path(transaction_id, store_root), phase)
        answer, cached = journal.answer(prompt, invoke)
        if cached:
            self._cache_hits += 1
        return answer

    def _cached_creator_payload(self, transaction_id: str, prompt: str) -> dict[str, Any]:
        return _answer_payload(self._preserved_natural_answer(
            transaction_id, "creator", prompt,
            lambda: self._run(prompt, role="worker", transaction_id=transaction_id),
            store_root="creator-answers"))


def _repair_final_selection(payload, prompt, memory, coordinator, *, invoke):
    if (payload.get("material_requests") or not str(payload.get("prose") or "").strip()
            or not str(payload.get("decision_summary") or "").strip()):
        return payload
    coordinator.assert_ready_for_prose()
    index = json.loads((coordinator.root / "materials" / "index.json").read_text(encoding="utf-8"))
    corrected, _ = repair_material_choice(payload, prompt, phase="material-ready",
        candidate_ids=[item["candidate_id"] for item in index["entries"]],
        prior_decisions=memory.material_decisions, natural=True, invoke=invoke)
    return corrected


def _ensure_final_material_plan(payload, coordinator):
    if not getattr(coordinator, 'integrity_contract', None) or coordinator.plan_context() is not None:
        return
    try:
        coordinator.save_plan(parse_creator_material_plan(payload))
    except ValueError as error:
        raise NaturalSourceClarificationError(str(error)+'；原主创补交本场取材计划。',
            fields=('/material_plan',), payload=deepcopy(payload)) from error


def _creator_context(memory, coordinator, briefing, revision_context) -> dict[str, Any]:
    library = SceneMaterialLibrary(coordinator.root / 'materials')
    candidate_ids = list(library.candidate_ids())
    remembered = {"创作意图": memory.intent.to_dict() if memory.intent else None,
                  "素材目录": "见 material_index", "取舍札记": memory.current_decisions(),
                  "阶段": memory.phase}
    if memory.deferred_editor_focus:
        remembered['正文交付时再定位的编辑问题']=memory.deferred_editor_focus
    if memory.pending_body_source:
        remembered['待取材后审定的正文候选']=memory.pending_body_source
    cards = coordinator.creator_card_context()
    targets = {*(briefing['scene_brief'].get('participants') or []),
               *(row['card']['target'] for row in cards['frozen_scene_cards'])}
    cards['work_cards'] = [row for row in cards['work_cards'] if row.get('target', (row.get('card') or {}).get('target')) in targets]
    cards['previous_work_cards'] = [row for row in cards.get('previous_work_cards', [])
                                    if row['card']['target'] in targets]
    from .creator_context_projection import deduplicate_cards
    cards = deduplicate_cards(cards)
    return {"briefing": briefing_for_natural_context(briefing), "creator_memory": remembered,
            **creator_integrity_context(coordinator, revision_context),
            "available_material_ids": candidate_ids,
            "material_need_contract": material_need_version(coordinator),
            "material_index": library.index_prompt(),
            "frozen_material_plan": coordinator.plan_context(),
            **({"eligible_actor_refs": coordinator.material_scope["actor_refs"]} if coordinator.material_scope.get("actor_refs") else {}),
            "eligible_actors": coordinator.material_scope.get("actor_targets", briefing["scene_brief"].get("participants", [])),
            "free_character_subjects": coordinator.material_scope.get("version") == "work-v1",
            "revision_context": revision_context,
            "delivery_stage": "准备邀请与创作札记" if not candidate_ids else "评议已返回素材，继续邀请或交付正文",
            **({'actor_card_context': cards} if targets else {})}


def _needs_card_design(context, feedback):
    cards = context.get('actor_card_context') or {}
    known = {row['card']['target'] for row in cards.get('frozen_scene_cards') or []}
    known.update(row.get('target', (row.get('card') or {}).get('target')) for row in cards.get('work_cards') or [])
    requested = set(context['briefing']['scene_brief'].get('participants') or [])
    return bool(requested - known or feedback and '人格卡' in feedback.get('issue', ''))


def _creator_guidance(layers, mode, *, include_actor=True):
    return "\n\n".join(layers[key] for key in (
        "scene.v2.creator.bootstrap", f"scene.v2.creator.{mode}",
        "scene.v2.creator.delegation", "scene.v2.creator.actor-card",
        "scene.v2.creator.archive", "scene.v2.creator.sandbox", "scene.v2.creator.selection")
        if include_actor or key != "scene.v2.creator.actor-card")


def _validate_transport_delta(payload, brief):
    if not payload.get('prose') or not payload.get('decision_summary'):
        return
    policy = derive_scene_policy(mode=SceneExecutionMode.STANDARD, risk=brief.risk)
    report = verify_creative_result(brief, creative_result_from_payload(payload), policy, known_refs=known_scene_refs(brief))
    invalid = [issue.message for issue in report.issues if issue.code=='unknown-delta-target']
    if invalid:
        raise NaturalSourceClarificationError('；'.join(invalid) + '。未来交接写入 scene_delta.next_handoff；实际改变采用本场已有目标：'
            + ', '.join(sorted(known_scene_refs(brief))),fields=("/scene_delta",),payload=deepcopy(payload))


def _validate_creator_context(payload,brief,coordinator):
    _validate_transport_delta(payload,brief)
    validate_source_needs(payload,coordinator)
    _validate_transport_intent(payload)
    _validate_transport_material_plan(payload)


def _validate_transport_material_plan(payload):
    if not payload.get('material_requests') or payload.get('material_plan') is None:
        return
    try:
        parse_creator_material_plan(payload)
    except ValueError as error:
        raise NaturalSourceClarificationError(str(error) +
            '。仅补交 material_plan，原主创选择本场至少一类必用伙伴并写文学理由；其余字段冻结。',
            fields=('/material_plan',), payload=deepcopy(payload)) from error


def _validate_request_archive_choices(requests, coordinator):
    for index, request in enumerate(requests):
        try:
            coordinator.validate_request_archives([request])
        except ValueError as error:
            raise NaturalSourceClarificationError(str(error) +
                '。仅更正这条委托的档案挂载、工作语境和对应需求依据。'
                '作品档案使用实际相对路径；沙盒笔记不能冒充作品档案，'
                '需要其内容时由原主创明确交付到 working_context；其余委托与原文冻结。',
                fields=tuple(f'/material_requests/{index}/{field}' for field in
                             ('archive_attachments','working_context','need_evidence'))) from error


def _validate_transport_intent(payload):
    proposed = payload.get('creative_intent')
    if proposed is None or isinstance(proposed, dict) and proposed and all(
            key in {'reader_experience','reader_knows','reader_misreads','withheld'} and value == ''
            for key, value in proposed.items()):
        return  # Existing memory retains an explicitly empty compatibility update.
    try:
        CreativeIntentV1.from_payload(proposed)
    except ValueError as error:
        raise NaturalSourceClarificationError(str(error) +
            '。仅补交 creative_intent：reader_experience 至多 600 字符，其余三项各至多 400 字符；'
            '按原意区分体验、已知、误读与保留信息，其他字段和完整原文冻结。',
            fields=('/creative_intent',), payload=deepcopy(payload)) from error


def _complete_review_evidence_failure(error):
    import re
    payload=error.payload
    return bool(isinstance(payload,dict) and payload.get('decision') in {'pass','revise','escalate'}
        and payload.get('summary') and error.fields and all(re.fullmatch(
            r'/(?:strengths|major_issues|optional_explorations|issue_progress)/\d+/evidence',path)
            for path in error.fields))
