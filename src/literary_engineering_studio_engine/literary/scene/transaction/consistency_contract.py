"""Validate author-owned facts and cumulative changes; never infer story truth."""
from hashlib import sha256
import json
from collections.abc import Mapping

CONSISTENCY_CONTRACT = 'scene-consistency/v1'
DELTA_GROUPS = ('character_changes', 'canon_candidates', 'continuity_changes',
                'promise_updates', 'reader_question_updates', 'new_asset_candidates')


class SceneConsistencyError(ValueError):
    def __init__(self, message, fields):
        super().__init__(message)
        self.fields = tuple(fields)


def delta_inventory(delta):
    rows = []
    for group in DELTA_GROUPS:
        for proposal in (delta or {}).get(group) or []:
            identity = [group, proposal.get('target_ref'), proposal.get('summary'), proposal.get('operation', 'update')]
            rows.append({'proposal_id': sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:20],
                         'group': group, **proposal})
    return rows


def validate_creator_consistency(payload, prior_delta=None):
    if not payload.get('prose') or payload.get('material_requests'):
        return
    record = payload.get('consistency_record')
    if not isinstance(record, dict):
        raise SceneConsistencyError('交付当前稿的 consistency_record，事实判断由原主创填写。', ['/consistency_record'])
    delta = payload.get('scene_delta')
    if not isinstance(delta, Mapping):
        raise SceneConsistencyError('scene_delta 须按变化类别分组，不能交付未分组的提案列表。', ['/scene_delta'])
    for group in DELTA_GROUPS:
        entries = delta.get(group, [])
        if not isinstance(entries, list) or any(not isinstance(row, Mapping) for row in entries):
            raise SceneConsistencyError('scene_delta 各变化类别须是提案对象数组。', ['/scene_delta'])
    _canon_classification(record, delta)
    _facts(record, payload['prose'], delta)
    _cumulative_dispositions(record, prior_delta, delta)


def _canon_classification(record, delta):
    classification = record.get('canon_change')
    if not isinstance(classification, bool) and classification != 'unknown':
        raise SceneConsistencyError('canon_change 必须是 true、false 或 unknown。', ['/consistency_record'])
    if classification is False and (not _text(record.get('no_canon_change_reason')) or delta.get('canon_candidates')):
        raise SceneConsistencyError('无Canon变化须说明理由，不能同时交付Canon变化提案。', ['/consistency_record'])
    if classification is not False and not delta.get('canon_candidates'):
        raise SceneConsistencyError('有或无法排除Canon变化时，交付候选提案；未确认提案不能视为已应用。',
                                    ['/consistency_record', '/scene_delta'])


def _facts(record, prose, delta):
    facts = record.get('facts')
    if not isinstance(facts, list) or not facts and not _text(record.get('no_persistent_facts_reason')):
        raise SceneConsistencyError('列出本稿持续事实；确实没有时说明理由。', ['/consistency_record'])
    for fact in facts:
        _fact(fact, prose, delta)
    _canon_fact_coverage(facts, delta)


def _canon_fact_coverage(facts, delta):
    for proposal in delta.get('canon_candidates') or []:
        summary = proposal.get('summary')
        linked = [fact for fact in facts if isinstance(fact, dict) and fact.get('durable') is True
                  and fact.get('source_state') in {'new', 'changed'}
                  and fact.get('delta_group') == 'canon_candidates'
                  and fact.get('delta_target') == proposal.get('target_ref')
                  and fact.get('delta_summary') == summary]
        if not _text(summary) or '；' in summary or ';' in summary or len(linked) != 1:
            raise SceneConsistencyError('每条Canon候选只对应一项持续事实；拆开合并叙述，并在facts中逐项登记当前正文证据。',
                                        ['/consistency_record', '/scene_delta'])


def _fact(fact, prose, delta):
    fields = ('subject', 'predicate', 'value', 'evidence', 'source_state')
    if not isinstance(fact, dict) or any(not _text(fact.get(key)) for key in fields):
        raise SceneConsistencyError('事实记录须包含对象、属性、值、当前正文引句和来源状态。', ['/consistency_record'])
    if fact['evidence'] not in prose or fact['source_state'] not in {'new', 'changed', 'unchanged', 'attributed', 'pending'}:
        raise SceneConsistencyError('事实引句须来自当前稿，来源状态须明确。', ['/consistency_record'])
    if not isinstance(fact.get('durable'), bool):
        raise SceneConsistencyError('由主创明确声明事实是否持续 durable。', ['/consistency_record'])
    if fact['durable'] and fact['source_state'] in {'new', 'changed'}:
        group = fact.get('delta_group')
        matching = [row for row in delta.get(group) or [] if row.get('target_ref') == fact.get('delta_target')
                    and row.get('summary') == fact.get('delta_summary')]
        if group not in DELTA_GROUPS or not matching:
            raise SceneConsistencyError('新建或改变的持续事实须指向本稿SceneDelta中的准确提案。',
                                        ['/consistency_record', '/scene_delta'])


def _cumulative_dispositions(record, prior_delta, delta):
    prior = {row['proposal_id']: row for row in delta_inventory(prior_delta)}
    if not prior:
        return
    dispositions = record.get('prior_delta_dispositions')
    if not isinstance(dispositions, list):
        raise SceneConsistencyError('逐项说明上一未提交稿Delta的保留、替换或撤回；草稿记录尚未正式写回。',
                                    ['/consistency_record', '/scene_delta'])
    current = delta_inventory(delta)
    current_ids = {row['proposal_id'] for row in current}
    seen = set()
    for row in dispositions:
        _disposition(row, prior, current, current_ids, seen)
    if seen != set(prior):
        raise SceneConsistencyError('累计Delta核对遗漏上一稿提案，不能以“之前已登记”跳过写回。',
                                    ['/consistency_record', '/scene_delta'])


def _disposition(row, prior, current, current_ids, seen):
    identifier = row.get('proposal_id') if isinstance(row, dict) else None
    if identifier not in prior or identifier in seen or not _text(row.get('reason')):
        raise SceneConsistencyError('上一稿提案处置须覆盖准确编号且说明理由。', ['/consistency_record'])
    seen.add(identifier)
    action = row.get('action')
    if action == 'withdraw':
        return
    if action == 'retain' and identifier in current_ids:
        return
    replacement = row.get('replacement') or {}
    if action == 'replace' and any(all(proposal.get(key) == replacement.get(key)
            for key in ('group', 'target_ref', 'summary')) for proposal in current):
        return
    raise SceneConsistencyError('保留或替换的提案必须出现在当前累计Delta中，不能只写札记。',
                                ['/consistency_record', '/scene_delta'])


def _text(value):
    return isinstance(value, str) and bool(value.strip())
