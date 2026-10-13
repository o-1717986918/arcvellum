"""Typed metadata repairs; semantic values remain the original author's work."""
from literary_engineering_studio_engine.public.literary import CONSISTENCY_CATEGORIES

_QUOTE = {'prose_sha256': 'context.prose_source.sha256的准确值',
          'prose_block': '真正支持此判断的context.prose_source.blocks现有id；程序原样取回该段'}
_FINDINGS = {
    'strengths': {'claim': '原审读者重新核对后的成立之处', 'evidence': _QUOTE},
    'major_issues': {'title': '仍成立的主要问题', 'category': 'time/quantity/space/object_state/identity/writeback/literary',
        'evidence': _QUOTE, 'problem_excerpt': '此条evidence内部真正有问题的连续原句',
        'counter_excerpt': '当前正文的冲突另一端原句，无则空', 'reader_effect': '阅读影响',
        'direction': '修复方向', 'prior_issue_id': '对应历史编号，新问题为空'},
    'optional_explorations': {'question': '可选审美方向', 'evidence': _QUOTE, 'direction': '可选方向'},
    'issue_progress': {'issue_id': '已有待核对编号', 'status': 'resolved/persists/changed/uncertain',
        'evidence': _QUOTE, 'problem_excerpt': 'persists/changed时为此条evidence内仍存在的问题；resolved时空'},
}


def integrity_field_contract(path):
    parts = path.strip('/').split('/')
    root = parts[0]
    if len(parts)>1:
        return _nested_integrity_contract(parts)
    if root in _FINDINGS:
        return [_FINDINGS[root]]
    if path == '/consistency_checks':
        return [{'category': category, 'status': 'clear/issue/uncertain',
                 'evidence': [_QUOTE], 'note': '逐项核对事实及fact_alerts；无相关内容evidence为空数组'}
                for category in CONSISTENCY_CATEGORIES]
    if path == '/decision':
        return 'pass/revise/escalate；尚有主要问题用revise，无法判断的事实警报用escalate'
    if path == '/summary':
        return '原审读者更新后的结论字符串'
    if path == '/revision_instructions':
        return ['仅当前稿仍成立的必改项；已经改正或撤回的项删除']
    if path == '/material_decisions':
        return [{'candidate_id': 'available_material_ids中实际编号，逐项覆盖，不用material_id',
            'decision': 'use/adapt/discard/defer，不用status', 'reason': '原作者文学理由',
            'source_excerpt': '采用/改写时为候选准确短原句', 'prose_excerpt': '本稿准确短原句',
            'indirect_use': '仅间接理解用途时写明，否则空字符串', 'prose_location': '间接用途的结构位置'}]
    if path == '/consistency_record':
        return {'canon_change': 'true/false/unknown', 'no_canon_change_reason': 'false时非空',
            'facts': [{'subject': '对象', 'predicate': '属性', 'value': '事实',
                'evidence': '当前正文准确短原句，字符串',
                'source_state': 'new/changed/unchanged/attributed/pending', 'durable': '布尔值',
                'delta_group': '新改持续事实对应实际Delta组', 'delta_target': '对应target_ref',
                'delta_summary': '逐字符复制对应scene_delta提案的summary，包含全部标点，不另写概括'}], 'no_persistent_facts_reason': '无事实时的理由',
            'prior_delta_dispositions': [{'proposal_id': 'prior_delta_inventory编号',
                'action': 'retain/replace/withdraw', 'reason': '逐项原作者判断',
                'replacement': {'group': 'replace时的组', 'target_ref': 'replace时目标',
                                'summary': 'replace时的实际提案summary'}}]}
    if path == '/scene_delta':
        proposal = {'target_ref': 'context.available_delta_targets中的本场实际目标',
                    'summary': '本稿实际改变', 'evidence': '当前正文准确原句',
                    'operation': 'append/update/replace', 'attributes': {}}
        canon_proposal={**proposal,'summary':'仅一个对象的一项持续事实，不含分号；canon_candidates每条必须在facts中恰有一条durable=true、source_state=new或changed、delta_group=canon_candidates且delta_target/delta_summary逐字相同的事实'}
        return {'character_changes': [proposal], 'canon_candidates': [canon_proposal],
                'continuity_changes': [proposal], 'promise_updates': [],
                'reader_question_updates': [], 'new_asset_candidates': [],
                'next_handoff': ['下一场交接原作者文字；没有则空数组']}
    return None


def _nested_integrity_contract(parts):
    root=parts[0]
    if root in _FINDINGS and len(parts)==2:
        return _FINDINGS[root]
    if root=='scene_delta' and len(parts)==2:
        return integrity_field_contract('/scene_delta').get(parts[1])
    if root=='consistency_record':
        return _fact_field_contract(parts)
    return None


def _fact_field_contract(parts):
    record=integrity_field_contract('/consistency_record')
    if parts[1]!='facts':
        return record.get(parts[1])
    if len(parts)==2:
        return record['facts']
    if len(parts)==3:
        return record['facts'][0]
    return record['facts'][0].get(parts[3]) if len(parts)==4 else None
