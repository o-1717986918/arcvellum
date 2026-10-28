"""Recover one unambiguous missing object terminator; never edit JSON values."""
from hashlib import sha256
import json


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def recover_object_terminator(answer):
    text = answer.strip()
    if text.startswith(chr(96) * 3 + 'json') and text.endswith(chr(96) * 3):
        text = text[7:-3].strip()
    if not text.startswith('{') or not text.endswith('}'):
        return None
    stack, inserted, pieces = [], [], []
    quoted, escaped = False, False
    for position, glyph in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif glyph == '\\':
                escaped = True
            elif glyph == '"':
                quoted = False
            pieces.append(glyph)
            continue
        if glyph == '"':
            quoted = True
        elif glyph in '{[':
            stack.append(glyph)
        elif glyph in '}]':
            expected = '{' if glyph == '}' else '['
            if glyph == ']' and stack[-2:] == ['[', '{'] and not inserted:
                stack.pop()
                pieces.append('}')
                inserted.append(position)
            if not stack or stack.pop() != expected:
                return None
        pieces.append(glyph)
    if stack or quoted or len(inserted) != 1:
        return None
    normalized = ''.join(pieces)
    try:
        payload = json.loads(normalized, object_pairs_hook=_unique_object)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload, {
        'schema': 'arcvellum/transport-json-closure/v1',
        'operation': 'insert-one-object-terminator-before-array-close',
        'offset_unit': 'unicode-codepoint', 'inserted_at': answer.find(text) + inserted[0],
        'json_start_offset': answer.find(text),
        'raw_sha256': sha256(answer.encode('utf-8')).hexdigest(),
        'normalized_sha256': sha256(normalized.encode('utf-8')).hexdigest(),
        'values_changed': False,
    }
