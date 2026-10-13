"""Keep literal completed prose while the creator clarifies natural selection IDs."""
from copy import deepcopy
import re


def shared_prefix_source(answer, identifier):
    if not isinstance(identifier, str) or not re.fullmatch(r'v2:[\w-]+:[1-9]\d*', identifier):
        return None
    prefix, number = identifier.rsplit(':', 1)
    pattern = re.escape(prefix + ':') + r'(?P<first>[1-9]\d*)(?P<rest>(?:[ \t]*/[ \t]*:[1-9]\d*)+)'
    matches = []
    for match in re.finditer(pattern, answer):
        numbers = [match['first'], *re.findall(r':([1-9]\d*)', match['rest'])]
        if number in numbers:
            matches.append({'candidate_id': identifier, 'form': 'shared-prefix-list',
                'start': match.start(), 'end': match.end(), 'source': match[0]})
    return matches[0] if matches else _backtick_prefix_source(answer,prefix,number,identifier)


def _backtick_prefix_source(answer,prefix,number,identifier):
    pattern=re.escape(prefix+':')+r'(?P<first>[1-9]\d*)`(?P<rest>(?:[ \t]*[、，,/][ \t]*`:[1-9]\d*`)+)'
    for match in re.finditer(pattern,answer):
        if number in [match['first'],*re.findall(r':([1-9]\d*)',match['rest'])]:
            return {'candidate_id':identifier,'form':'same-line-backtick-prefix-list',
                    'start':match.start(),'end':match.end(),'source':match[0]}
    return (_range_choice_source(answer,prefix,number,identifier)
        or _paragraph_prefix_source(answer,prefix,number,identifier)
        or _ellipsis_choice_source(answer,prefix,number,identifier))


def _paragraph_prefix_source(answer,prefix,number,identifier):
    for short in re.finditer(r'`:'+re.escape(number)+r'`',answer):
        preceding=answer[:short.start()]
        boundary=list(re.finditer(r'\n|(?m:^#{1,6}[ \t]+)',preceding))
        start=boundary[-1].end() if boundary else 0
        anchors=list(re.finditer(r'v2:[\w-]+:[1-9]\d*',preceding[start:]))
        if not anchors or anchors[-1][0].rsplit(':',1)[0]!=prefix:
            continue
        anchor=anchors[-1]
        return {'candidate_id':identifier,'form':'same-paragraph-explicit-prefix',
            'start':short.start(),'end':short.end(),'source':short[0],
            'prefix_start':start+anchor.start(),'prefix_end':start+anchor.end(),'prefix_source':anchor[0]}
    return None


def _range_choice_source(answer,prefix,number,identifier):
    pattern=re.escape(prefix+':')+r'(?P<range>[1-9]\d*(?:[-–—~至][1-9]\d*)?(?:[,，、][1-9]\d*(?:[-–—~至][1-9]\d*)?)*)'
    for match in re.finditer(pattern,answer):
        if not re.search(r'[-–—~至,，、]',match['range']):
            continue
        for part in re.split(r'[,，、]',match['range']):
            bounds=list(map(int,re.split(r'[-–—~至]',part)))
            if bounds[0]<=int(number)<=bounds[-1]:
                return {'candidate_id':identifier,'form':'explicit-number-range','start':match.start(),
                        'end':match.end(),'source':match[0]}
    return None


def _ellipsis_choice_source(answer, prefix, number, identifier):
    """An explicit bold row can inherit its section's preceding full ID prefix."""
    suffix = r'(?m)^\*\*[^*`\n]{0,40}`(?:…|\.\.\.):' + re.escape(number) + r'`'
    for match in re.finditer(suffix, answer):
        preceding = answer[:match.start()]
        anchors = list(re.finditer(r'(?m)^\*\*[^*`\n]{0,40}`(?P<prefix>v2:[\w-]+):[1-9]\d*`', preceding))
        if not anchors:
            continue
        anchor = anchors[-1]
        if anchor['prefix'] != prefix or re.search(r'(?m)^#{1,6}\s', preceding[anchor.end():]):
            continue
        return {'candidate_id': identifier, 'form': 'section-prefix-ellipsis',
            'start': match.start(), 'end': match.end(), 'source': match[0],
            'prefix_start': anchor.start(), 'prefix_end': anchor.end(), 'prefix_source': anchor[0]}
    return None


def abbreviated_choice_source(answer, identifier, known):
    if not isinstance(identifier,str) or identifier not in (known or []):
        return None
    for match in re.finditer(r'(?m)^[-*][ \t]+(?:\*\*)?(?P<short>[a-f0-9]{4,63})(?::(?P<number>[1-9]\d*))?(?![\w:])',answer):
        candidates=[item for item in known if re.fullmatch(r'v2:'+match['short']+r'[a-f0-9]*:'+
            (re.escape(match['number']) if match['number'] else r'[1-9]\d*'),item)]
        if candidates==[identifier]:
            return {'candidate_id':identifier,'form':'unique-catalog-hash-abbreviation',
                'start':match.start(),'end':match.end(),'source':match[0]}
    return None


def validate_choice_ids(answer, payload, validate_literal, known=None):
    for decision in payload.get('material_decisions') or []:
        if not isinstance(decision, dict):
            raise ValueError('selected material decisions must be objects')
        identifier = decision.get('candidate_id')
        notation = shared_prefix_source(answer, identifier) or abbreviated_choice_source(answer,identifier,known)
        literal = isinstance(identifier,str) and re.search(r'(?<![A-Za-z0-9_:])'+re.escape(identifier)+r'(?![A-Za-z0-9_:])',answer)
        if not literal and notation:
            payload.setdefault('material_id_notation_recovery', []).append(notation)
        elif not literal:
            raise ValueError('extraction changed selected material candidate ID; original natural text is preserved')
        else:
            validate_literal(answer, identifier, 'selected material candidate ID')


def revalidate_pending_selection(answer, payload, kind, context, validate_literal):
    """Retry preserved ID evidence; never infer or replace the author's choices."""
    rows = payload.get('unverified_material_decisions')
    known = context.get('available_material_ids') or []
    if (kind != 'creator' or not payload.get('material_selection_pending')
            or payload.get('material_decisions') or not isinstance(rows, list) or not rows
            or any(not isinstance(row, dict) or row.get('candidate_id') not in known for row in rows)):
        return payload
    restored = deepcopy(payload)
    restored['material_decisions'] = deepcopy(rows)
    try:
        validate_choice_ids(answer, restored, validate_literal, known)
    except ValueError:
        return payload
    restored.pop('material_selection_pending')
    restored['selection_id_revalidation'] = {
        'candidate_ids': [row['candidate_id'] for row in rows],
        'method': 'preserved-decisions-current-source-and-catalog',
    }
    return restored


def archive_notes_before_materials(payload, answer, context):
    """Archive choices stay as notes when no candidate material exists yet."""
    decisions = payload.get('material_decisions') or []
    if (not payload.get('material_requests') or payload.get('prose') or not decisions
            or context.get('available_material_ids') != []
            or any(str(row.get('candidate_id', '')) in answer for row in decisions)):
        return payload
    result = deepcopy(payload)
    result['archive_selection_transport_notes'] = decisions
    result['material_decisions'] = []
    return result


def pending_selection(payload, kind, context, error):
    if (kind != 'creator' or context.get('selection_only') or payload.get('material_requests')
            or not payload.get('prose') or not payload.get('decision_summary')
            or 'v2:' not in str(context.get('material_index', '')) or not payload.get('material_decisions')
            or str(error) != 'extraction changed selected material candidate ID; original natural text is preserved'):
        raise error
    result = deepcopy(payload)
    result['unverified_material_decisions'] = result['material_decisions']
    result['material_decisions'] = []
    result['material_selection_pending'] = '主创的自然取舍需要与实际候选编号核对。'
    return result
