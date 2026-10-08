"""Restore unique literal spans after transport changes quotation presentation only."""
from hashlib import sha256
import re


def restore_commission_source(answer, payload):
    recoveries = []
    projected, offsets = _quote_projection(answer)
    for index, request in enumerate(payload.get("material_requests") or []):
        if not isinstance(request, dict):
            continue
        for container, field, label in _fields(request):
            text = container.get(field)
            if not isinstance(text, str) or not text or text in answer:
                continue
            span = _literal_span(answer, text, projected, offsets)
            if span is None:
                continue
            raw_start, raw_end = span
            original = answer[raw_start:raw_end]
            container[field] = original
            projection = ("blockquote-markers-only" if _quote_projection(text, normalize_quotes=False)[0]
                in _quote_projection(original, normalize_quotes=False)[0] else "blockquote-and-quotation-presentation")
            recoveries.append({"request_index": index, "field": label, "projection": projection,
                "extracted_sha256": sha256(text.encode()).hexdigest(), "start": raw_start, "end": raw_end})
    if recoveries:
        payload["commission_format_recovery"] = recoveries
    return payload


def _fields(request):
    fields = [(request, field, field) for field in ("author_prompt", "working_context", "style_direction")]
    card = request.get("character_card")
    sections = card.get("sections") if isinstance(card, dict) else None
    if isinstance(sections, dict):
        fields.extend((sections, field, "character_card.sections." + field) for field in sections)
    return fields


def _literal_span(answer, text, projected, offsets):
    needle, _ = _quote_projection(text)
    start = projected.find(needle)
    if not needle or start < 0:
        return None
    locations = [match.start() for match in re.finditer(re.escape(needle), projected)]
    originals = {answer[offsets[pos]:offsets[pos+len(needle)-1]+1] for pos in locations}
    if len(originals) != 1:
        return None
    raw_start, raw_end = offsets[start], offsets[start+len(needle)-1]+1
    line_start = answer.rfind("\n", 0, raw_start)+1
    if re.fullmatch(r"[ \t]*> ?", answer[line_start:raw_start]):
        raw_start = line_start
    return raw_start, raw_end


def _quote_projection(text, *, normalize_quotes=True):
    parts, offsets, position = [], [], 0
    for line in text.splitlines(keepends=True):
        prefix = re.match(r"[ \t]*> ?", line)
        count = prefix.end() if prefix else 0
        body = line[count:]
        parts.append(body.translate(str.maketrans({glyph: '"' for glyph in "\"'“”‘’"})) if normalize_quotes else body)
        offsets.extend(range(position + count, position + len(line)))
        position += len(line)
    return "".join(parts), offsets


def restore_tone_source(answer,payload):
    projected,offsets=_quote_projection(answer)
    for index,edit in enumerate(payload.get('edits') or []):
        if not isinstance(edit,dict):
            continue
        label=edit.get('rule_id')
        if isinstance(label,str):
            match=re.match(r'^(?:规则\s*|rule[ \t:-]*)?(1[01]|[1-9])(?:\b|[^\d])',label,re.I)
            if match and label!=match[1]:
                edit['rule_id']=match[1]
                payload.setdefault('tone_rule_recovery',[]).append({'edit':index,'original':label,'canonical':match[1]})
        for field in ('before','after'):
            text=edit.get(field)
            if not isinstance(text,str) or not text or text in answer:
                continue
            span=_literal_span(answer,text,projected,offsets)
            if span:
                edit[field]=answer[span[0]:span[1]]
                payload.setdefault('tone_presentation_recovery',[]).append({'edit':index,'field':field,
                    'start':span[0],'end':span[1]})
    return payload
