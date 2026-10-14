"""Read explicit natural labels; unresolved meaning remains for technical annotation."""
import re
from hashlib import sha256
from literary_engineering_studio_engine.public.literary import ACTOR_CARD_SCHEMA, LEGACY_ACTOR_CARD_SCHEMA
from .natural_card_source import _labelled_cards, _CARD_SETS
from .natural_material_response import whole_material_response
from .natural_choice_labels import local_choice_labels
from .natural_authored_records import authored_record
from .evidence_patch_source import resolve_review_record_evidence
from .natural_transport_repair import NaturalExtractionError, NaturalSourceClarificationError


def local_delivery(answer, kind, context):
    if kind == 'review' and context.get('creation_integrity_contract'):
        return _local_review(answer,context)
    if kind == 'creator' and context.get('creation_integrity_contract') and authored_record(answer, 'creator_record'):
        fields = local_creator_fields(answer, kind, context)
        if fields.get('prose') or fields.get('material_requests'):
            return fields
    if kind == 'material':
        return _local_material(answer, context)
    if kind == 'card':
        cards = local_cards(answer, context)
        target = context.get('target')
        return {'card': cards[target]} if target in cards else None
    if kind == 'style-choice':
        return _style_choice(answer)
    if kind == 'tone':
        return _tone_edits(answer)
    if kind == 'material-plan':
        fields = labelled_fields(answer, {'required_kinds': ('必用类别', 'required_kinds'), 'reason': ('理由', 'reason')})
        if set(fields) == {'required_kinds', 'reason'}:
            fields['required_kinds'] = _identifiers(fields['required_kinds'])
            return {'material_plan': fields}
    return None


def _local_review(answer, context):
    record = authored_record(answer, 'review_record')
    if record is None:
        return None
    try:
        return resolve_review_record_evidence(record,context.get('prose',''))
    except NaturalExtractionError as error:
        clarified = NaturalSourceClarificationError(str(error),fields=error.fields,payload=record)
        clarified.source_text=answer
        raise clarified from error


def local_cards(answer, context):
    targets = set(context.get('eligible_actors') or [])
    if context.get('target'):
        targets.add(context['target'])
    rows = {}
    for sections in _labelled_cards(answer):
        schema = _CARD_SETS.get(frozenset(sections))
        if schema not in (ACTOR_CARD_SCHEMA, LEGACY_ACTOR_CARD_SCHEMA):
            continue
        identity = sections['CORE_IDENTITY']
        matches = _card_identity_targets(answer, identity, targets)
        if len(matches) == 1:
            target = matches[0]
            card = {'schema': schema, 'target': target, 'sections': sections,
                    'source_refs': ['natural-source:' + sha256(answer.encode('utf-8')).hexdigest()], 'notes': ''}
            rows[target] = None if target in rows else card
    return {target: card for target, card in rows.items() if card is not None}


def _card_identity_targets(answer, identity, targets):
    names = _identity_values(identity, '角色名|姓名|名字|target')
    codes = _identity_values(identity, '代号')
    heading = _explicit_card_heading(answer, identity)
    if names:
        matches = targets.intersection(names)
    elif targets.intersection(codes):
        matches = targets.intersection(codes)
    elif heading in targets:
        matches = {heading}
    else:
        matches = set() if codes else {target for target in targets if target in identity}
    if heading in targets and matches and heading not in matches:
        return []  # An explicit name and card heading disagree; preserve ambiguity.
    return list(matches)


def _identity_values(identity, labels):
    return {re.split(r'[；;。]', match[1], maxsplit=1)[0].strip('`* \"\'')
            for match in re.finditer(r'(?m)^[ \t]*(?:[-*][ \t]+)?(?:' + labels +
                                     r')[ \t]*[:：][ \t]*([^\n]+)', identity)}


def _explicit_card_heading(answer, identity):
    if answer.count(identity) != 1:
        return ''
    prefix = answer[:answer.index(identity)]
    headings = list(re.finditer(r'(?m)^#{1,6}[ \t]+(?:角色卡|人物卡)[ \t]*[·:：\-][ \t]*([^\n]+)', prefix))
    return headings[-1][1].strip('`* \"\' \r') if headings else ''


def local_creator_fields(answer, kind, context=None):
    if kind != 'creator':
        return {}
    authored = _creator_authored_fields(answer, context)
    if explicit_creator_phase(answer) == 'prepare':
        return {**authored, 'prose': ''}
    fields = labelled_fields(answer, {'prose': ('最终正文', '正文候选'),
        'decision_summary': ('创作札记', 'decision_summary'),
        'delta': ('交接札记', 'SceneDelta', '连续性交接'),
        'selection': ('素材取舍', '取舍记录'), 'requests': ('待执行委托',)})
    result = {**_creator_note_fields(answer, fields, context or {}), **authored}
    if fields.get('requests'):
        return result
    body = _headed_creator_body(answer) or _delimited_creator_body(answer)
    if body is not None:
        if (context or {}).get('available_material_ids') == [] and _has_commission_heading(answer):
            return {**result, 'prose':'','pending_body_source':body,'delivery_phase_recovery':'pending-explicit-commissions'}
        result['prose'] = body
        if not _has_commission_heading(answer):
            result['material_requests'] = []
        return result
    if fields.get('prose'):
        result['prose'] = fields['prose']
    return result


def _creator_authored_fields(answer, context):
    if not (context or {}).get('creation_integrity_contract'):
        return {}
    record = authored_record(answer, 'creator_record') or {}
    return {key: value for key, value in record.items() if key != 'prose'}


def _has_commission_heading(answer):
    return bool(re.search(r'(?m)^(?:#{1,6}[ \t]+|\*\*)(?:[一二三四五六七八九十\d]+[、.．· \t-]+)?(?:取材委托|本轮委托|委托[一二三四五六七八九十\dA-Z]+)', answer))


def _creator_note_fields(answer, fields, context):
    result = {}
    summary = _source_note_section(answer) or fields.get('decision_summary')
    if summary:
        result['decision_summary'] = summary
    choices = local_choice_labels(answer, context.get('available_material_ids') or [])
    if choices:
        result['material_decisions'] = choices
    return result


def _source_note_section(answer):
    match = re.search(r'(?m)^(#{1,6})[ \t]+(?:[一二三四五六七八九十\d]+[、.．· \t-]+)?(?:本场文学判断|本轮开场判断|创作意图与缺口判断|创作札记|取舍札记)[^\n]*$', answer)
    if not match:
        return None
    closing = re.search(r'(?m)^#{1,'+str(len(match[1]))+r'}[ \t]+', answer[match.end():])
    end = match.end()+closing.start() if closing else len(answer)
    return answer[match.end():end].strip().removesuffix('---').rstrip() or None


def _delimited_creator_body(answer):
    pattern = (r'(?:下面(?:是|交付)(?:最终|本场|本单元)?正文|正文如下)[。:：]\s*\n\s*---\s*\n'
               r'(?P<body>[\s\S]+?)\n---\s*\n(?=(?:\*\*|#{1,6}[ \t]+)?(?:交接札记|创作札记|素材取舍|返修札记|主创札记))')
    matches = list(re.finditer(pattern, answer))
    if len(matches) == 1:
        return matches[0]['body'].strip()
    title_boundary = r'(?m)^---[ \t]*\n\s*\n(?P<body>#[^\n]+\n[\s\S]+?)\n---[ \t]*\n\s*\n(?=#{1,6}[ \t]+(?:创作札记|取舍札记|素材取舍|返修札记|主创札记))'
    matches=list(re.finditer(title_boundary,answer))
    return matches[0]['body'].strip() if len(matches)==1 else None


def _headed_creator_body(answer):
    pattern = r'(?m)^(#{1,6})[ \t]+(?:[一二三四五六七八九十\d]+[、.．· \t-]+)?(?:最终正文|正文候选|正文)[^\n]*$'
    matches = [match for match in re.finditer(pattern, answer) if not re.search('试写|草稿', match[0])]
    if len(matches) != 1:
        return None
    match = matches[0]
    closing = re.search(r'(?m)^#{1,' + str(len(match[1])) + r'}[ \t]+(?:[一二三四五六七八九十\d]+[、.．· \t-]+)?(?:交接|取舍|素材取舍|创作札记|返修札记|主创札记|SceneDelta|连续性交接)[^\n]*$', answer[match.end():])
    end = match.end()+closing.start() if closing else len(answer)
    record_start = _creator_record_start(answer)
    if record_start is not None and record_start > match.end():
        end = min(end, record_start)
    body = answer[match.end():end].strip()
    if body.endswith('\n---'):
        body = body[:-4].rstrip()
    return body or None


def _creator_record_start(answer):
    if authored_record(answer, 'creator_record') is None:
        return None
    blocks=[match for match in re.finditer(r'(?ms)^```json[ \t]*\r?\n.*?\r?\n```[ \t]*$',answer)
            if authored_record(match[0], 'creator_record') is not None]
    return blocks[0].start() if len(blocks)==1 else None


def explicit_creator_phase(answer):
    for line in answer.splitlines():
        if re.search(r'(?:交付阶段|本轮阶段)\s*[*：:]', line):
            if re.search(r'准备邀请|准备阶段|等待取材|待执行委托', line):
                return 'prepare'
            if re.search(r'完成正文|最终正文|成稿交付|完成阶段', line):
                return 'complete'
    if re.search(r'(?m)^#{1,6}[ \t]+(?:[一二三四五六七八九十\d]+[、.．· \t-]+)?(?:本轮重新委托|(?:本轮)?待执行委托)', answer):
        return 'prepare'
    return None


def labelled_fields(text, aliases):
    names = {name: field for field, values in aliases.items() for name in values}
    pattern = r'(?m)^[ \t]*(?:#{1,6}[ \t]+|[-*][ \t]+)?(?:【)?(' + '|'.join(map(re.escape, names)) + r')(?:】)?[ \t]*(?:[:：][ \t]*|\n)'
    matches = list(re.finditer(pattern, text))
    result = {}
    for index, match in enumerate(matches):
        end = matches[index+1].start() if index+1 < len(matches) else len(text)
        value = text[match.end():end].strip()
        key = names[match[1]]
        if key in result:
            return {}
        if value:
            result[key] = value
    return result


def _style_choice(answer):
    fields = labelled_fields(answer, {'preset_id': ('预设', '选用预设', 'preset_id'),
        'reference_ids': ('参照', '参照片段', 'reference_ids'),
        'literary_mode': ('叙述方式', '文学方式', 'literary_mode'), 'reason': ('选择理由', 'reason')})
    if len(fields) != 4:
        return None
    fields['preset_id'] = fields['preset_id'].strip('` ')
    fields['reference_ids'] = _identifiers(fields['reference_ids'])
    return fields


def _identifiers(value):
    if value.strip() in ('无', '空', '[]'):
        return []
    return [item.strip('` ') for item in re.split(r'[,，、\s]+', value) if item.strip('` ')]


def _local_material(answer, context):
    if context.get('role') in {'environment-writer', 'character-describer', 'scene-describer'} and answer.strip():
        return {'candidates': [{'text': answer, 'focus': '本次委托的完整自然回应',
                                'source_delivery': 'original-v2'}]}
    plain = whole_material_response(answer, context)
    if plain is not None or context.get('role') != 'character-actor':
        return plain
    text = answer.strip()
    if re.fullmatch(r'“[^“”\n]+”', text):
        return {'candidates': [{'text': text, 'focus': '人物的当轮回应', 'spoken': text[1:-1],
                                'source_delivery': 'original-v2',
                                'annotation_spans': [{'kind': 'spoken', 'start': 1, 'end': len(text)-1}]}]}
    fields = labelled_fields(answer, {'spoken': ('台词',), 'first_person_action': ('动作',),
                                     'private_impulse': ('内心冲动', '私人冲动')})
    if not fields or len(text) > 2400:
        return None
    spans = [{'kind': key, 'start': text.index(value), 'end': text.index(value)+len(value)}
             for key, value in fields.items() if text.count(value) == 1]
    if len(spans) != len(fields):
        return None
    return {'candidates': [{'text': text, 'focus': '人物的当轮回应', **fields,
                            'source_delivery': 'original-v2', 'annotation_spans': spans}]}


def _tone_edits(answer):
    marked = _marked_tone_edits(answer)
    if marked is not None:
        return marked
    starts = list(re.finditer(r'(?m)^[ \t]*(?:#{1,6}[ \t]+|[-*][ \t]+)?(?:原句|before)[:：]', answer))
    if not starts:
        return _tone_no_change(answer)
    edits=[]
    for index, match in enumerate(starts):
        end=starts[index+1].start() if index+1<len(starts) else len(answer)
        fields=labelled_fields(answer[match.start():end], {'before':('原句','before'),
            'after':('改句','after'),'reason':('理由','reason'),'rule_id':('规则编号','rule_id')})
        if set(fields)!= {'before','after','reason','rule_id'} or not re.fullmatch(r'(?:[1-9]|10|11)',fields['rule_id']):
            return None
        edits.append(fields)
    return {'edits':edits,'summary':''}


def _tone_no_change(answer):
    """Register an explicit verdict for the whole pass, never an absent answer."""
    if re.search(r'【(?:原片段|替换片段)】|(?:改句|after)[:：]|建议(?:替换|修改)[:：]', answer):
        return None
    verdict = re.search(
        r'(?:本场|本轮|本次)(?:不(?:给|提出)|没有|无)(?:额外的)?(?:替换|修改)建议'
        r'[；，,;][ \t]*(?:照原稿保留即可|保留原稿|原稿保留)[。.!！]?', answer)
    if verdict is None:
        return None
    return {'edits': [], 'summary': verdict[0], 'no_edit_source': verdict[0]}


def _marked_tone_edits(answer):
    pattern = r'(?m)^[ \t]*\*{0,2}【(规则编号|原片段|替换片段|理由)】\*{0,2}[ \t]*[:：]?[ \t]*'
    labels = list(re.finditer(pattern, answer))
    if not labels or labels[0][1] != '规则编号':
        return None
    aliases = {'规则编号': 'rule_id', '原片段': 'before', '替换片段': 'after', '理由': 'reason'}
    edits, current = [], {}
    for index, match in enumerate(labels):
        if match[1] == '规则编号' and current:
            edits.append(current); current = {}
        end = labels[index + 1].start() if index + 1 < len(labels) else len(answer)
        value = re.split(r'(?m)^---[ \t]*$|^#{1,6}[ \t]+', answer[match.end():end], maxsplit=1)[0].strip()
        key = aliases[match[1]]
        if key in current:
            return None
        current[key] = value
    edits.append(current)
    for edit in edits:
        if set(edit) != {'rule_id', 'before', 'after', 'reason'} or not all(edit.values()):
            return None
        rule = re.match(r'规则\s*(1[01]|[1-9])(?:\D|$)', edit['rule_id'])
        if rule is None:
            return None
        edit['rule_id'] = rule[1]
    return {'edits': edits, 'summary': ''}
