"""Adapt Engine integrity contracts to preserved, author-owned natural deliveries."""
from copy import deepcopy
from hashlib import sha256
import json
from literary_engineering_studio_engine.public.literary import (
    CONSISTENCY_CONTRACT, SceneConsistencyError, delta_inventory, validate_creator_consistency,
    current_fact_alerts,
)
from .natural_transport_repair import NaturalSourceClarificationError, NaturalExtractionError
from .natural_transport_store import save_json
from .natural_authored_records import author_field_present, restore_authored_consistency_layout


def validate_integrity_delivery(answer, payload, context):
    if context.get('creation_integrity_contract') != CONSISTENCY_CONTRACT or context.get('selection_only'):
        return
    restore_authored_consistency_layout(answer, payload)
    try:
        validate_creator_consistency(payload, (context.get('revision_context') or {}).get('previous_scene_delta'))
    except SceneConsistencyError as error:
        raise NaturalSourceClarificationError(str(error), fields=error.fields, payload=deepcopy(payload)) from error
    if payload.get('prose') and not payload.get('material_requests'):
        _authored_choice_shape(payload, context)
    if payload.get('prose') and not author_field_present(answer, 'consistency_record', payload['consistency_record']):
        raise NaturalSourceClarificationError('完整性记录须是原主创 creator_record 的明确值，不能由整理器代作事实判断。',
            fields=('/consistency_record',), payload=deepcopy(payload))


def _authored_choice_shape(payload, context):
    rows = payload.get('material_decisions') or []
    identifiers = [row.get('candidate_id') for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    expected = set(context.get('available_material_ids') or [])
    if (not isinstance(rows, list) or len(identifiers) != len(rows) or len(identifiers) != len(set(identifiers))
            or set(identifiers) != expected or any(not row.get('reason') or row.get('decision')
                not in {'use', 'adapt', 'defer', 'discard'} for row in rows if isinstance(row, dict))):
        raise NaturalSourceClarificationError('material_decisions须逐项使用candidate_id、decision、reason；覆盖当前候选，允许defer/discard。',
            fields=('/material_decisions',), payload=deepcopy(payload))


def save_consistency_record(root, payload):
    if 'consistency_record' not in payload:
        return
    body = sha256(payload['prose'].encode()).hexdigest()
    save_json(root / 'consistency' / (body + '.json'), {
        'contract': CONSISTENCY_CONTRACT, 'body_sha256': body,
        'author_source': payload.get('source_provenance'),
        'record': payload['consistency_record'], 'scene_delta': payload['scene_delta']})


def read_consistency_record(root, prose):
    path = root / 'consistency' / (sha256(prose.encode()).hexdigest() + '.json')
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def current_review_context(history):
    prior = history.get('previous') or {}
    return {'previous': {'prose_sha256': prior.get('prose_sha256'),
                        'sequence': prior.get('sequence')},
            'open_issues': [{key: row.get(key) for key in
                ('issue_id', 'title', 'evidence', 'status', 'latest_evidence')}
                for row in history.get('open_issues') or []],
            'history_policy': '这些是旧稿问题线索；旧引文不是当前证据。先读当前稿，逐项重新定位或撤回。'}


def prior_delta_context(revision_context):
    previous = (revision_context or {}).get('previous_scene_delta')
    return delta_inventory(previous)


def creator_integrity_context(coordinator, revision_context):
    contract = getattr(coordinator, 'integrity_contract', None)
    return {'creation_integrity_contract': contract, 'prior_delta_inventory': prior_delta_context(revision_context)} if contract else {}


def material_need_version(coordinator):
    from .material_need import needs_required
    if not needs_required(getattr(coordinator, 'layers', {})):
        return ''
    return 'v2' if getattr(coordinator, 'integrity_contract', None) else 'v1'


def integrity_review_context(context, snapshot, root, prose):
    contract = snapshot.get('creation_integrity_contract')
    if not contract:
        return context
    return {**context, 'creation_integrity_contract': contract,
            'fact_alerts': current_fact_alerts(prose),
            'creator_consistency_record': read_consistency_record(root, prose),
            'review_continuity': current_review_context(context['review_continuity'])}


def checked_creation_cache(saved, snapshot, root):
    if not snapshot.get('creation_integrity_contract'):
        return saved
    record = read_consistency_record(root, saved['prose'])
    if not record or record.get('scene_delta') != saved['scene_delta']:
        raise RuntimeError('cached creative result lacks its matching integrity evidence')
    validate_creator_consistency({**saved, 'consistency_record': record['record']})
    return saved


def save_review_integrity(root, prose, extracted):
    body = sha256(prose.encode()).hexdigest()
    save_json(root / 'review-integrity' / (body + '.json'), {
        'body_sha256': body, 'contract': CONSISTENCY_CONTRACT, 'record': extracted})


def validate_current_material_choices(payload, sources):
    if not payload.get('prose') or payload.get('material_requests'):
        return
    rows = payload.get('material_decisions') or []
    identifiers = [row.get('candidate_id') for row in rows if isinstance(row, dict)]
    failures = []
    if len(identifiers) != len(set(identifiers)) or set(identifiers) != set(sources):
        failures.append('逐项评议当前所有候选，允许defer或discard，不把遗漏伪装为利用。')
    for row in rows:
        _material_choice(row, sources, payload['prose'], failures)
    if failures:
        raise NaturalSourceClarificationError('；'.join(dict.fromkeys(failures)),
            fields=('/material_decisions',), payload=deepcopy(payload))


def _material_choice(row, sources, prose, failures):
    identifier = row.get('candidate_id') if isinstance(row, dict) else None
    if identifier not in sources or row.get('decision') not in {'use', 'adapt', 'discard', 'defer'} or not row.get('reason'):
        failures.append('取舍须采用实际候选编号、有效决定及原主创理由。')
        return
    if row['decision'] not in {'use', 'adapt'}:
        return
    excerpt = row.get('source_excerpt')
    landing = row.get('prose_excerpt')
    if not isinstance(excerpt, str) or not excerpt or excerpt not in sources[identifier]['text']:
        failures.append(f'候选 {identifier} 的 source_excerpt 不在该候选原文；请从已提供的该候选 text 中逐字截取，不要倒抄正文。')
    if row.get('indirect_use'):
        if not row.get('prose_location'):
            failures.append('间接用途也须指明本稿的结构位置。')
    elif not isinstance(landing, str) or not landing or landing not in prose:
        failures.append(f'候选 {identifier} 的 prose_excerpt 须是当前正文准确引句；返修后旧锚点不能沿用。')
