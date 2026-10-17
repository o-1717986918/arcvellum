"""Preserve explicit narrative choices without interpreting fictional meaning."""
import re

_FIELDS = (
    'narrative_mode', 'temporal_structure', 'viewpoint_design', 'pacing_design',
    'structural_signature', 'narrator_voice', 'world_presentation',
)
_LABEL = re.compile(
    r'(?m)^[ \t]*(?:[-*][ \t]+)?(?:\*\*|`)?('
    + '|'.join(_FIELDS) + r')(?:\*\*|`)?[ \t]*[:：][ \t]*'
)


def normalize_narrative_design(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, str):
        value = _labelled_design(value.strip())
    if not isinstance(value, dict):
        raise ValueError('narrative_design must be an object or authored narrative text')
    if any(not isinstance(key, str) or not key.strip() or not isinstance(text, str)
           for key, text in value.items()):
        raise ValueError('narrative_design fields must contain authored text, not nested or numeric values')
    design = {key: text.strip() for key, text in value.items() if text.strip()}
    if any(len(text) > 8000 for text in design.values()) or sum(map(len, design.values())) > 32000:
        raise ValueError('narrative design exceeds context capacity; shorten the plan explicitly')
    return design


def _labelled_design(text: str) -> dict[str, str]:
    matches = list(_LABEL.finditer(text))
    if not matches:
        return {'notes': text} if text else {}
    design = {}
    if text[:matches[0].start()].strip():
        design['notes'] = text[:matches[0].start()].strip()
    for index, match in enumerate(matches):
        key = match[1]
        if key in design:
            raise ValueError(f'narrative_design repeats {key}; resolve the authored choices explicitly')
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        design[key] = text[match.end():end].strip()
    return design
