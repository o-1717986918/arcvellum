"""Recover presentation-only card differences from explicit, complete author-labelled cards."""
import re
from literary_engineering_studio_engine.public.literary import (
    ACTOR_CARD_SECTIONS, LEGACY_ACTOR_CARD_SECTIONS, ACTOR_CARD_SCHEMA, LEGACY_ACTOR_CARD_SCHEMA,
)

_ALIASES = {"核心身份与代号": "CORE_IDENTITY", "私密空间行为模式": "PRIVATE_BEHAVIOR_MODES",
            "私密互动关键词与动作库": "INTERACTION_LIBRARY"}

_CARD_SETS = {frozenset(ACTOR_CARD_SECTIONS): ACTOR_CARD_SCHEMA,
              frozenset(LEGACY_ACTOR_CARD_SECTIONS): LEGACY_ACTOR_CARD_SCHEMA}
_FIELD = re.compile(r"(?m)^[ \t]*(?:#{1,6}[ \t]+)?(?:\*\*)?(?:【)?(" +
    '|'.join((*LEGACY_ACTOR_CARD_SECTIONS, *_ALIASES)) + r")(?:】)?(?:\*\*)?[ \t]*[:：]?[ \t]*")
_END = re.compile(r"(?m)^\s*(?:#{1,5}\s|---\s*$)")


def restore_labelled_card_sections(answer, payload):
    groups = _labelled_cards(answer)
    requests = list(payload.get('material_requests') or [])
    if isinstance(payload.get('card'), dict):
        requests.append({'character_card': payload['card'], 'target': payload['card'].get('target')})
    for request in requests:
        card = request.get('character_card')
        sections = card.get('sections') if isinstance(card, dict) else None
        sections = _canonical_sections(sections)
        if isinstance(card, dict):
            card['sections'] = sections
            if isinstance(sections, dict) and frozenset(sections) in _CARD_SETS:
                card['schema'] = _CARD_SETS[frozenset(sections)]
                card.setdefault('target', request.get('target'))
                card.setdefault('source_refs', [])
        target = request.get('target')
        if not isinstance(sections, dict) or not isinstance(target, str):
            continue
        matches = [group for group in groups if frozenset(group) in _CARD_SETS
            and target in group['CORE_IDENTITY']]
        if len(matches) == 1:
            _restore_fields(answer, sections, matches[0], target, payload)
    return payload


def _labelled_cards(answer):
    fields = list(_FIELD.finditer(answer))
    groups, group = [], {}
    for index, match in enumerate(fields):
        key = _ALIASES.get(match[1], match[1])
        if key == 'PERSONA_LOAD' and group:
            groups.append(group); group = {}
        end = fields[index+1].start() if index+1 < len(fields) else len(answer)
        trailing = _END.search(answer, match.end(), end)
        if trailing:
            end = trailing.start()
        text = answer[match.end():end].strip()
        group[key] = text
    if group:
        groups.append(group)
    groups.extend(_table_cards(answer))
    return groups


def _table_cards(answer):
    pattern = re.compile(r'(?m)^\|\s*(?:\*\*)?(' + '|'.join(LEGACY_ACTOR_CARD_SECTIONS) +
                         r')(?:\*\*)?\s*\|(?P<text>.+)\|\s*$')
    groups, group = [], {}
    for match in pattern.finditer(answer):
        if match[1] == 'PERSONA_LOAD' and group:
            groups.append(group); group = {}
        group[match[1]] = match['text'].strip()
    if group:
        groups.append(group)
    return groups


def _restore_fields(answer, sections, original, target, payload):
    for key, value in list(sections.items()):
        source = original.get(key)
        if isinstance(value, str) and source and value not in answer and _presentation(source) == _presentation(value):
            sections[key] = source
            payload.setdefault('card_presentation_recovery', []).append({'target':target,'section':key,
                'start':answer.index(source),'end':answer.index(source)+len(source)})


def _presentation(text):
    text = re.sub(r'(?m)^\s*[-*+]\s+', '', text)
    text = text.translate(str.maketrans({glyph:'"' for glyph in "\"'“”‘’"}))
    return re.sub(r'[\s／/]', '', text)


def _canonical_sections(raw):
    if isinstance(raw, list) and all(isinstance(row, dict) and isinstance(row.get('name'), str) and isinstance(row.get('text'), str) for row in raw):
        mapped = {row['name']: row['text'] for row in raw}
        if len(mapped) == len(raw):
            raw = mapped
    if isinstance(raw, dict):
        renamed = {_ALIASES.get(key.strip("【】"), key.strip("【】")): value for key, value in raw.items()}
        if len(renamed) == len(raw) and frozenset(renamed) in _CARD_SETS:
            return renamed
    return raw
