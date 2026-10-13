"""Versioned references into a complete natural literary delivery."""
from hashlib import sha256
import re
from typing import Any

SOURCE_SCHEMA = 'arcvellum/natural-source-index/v1'


def natural_source_index(text: str) -> dict[str, Any]:
    blocks = []
    for match in re.finditer(r'[^\n]+(?:\n|$)', text):
        if not match.group().strip():
            continue
        start, end = match.span()
        value = text[start:end]
        blocks.append({'id': f'b{len(blocks)+1:04d}', 'start': start, 'end': end,
                       'beginning': value[:24], 'ending': value[-16:]})
    return {'schema': SOURCE_SCHEMA, 'sha256': sha256(text.encode('utf-8')).hexdigest(),
            'index_unit': 'unicode-codepoint', 'end_exclusive': True, 'blocks': blocks}


def resolve_natural_source_references(payload: Any, text: str) -> Any:
    """Reconstruct literal fields; ambiguous anchors and foreign versions fail explicitly."""
    index = natural_source_index(text)
    blocks = {block['id']: block for block in index['blocks']}
    declared = payload.get('source_sha256') if isinstance(payload, dict) else None
    if declared is not None and declared != index['sha256']:
        raise ValueError('source reference digest differs from preserved original')
    return _resolve(payload, text, index['sha256'], blocks, declared)


def _resolve(value, text, digest, blocks, declared):
    if isinstance(value, list):
        return [_resolve(item, text, digest, blocks, declared) for item in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {'$source'}:
        ref = value['$source']
        if not isinstance(ref, dict) or (ref.get('sha256') or declared) != digest:
            raise ValueError('source reference requires the original digest')
        return _source_slice(ref, text, blocks)
    return {key: _resolve(item, text, digest, blocks, declared) for key, item in value.items()}


def _source_slice(ref, text, blocks):
    start, end = _source_span(ref, text, blocks)
    return text[start:end]


def natural_source_reference_span(ref: dict, text: str) -> tuple[int, int]:
    """Offsets use Python Unicode code points, with an exclusive end."""
    index = natural_source_index(text)
    if ref.get('sha256') != index['sha256']:
        raise ValueError('source reference digest differs from preserved original')
    return _source_span(ref, text, {block['id']: block for block in index['blocks']})


def _source_span(ref, text, blocks):
    first, last = ref.get('first_block'), ref.get('last_block') or ref.get('first_block')
    if first not in blocks or last not in blocks:
        raise ValueError('source reference needs known first/last blocks')
    start, end = blocks[first]['start'], blocks[last]['end']
    if end <= start:
        raise ValueError('source reference block range is reversed')
    region = text[start:end]
    beginning, ending = ref.get('start_anchor'), ref.get('end_anchor')
    if beginning:
        start += _unique_anchor(region, beginning)
    if ending:
        end = blocks[first]['start'] + _unique_anchor(region, ending) + len(ending)
    if end <= start:
        raise ValueError('source reference anchors are reversed')
    return start, end


def _unique_anchor(region, anchor):
    if not isinstance(anchor, str) or not anchor:
        raise ValueError('source anchor must be nonempty text')
    locations = [match.start() for match in re.finditer(re.escape(anchor), region)]
    if not locations:
        table = str.maketrans({glyph: '"' for glyph in "\"'“”‘’"})
        projected, needle = region.translate(table), anchor.translate(table)
        locations = [match.start() for match in re.finditer(re.escape(needle), projected)]
    if len(locations) != 1:
        raise ValueError('source anchor is missing or ambiguous inside its block range: ' + repr(anchor))
    return locations[0]
