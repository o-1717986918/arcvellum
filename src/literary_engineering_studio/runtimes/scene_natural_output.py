"""Natural answers are archived before a separate, tool-free transport extraction."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping
from .natural_field_repair import apply_field_patch, field_repair_task
from .natural_authored_records import authored_record, replay_authored_patch
from .evidence_patch_source import resolve_evidence_patches
from .material_need import require_source_needs

from .commission_source_format import restore_commission_source, restore_tone_source, tone_text_matches_source
from .natural_card_source import restore_labelled_card_sections
from .archive_partition_transport import normalize_archive_partitions, require_source_partition_choice
from .creator_delivery_labels import resolve_creator_targets, recover_style_preset_id, recover_style_reference_ids, recover_style_list_format
from .event_material_provenance import event_fields, recover_event_source_status
from .scene_review_validation import validate_review_extraction
from .natural_selection_pending import pending_selection, archive_notes_before_materials, validate_choice_ids, revalidate_pending_selection
from .handoff_transport import restore_handoff_targets
from .planning_reading import normalize_planning_weights
from .actor_card_transport import actor_card_contract, card_section_schema
from .natural_transport_pipeline import NaturalTransportPipeline
from .natural_transport_repair import NaturalExtractionError, NaturalSourceClarificationError
from .natural_local_delivery import explicit_creator_phase
from .natural_delivery_phase import project_creator_phase
from .creator_body_boundary import detach_creator_notes
from .natural_editor_focus import recover_creator_editor_focus
from .scene_integrity import validate_integrity_delivery
from literary_engineering_studio_engine.public.literary import (
    ACTOR_CARD_SECTIONS, ACTOR_CARD_SCHEMA, LEGACY_ACTOR_CARD_SCHEMA,
    parse_scene_material_requests_v4, parse_creator_material_plan,
)

NATURAL_RESPONSE_MODE = "natural-v1"
STYLE_TOKEN = "{{STYLE_DIRECTION}}"
from .natural_output_contracts import CONTRACTS


def render_style(template: str, direction: str) -> str:
    if template.count(STYLE_TOKEN) != 1:
        raise ValueError("creative identity needs exactly one style field")
    return template.replace(STYLE_TOKEN, direction.strip() or "由本次作品与委托的语感展开。")


def creator_style(briefing: Mapping[str, Any]) -> str:
    style = briefing.get("style") or {}
    if (style.get("assembled") or {}).get("content"):
        return style["assembled"]["content"]
    measured = style.get("stylometry") or {}
    keys = ("author_directive",) if measured.get("combine") == "replace" else ("author_directive", "mounted")
    return "\n\n".join(str(item.get("content") or "").strip()
                        for key in (*keys, "preset_direction", "selected_strategy", "references", "stylometry")
                        if isinstance((item := style.get(key)), dict) and item.get("content"))


def briefing_for_natural_context(briefing: Mapping[str, Any]) -> dict[str, Any]:
    """Keep style provenance in request context; its full text travels in system_prompt."""
    result = dict(briefing)
    style = briefing.get("style")
    if not isinstance(style, Mapping):
        return result
    projected: dict[str, Any] = {}
    for key, value in style.items():
        if not isinstance(value, Mapping):
            projected[key] = value
            continue
        item = dict(value)
        if str(item.get("content") or "").strip():
            item.pop("content", None)
            item["delivered_via"] = "system_prompt"
        projected[key] = item
    result["style"] = projected
    return result


class NaturalOutputProcessor:
    def __init__(self, root: Path, system_prompt: str, invoke: Callable[[str, str], str], validate_payload=None):
        self.root, self.system_prompt, self.invoke = root, system_prompt, invoke
        self.validate_payload = validate_payload

    def _prepare(self, answer, payload, kind, context):
        payload = _transport_payload(payload, kind)
        if kind == 'creator' and context.get('creation_integrity_contract'):
            validate_integrity_delivery(answer, payload, context)
        payload = revalidate_pending_selection(answer, payload, kind, context, _verbatim)
        try:
            payload = _prepare_transport_payload(answer, payload, kind, context)
        except NaturalSourceClarificationError as error:
            error.payload = payload
            raise
        except ValueError as error:
            payload = pending_selection(payload, kind, context, error)
            payload = _prepare_transport_payload(answer, payload, kind, context)
        if self.validate_payload:
            try:
                self.validate_payload(payload)
            except NaturalSourceClarificationError as error:
                error.payload = payload
                raise
        if kind == 'creator':
            validate_integrity_delivery(answer, payload, context)
            require_source_needs(answer, payload, context)
            payload['source_provenance'] = _commission_provenance(answer, payload, context)
        return payload

    def process(self, answer: str, *, kind: str, context: Mapping[str, Any], reuse_only=False) -> dict[str, Any]:
        try:
            return NaturalTransportPipeline(self.root, self.system_prompt, self.invoke, self._prepare, CONTRACTS).process(
                answer, kind, context, reuse_only=reuse_only)
        except (NaturalSourceClarificationError,NaturalExtractionError):
            raise
        except ValueError as error:
            raise NaturalExtractionError(str(error)) from error

    def process_field_repair(self, source, reply, *, kind, context, payload, fields):
        combined=source+'\n\n【原作者指定字段补交】\n'+reply
        def prepare(_answer,patch,_kind,_context):
            patch=replay_authored_patch(patch,source,reply,fields)
            patch=resolve_evidence_patches(patch,str(payload.get('prose') or context.get('prose') or ''),fields)
            merged=apply_field_patch(payload,patch,fields)
            try:
                value=self._prepare(combined,merged,kind,context)
            except NaturalSourceClarificationError as error:
                error.source_text=combined
                raise
            except NaturalExtractionError as error:
                if not error.fields:
                    raise
                next_error = NaturalSourceClarificationError(str(error), fields=error.fields, payload=merged)
                next_error.source_text = combined
                raise next_error from error
            value['field_repair_provenance']={'parent_source_sha256':sha256(source.encode()).hexdigest(),
                'reply_sha256':sha256(reply.encode()).hexdigest(),'allowed_fields':list(fields)}
            return value
        contract=field_repair_task(source,payload,fields,context)['response_contract']
        return NaturalTransportPipeline(self.root,self.system_prompt,self.invoke,prepare,
            {'field-repair':contract}).process(reply,'field-repair',
                {**context,'allowed_paths':list(fields),'parent_source_sha256':sha256(source.encode()).hexdigest(),
                 'frozen_fields_sha256':sha256(json.dumps({key:value for key,value in payload.items()
                     if not key.startswith('__')},ensure_ascii=False,sort_keys=True).encode()).hexdigest()})


def _prepare_transport_payload(answer, payload, kind, context):
    payload = _transport_payload(payload, kind)
    if kind.startswith('planning-'):
        payload = normalize_planning_weights(payload)
    if kind == "card" and payload.get("schema") in {ACTOR_CARD_SCHEMA, LEGACY_ACTOR_CARD_SCHEMA}:
        payload = {"card": payload}
    if kind == 'card':
        payload = restore_labelled_card_sections(answer, payload)
    if kind == "creator":
        payload = _prepare_creator_transport(answer, payload, context)
    if kind == "material" and context.get("role") == "event-narrator":
        payload = recover_event_source_status(answer, payload)
    if kind == 'tone':
        payload = restore_tone_source(answer,payload,context.get('prose'))
    validate_extracted_text(answer, payload, kind, context)
    if kind == "creator" and "briefing" in context:
        _validate_creator_material_requests(answer, payload, context)
    return payload


def _validate_creator_material_requests(answer, payload, context):
    participants = context.get("eligible_actors", (context["briefing"].get("scene_brief") or {}).get("participants") or [])
    try:
        parse_scene_material_requests_v4(payload, list(participants), free_character_subjects=context.get("free_character_subjects", False))
    except ValueError as error:
        if not authored_record(answer, 'creator_record') or not payload.get('material_requests'):
            raise
        fields = ['/material_requests']
        if payload.get('material_plan') is not None:
            try:
                parse_creator_material_plan(payload)
            except ValueError:
                fields.append('/material_plan')
        if isinstance(payload.get('creative_intent'), str) and payload['creative_intent'].strip():
            fields.append('/creative_intent')
        raise NaturalSourceClarificationError(
            str(error) + '。原主创仅补交授权的结构记录，保留邀约的原意和原文。',
            fields=tuple(fields), payload=payload) from error


def _prepare_creator_transport(answer, payload, context):
    payload = detach_creator_notes(payload)
    payload = project_creator_phase(answer, payload)
    if payload.get('pending_body_source') and not payload.get('material_requests'):
        raise ValueError('pending creator invitations require material_requests before this saved candidate is finalized')
    if explicit_creator_phase(answer) == 'prepare':
        payload['prose'] = ''
    for request in payload.get("material_requests") or []:
        card = request.get("character_card")
        if isinstance(card, dict) and not card.get("sections"):
            request["character_card"] = None
    payload = restore_labelled_card_sections(answer, payload)
    payload = restore_commission_source(answer, payload)
    payload = archive_notes_before_materials(payload, answer, context)
    payload = resolve_creator_targets(payload, context)
    payload = normalize_archive_partitions(payload)
    require_source_partition_choice(answer, payload)
    payload = _resolve_delta_aliases(payload, context)
    return restore_handoff_targets(payload)



def _resolve_delta_aliases(payload, context):
    aliases = context.get("eligible_actor_refs") or {}
    for key, changes in (payload.get("scene_delta") or {}).items():
        if key == "next_handoff" or not isinstance(changes, list):
            continue
        for change in changes:
            if isinstance(change, dict) and change.get("target_ref") in aliases:
                original = change["target_ref"]
                change["target_ref"] = aliases[original]
                payload.setdefault("delta_alias_resolution", []).append({"original": original, "reference": change["target_ref"]})
    return payload

def _transport_payload(payload, kind):
    if payload.get("operation") == kind and isinstance(payload.get("task_contract"), dict):
        delivered = payload["task_contract"]
        if not any(key in payload for key in CONTRACTS[kind]):
            return delivered
    return payload


def validate_extracted_text(answer: str, payload: Mapping[str, Any], kind: str,
                            context: Mapping[str, Any] | None = None) -> None:
    context = context or {}
    recover_creator_editor_focus(answer,payload,kind,context)
    _validate_editor_focus(answer,payload,context,kind)
    if kind == "card":
        _validate_card_text(answer, payload.get("card") or {})
    if kind == "creator":
        _validate_creator_delivery(answer, payload, context)
    if kind == "material":
        _validate_material_delivery(answer, payload, context)
    if kind == "review":
        if payload.get('decision') not in {'pass','revise','escalate'} or not isinstance(payload.get('summary'),str):
            raise ValueError('review extraction needs its original decision and summary')
        validate_review_extraction(payload, context, answer)
    if kind == "tone":
        _validate_tone_text(answer, payload)
    if kind == "style-choice":
        _validate_style_choice(answer, payload, context)
    if kind == 'material-plan':
        _validate_required_material_plan(answer, payload)
    if kind.startswith('planning-'):
        _validate_planning_chapter(payload, context)
        _validate_planning_participants(payload, context)


def _validate_required_material_plan(answer, payload):
    plan = parse_creator_material_plan(payload)
    _verbatim(answer, plan.reason, 'material plan reason')
    for ident in plan.required_kinds:
        _verbatim(answer, ident, 'material plan kind')


def _validate_planning_participants(payload, context):
    if 'registered_actor_names' not in context:
        return
    chapters = [payload['chapter']] if isinstance(payload.get('chapter'), dict) else payload.get('chapters') or []
    allowed = set(context['registered_actor_names'])
    for chapter in chapters:
        for scene in chapter.get('scenes') or []:
            unknown = set(scene.get('participants') or []) - allowed
            if unknown:
                raise ValueError('planning participant metadata needs registered names: ' + ', '.join(sorted(unknown)))


def _validate_planning_chapter(payload, context):
    if 'chapter_id' not in context or 'future_scene_count' not in context:
        return
    chapter = payload.get('chapter')
    if (not isinstance(chapter, dict) or chapter.get('chapter_id') != context['chapter_id']
            or len(chapter.get('scenes') or []) != context['future_scene_count']):
        raise ValueError('planning chapter must retain requested identity and every source unit')




def _validate_creator_delivery(answer, payload, context):
    if explicit_creator_phase(answer) == 'prepare' and not payload.get('material_requests'):
        raise ValueError('creator preparation needs its pending source invitations')
    if not payload.get("prose") and not payload.get("material_requests") and not (context.get("selection_only") and payload.get("material_decisions")):
        raise ValueError("creator extraction needs its source invitations or completed body")
    if payload.get("prose"):
        _verbatim(answer, payload["prose"], "prose")
        if payload.get("material_requests"):
            raise ValueError("creator transport mixes completed prose and pending material requests; select the source delivery phase")
    _validate_requested_cards(answer, payload, context)
    _commission_provenance(answer, payload, context)

def _validate_material_delivery(answer, payload, context):
    _validate_material_text(answer, payload)
    if context.get("role") == "event-narrator":
        for candidate in payload["candidates"]:
            event_fields(candidate)

def _validate_style_choice(answer, payload, context):
    if not recover_style_preset_id(answer, payload, context):
        raise ValueError("creator selected an unavailable style preset")
    _verbatim(answer, payload["preset_id"], "preset ID")
    recover_style_reference_ids(answer,payload,context)
    recover_style_list_format(answer,payload)
    references = payload.get("reference_ids")
    if not isinstance(references, list) or len(set(references)) != len(references):
        raise ValueError("style selection needs unique reference IDs")
    for ident in references:
        if ident not in context.get("reference_ids", []):
            raise ValueError("creator selected an unavailable reference")
        _verbatim(answer, ident, "reference ID")
    for key in ("literary_mode", "reason"):
        _verbatim(answer, payload.get(key), key)


def _commission_provenance(answer: str, payload: Mapping[str, Any], context=None) -> dict[str, Any]:
    rows,failed = [],[]
    for index, request in enumerate(payload.get("material_requests") or []):
        if not isinstance(request, dict):
            raise ValueError("invalid creator invitation extraction")
        spans = {}
        for key in ("author_prompt", "working_context", "style_direction"):
            if key not in request or (key in {"style_direction", "working_context"} and not request[key]):
                continue
            value = request[key]
            if not _commission_literal(answer,value,key):
                failed.append(f'/material_requests/{index}/{key}')
                continue
            literal = value if value in answer else json.dumps(value, ensure_ascii=False)[1:-1]
            start = answer.index(literal)
            spans[key] = {"start": start, "end": start + len(literal),
                          "encoding": "plain" if literal == value else "json-string"}
        _verify_attachment_ids(answer,request)
        rows.append({"request_index": index, "spans": spans})
    if failed:
        raise NaturalExtractionError('extraction changed invitation source fields; original natural text is preserved',fields=failed)
    validate_choice_ids(answer, payload, _verbatim, (context or {}).get('available_material_ids'))
    return {"source_sha256": sha256(answer.encode("utf-8")).hexdigest(), "requests": rows}


def _commission_literal(answer,value,key):
    try:
        _verbatim(answer,value,key)
        return True
    except ValueError:
        return False


def _verify_attachment_ids(answer,request):
    for attachment in request.get('material_attachments') or []:
        if isinstance(attachment,dict):
            _verbatim(answer,attachment.get('candidate_id'),'selected material candidate ID')


def _validate_tone_text(answer: str, payload: Mapping[str, Any]) -> None:
    edits = payload.get("edits")
    if not isinstance(edits, list):
        raise ValueError("tone extraction needs local edits")
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("tone edit extraction is invalid")
        if not tone_text_matches_source(answer, edit.get('before')):
            _verbatim(answer, edit.get("before"), "tone original fragment")
        if edit.get("after"):
            if not tone_text_matches_source(answer, edit['after']):
                _verbatim(answer, edit["after"], "tone replacement")


def _validate_card_text(answer: str, card: Mapping[str, Any]) -> None:
    card_section_schema(card)
    sections = card.get("sections")
    for value in sections.values():
        _verbatim(answer, value, "card section")


def _validate_material_text(answer: str, payload: Mapping[str, Any]) -> None:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("material extraction needs candidates")
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("invalid material extraction")
        _verbatim(answer, candidate.get("text"), "candidate text")
        for key in ("spoken", "first_person_action", "private_impulse"):
            if candidate.get(key):
                _verbatim(answer, candidate[key], key)
        for key in ('spoken_fragments', 'action_fragments', 'private_fragments'):
            for value in candidate.get(key) or []:
                _verbatim(answer, value, key)


def _validate_requested_cards(answer: str, payload: Mapping[str, Any], context: Mapping[str, Any]) -> None:
    cards = context.get("actor_card_context") or {}
    frozen = [*(cards.get("frozen_scene_cards") or []), *(cards.get("work_cards") or [])]
    for request in payload.get("material_requests") or []:
        card = request.get("character_card")
        if not card or any(card == item.get("card") for item in frozen):
            continue
        if (context.get('actor_system_template') or context.get('actor_card_schema')) and card_section_schema(card) != actor_card_contract(context)['schema']:
            raise ValueError('new actor card must use the current frozen template version')
        _validate_card_text(answer, card)


def _verbatim(answer: str, value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or (value not in answer and json.dumps(value, ensure_ascii=False)[1:-1] not in answer):
        raise ValueError(f"extraction changed {label}; original natural text is preserved")



def _validate_editor_focus(answer,payload,context,kind):
    if _defer_preparation_editor_focus(answer,payload,kind):
        return
    for focus in payload.get("editor_focus") or []:
        if not isinstance(focus,dict):
            raise ValueError("editor_focus must contain explicit source questions")
        _verbatim(answer,focus.get("issue"),"editor focus")
        if focus.get("operation"):
            _verbatim(answer,focus["operation"],"editor focus operation")
        excerpt = focus.get("excerpt")
        prose = payload.get("prose") if kind == "creator" else context.get("prose")
        if not isinstance(excerpt,str) or not excerpt.strip() or excerpt not in str(prose or ""):
            raise ValueError("editor_focus must select current prose exactly")


def _defer_preparation_editor_focus(answer,payload,kind):
    if kind=='creator' and payload.get('material_requests') and not payload.get('prose'):
        from copy import deepcopy
        for focus in payload.get('editor_focus') or []:
            if not isinstance(focus,dict):raise ValueError('editor_focus must contain explicit source questions')
            _verbatim(answer,focus.get('issue'),'editor focus')
        if payload.get('editor_focus'):
            payload['deferred_editor_focus']=deepcopy(payload['editor_focus'])
            payload['editor_focus']=[]
        return True
    return False
