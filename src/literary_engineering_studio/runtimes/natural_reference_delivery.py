"""Decode literal references and preserve actor annotations in original order."""
from copy import deepcopy
import json
from .natural_reference_ranges import recover_reference_ranges
from literary_engineering_studio_engine.public.literary import (
    natural_source_index, natural_source_reference_span, resolve_natural_source_references,
)


class PartialReferenceError(ValueError):
    def __init__(self, payload, paths, issues):
        super().__init__('; '.join(issues))
        self.payload, self.paths = payload, paths


def decode_reference_delivery(raw, answer):
    raw = delivery_fields(raw)
    raw = _candidate_containers(raw)
    raw = _encoded_references(raw, answer)
    if 'source_sha256' not in raw:
        raw={**raw,'source_sha256':natural_source_index(answer)['sha256']}
    raw=recover_reference_ranges(raw,answer)
    payload = _decode_fields(raw, answer)
    for position, candidate in enumerate(payload.get('candidates') or []):
        original = raw['candidates'][position]
        candidate['source_delivery'] = 'original-v2'
        _annotations(candidate, original, answer)
    return payload


def _encoded_references(value, answer):
    """Decode only an explicit source envelope that is not literal source prose."""
    if isinstance(value, dict):
        value=_reference_envelope(value)
        return {key: _encoded_references(item, answer) for key, item in value.items()}
    if isinstance(value, list):
        return [_encoded_references(item, answer) for item in value]
    if isinstance(value, str) and value not in answer and value.lstrip().startswith('{'):
        try:
            parsed = json.loads(value, object_pairs_hook=_unique_keys)
        except (ValueError, TypeError):
            return value
        if isinstance(parsed, dict) and set(parsed) == {'$source'} and isinstance(parsed['$source'], dict):
            return parsed
    return value


def _candidate_containers(raw):
    candidates = raw.get('candidates')
    if not isinstance(candidates, list):
        return raw
    flattened, containers = [], []
    def append(rows, path):
        for index, row in enumerate(rows):
            position = path + [index]
            if isinstance(row, dict) and set(row) == {'candidates'} and isinstance(row['candidates'], list):
                containers.append(position)
                append(row['candidates'], position)
            else:
                flattened.append(row)
    append(candidates, [])
    if not containers:
        return raw
    return {**raw, 'candidates': flattened, 'candidate_container_recovery': {'container_positions': containers}}


def _reference_envelope(value):
    ref=value.get('$source')
    extra=set(value)-{'$source'}
    if isinstance(ref,dict) and extra and extra.issubset({'start_anchor','end_anchor'}) and not extra.intersection(ref):
        return {'$source':{**ref,**{key:value[key] for key in extra}}}
    return value


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate source-reference key')
        result[key] = value
    return result


def delivery_fields(raw):
    """Accept a copied input envelope only when its literary object is explicit."""
    contract = raw.get('task_contract')
    keys = {'prose', 'material_requests', 'candidates', 'edits', 'card', 'preset_id',
            'chapter', 'chapters', 'scenes', 'decision', 'material_plan', 'patches'}
    if isinstance(contract, dict) and not keys.intersection(raw):
        return {**contract, **({'source_sha256': raw['source_sha256']} if 'source_sha256' in raw else {})}
    return raw


def _decode_fields(raw, answer):
    resolve_natural_source_references({'source_sha256':raw['source_sha256']},answer)
    paths,issues=[],[]
    payload={key:_decode_leaf(value,'/'+key,raw['source_sha256'],answer,paths,issues) for key,value in raw.items()}
    if paths:
        raise PartialReferenceError(payload, paths, issues)
    return payload


def _decode_leaf(value,path,digest,answer,paths,issues):
    if isinstance(value,dict) and set(value)=={'$source'}:
        try:
            return resolve_natural_source_references({'source_sha256':digest,'value':value},answer)['value']
        except ValueError as error:
            paths.append(path);issues.append(str(error));return value
    if isinstance(value,dict):
        return {key:_decode_leaf(item,path+'/'+key,digest,answer,paths,issues) for key,item in value.items()}
    if isinstance(value,list):
        return [_decode_leaf(item,path+'/'+str(index),digest,answer,paths,issues) for index,item in enumerate(value)]
    return value


def _annotations(candidate, original, answer):
    labels = {'spoken': 'spoken_fragments', 'first_person_action': 'action_fragments',
              'private_impulse': 'private_fragments'}
    spans = []
    text_start = _original_start(original.get('text'), candidate.get('text', ''), answer)
    for index, entry in enumerate(candidate.get('annotations') or []):
        kind, text = entry.get('kind'), entry.get('text')
        if kind not in labels or not isinstance(text, str) or not text.strip():
            raise ValueError('actor annotation needs a known kind and literal text')
        span = _annotation_span(original['annotations'][index], entry, candidate['text'], text_start, answer)
        if span is not None:
            spans.append(span)
    if spans:
        candidate['annotation_spans'] = _ordered_annotations(candidate, spans)
    for kind, label in labels.items():
        candidate[label]=[row['text'] for row in candidate.get('annotations') or [] if row['kind']==kind]
        if candidate.get(label):
            candidate[kind] = candidate[label][0]


def _ordered_annotations(candidate, spans):
    if [item['start'] for item in spans] == sorted(item['start'] for item in spans):
        return spans
    if len(spans) != len(candidate['annotations']):
        raise ValueError('actor annotations need original source order with every position verified')
    order=sorted(range(len(spans)),key=lambda index:spans[index]['start'])
    candidate['annotations']=[candidate['annotations'][index] for index in order]
    candidate['annotation_order_recovery']={'source_order':order}
    return [spans[index] for index in order]


def _annotation_span(original, entry, candidate, text_start, answer):
    start = _original_start(original.get('text'), entry['text'], answer)
    if start is None or text_start is None:
        return None
    relative = start - text_start
    text = entry['text']
    if relative < 0 or candidate[relative:relative+len(text)] != text:
        raise ValueError('actor annotation is outside its candidate')
    return {'kind': entry['kind'], 'start': relative, 'end': relative+len(text)}


def _original_start(raw, text, answer):
    if isinstance(raw, dict) and '$source' in raw:
        ref = {**raw['$source'], 'sha256': natural_source_index(answer)['sha256']}
        return natural_source_reference_span(ref, answer)[0]
    if text and answer.count(text) == 1:
        return answer.index(text)
    return None


def hydrate_local_cards(payload, cards):
    result = deepcopy(payload)
    for request in result.get('material_requests') or []:
        if not isinstance(request, dict):
            raise ValueError('saved material request must be an object')
        target = request.get('target')
        if request.get('kind') == 'actor' and target in cards:
            request['character_card'] = deepcopy(cards[target])
    return result
