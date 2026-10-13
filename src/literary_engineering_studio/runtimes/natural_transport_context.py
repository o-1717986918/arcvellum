"""Only interpretation inputs participate in technical extraction or its cache key."""
from copy import deepcopy
from hashlib import sha256
import json
import re
from .actor_card_transport import actor_card_contract

REFERENCE_MARKER = '[NATURAL_SOURCE_REFERENCES_V1]'
_FIELDS = {'review': ('prose', 'review_continuity'), 'tone': ('prose',),
           'style-choice': ('preset_ids', 'reference_ids')}


def extraction_context(kind, context):
    common = ('target', 'eligible_actors', 'eligible_actor_refs', 'actor_card_schema',
              'free_character_subjects', 'selection_only', 'registered_actor_names', 'creation_integrity_contract')
    result = {key: deepcopy(context[key]) for key in common if key in context}
    if context.get('actor_system_template'):
        result['actor_card_schema'] = actor_card_contract(context)['schema']
    if kind in {'creator','field-repair'}:
        _creator_context(result, context)
    if kind=='field-repair':
        result['allowed_paths']=deepcopy(context.get('allowed_paths',[]))
        result['parent_source_sha256']=context.get('parent_source_sha256','')
        result['frozen_fields_sha256']=context.get('frozen_fields_sha256','')
        result['prose']=context.get('prose','')
        result['review_continuity']=deepcopy(context.get('review_continuity',{}))
    if kind == 'material':
        _material_context(result, context)
    result.update({key: deepcopy(context[key]) for key in _FIELDS.get(kind, ()) if key in context})
    if kind == 'review':
        _review_history_identities(result)
    if kind.startswith('planning-'):
        for key in ('chapter_counts', 'chapter_id', 'future_scene_count'):
            if key in context:
                result[key] = deepcopy(context[key])
    return result


def _review_history_identities(result):
    for entry in ('previous', 'current'):
        historical = (result.get('review_continuity') or {}).get(entry)
        if isinstance(historical, dict) and 'review' in historical:
            review = historical.pop('review')
            historical['review_identity'] = sha256(json.dumps(review,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def _material_context(result, context):
    result['role'] = context.get('role')
    request = context.get('request') or {}
    result['request'] = {key: deepcopy(request[key]) for key in ('kind', 'target') if key in request}
    if not result['request']:
        match = re.search(r'(?m)^本场对象[:：]\s*([^\n]+)', str(context.get('invitation') or ''))
        if match:
            result['request']['target'] = match[1].strip()


def _creator_context(result, context):
    brief = (context.get('briefing') or {}).get('scene_brief') or {}
    result['briefing'] = {'scene_brief': {key: deepcopy(brief[key])
                                         for key in ('participants', 'source_refs') if key in brief}}
    result['material_index'] = context.get('material_index', '')
    if 'available_material_ids' in context:
        result['available_material_ids'] = deepcopy(context['available_material_ids'])
    if 'available_delta_targets' in context:
        result['available_delta_targets'] = deepcopy(context['available_delta_targets'])
    result['frozen_material_plan'] = deepcopy(context.get('frozen_material_plan'))
    if 'material_need_contract' in context:
        result['material_need_contract'] = context['material_need_contract']
    if context.get('creation_integrity_contract'):
        result['prior_delta_inventory'] = deepcopy(context.get('prior_delta_inventory') or [])
    cards = context.get('actor_card_context') or {}
    result['known_card_targets'] = sorted({row['card']['target'] for key in ('work_cards', 'frozen_scene_cards')
                                    for row in cards.get(key) or [] if isinstance(row.get('card'), dict)})
