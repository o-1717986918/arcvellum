"""Recover presentation-only card differences from explicit, complete author-labelled cards."""
import re
from literary_engineering_studio_engine.public.literary import ACTOR_CARD_SECTIONS

_FIELD = re.compile(r"(?m)^[ \t]*(?:#{1,6}[ \t]+)?(?:\*\*)?(" + '|'.join(ACTOR_CARD_SECTIONS) + r")(?:\*\*)?[ \t]*[:：]?[ \t]*")
_END = re.compile(r"(?m)^\s*(?:#{1,5}\s|---\s*$)")


def restore_labelled_card_sections(answer, payload):
    groups = _labelled_cards(answer)
    for request in payload.get('material_requests') or []:
        card = request.get('character_card')
        sections = card.get('sections') if isinstance(card, dict) else None
        target = request.get('target')
        if not isinstance(sections, dict) or not isinstance(target, str):
            continue
        matches = [group for group in groups if set(group) == set(ACTOR_CARD_SECTIONS)
            and target in group['CORE_IDENTITY']]
        if len(matches) == 1:
            _restore_fields(answer, sections, matches[0], target, payload)
    return payload


def _labelled_cards(answer):
    fields = list(_FIELD.finditer(answer))
    groups, group = [], {}
    for index, match in enumerate(fields):
        key = match[1]
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
