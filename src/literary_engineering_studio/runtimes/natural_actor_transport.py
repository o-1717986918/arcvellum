"""Keep a character's whole reply while extracting only its source annotations."""
from copy import deepcopy
from .natural_reference_delivery import delivery_fields, decode_reference_delivery


def seed_actor_response(raw, answer, kind, context):
    raw = delivery_fields(raw)
    if kind != 'material' or context.get('role') != 'character-actor' or raw.get('patches'):
        return raw
    result = deepcopy(raw)
    candidates = result.get('candidates')
    if not isinstance(candidates, list) or len(candidates) != 1:
        raise ValueError('actor candidates need one complete response with ordered annotations')
    candidate = candidates[0]
    candidate['text'] = answer
    if not candidate.get('annotations'):
        annotations = []
        for field in ('spoken', 'first_person_action', 'private_impulse'):
            text = candidate.get(field)
            if isinstance(text, str) and text and answer.count(text) == 1:
                annotations.append({'kind': field, 'text': text})
        candidate['annotations'] = sorted(annotations, key=lambda row: answer.index(row['text']))
    if not candidate.get('annotations'):
        raise ValueError('actor candidates need source annotations of the target character')
    return result


def finish_actor_fields(payload,answer,kind,context):
    if kind!='material' or context.get('role')!='character-actor':
        return payload
    raw=deepcopy(payload)
    for candidate in raw.get('candidates') or []:
        for field in ('spoken_fragments','action_fragments','private_fragments','annotation_spans','source_delivery'):
            candidate.pop(field,None)
    return decode_reference_delivery(seed_actor_response(raw,answer,kind,context),answer)
