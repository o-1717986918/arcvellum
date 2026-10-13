"""Restore unique literal spans after transport changes quotation presentation only."""
from hashlib import sha256
import json
import re


def restore_commission_source(answer, payload):
    restore_attachment_line_ranges(answer,payload)
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
            terminal_recovery = span is None and label in {"author_prompt", "working_context", "style_direction"}
            if terminal_recovery:
                span = _terminal_punctuation_span(answer, text)
            if span is None:
                continue
            raw_start, raw_end = span
            original = answer[raw_start:raw_end]
            container[field] = original
            projection = ("blockquote-markers-only" if _quote_projection(text, normalize_quotes=False)[0]
                in _quote_projection(original, normalize_quotes=False)[0] else "blockquote-and-quotation-presentation")
            if terminal_recovery:
                projection = "terminal-punctuation-only"
            recoveries.append({"request_index": index, "field": label, "projection": projection,
                "extracted_sha256": sha256(text.encode()).hexdigest(), "start": raw_start, "end": raw_end})
    if recoveries:
        payload["commission_format_recovery"] = recoveries
    return payload


def restore_attachment_line_ranges(answer,payload):
    """Fill missing endpoints only from one explicitly written source range."""
    for index,request in enumerate(payload.get('material_requests') or []):
        for attachment,item in enumerate(request.get('archive_attachments') or []):
            if item.get('start_line') is not None and item.get('end_line') is not None:
                continue
            path=item.get('path')
            if not isinstance(path,str):continue
            pattern=r'`'+re.escape(path)+r'`\s*第\s*(\d+)(?:\s*[-–—~至]\s*(\d+))?\s*行'
            matches=list(re.finditer(pattern,answer))
            ranges={(int(m[1]),int(m[2] or m[1])) for m in matches}
            if len(ranges)!=1:continue
            start,end=next(iter(ranges))
            if any(item.get(key) is not None and item[key]!=value for key,value in (('start_line',start),('end_line',end))):
                continue
            original={key:item.get(key) for key in ('start_line','end_line')}
            item.update(start_line=start,end_line=end)
            payload.setdefault('attachment_line_recovery',[]).append({'request_index':index,'attachment_index':attachment,
                'path':path,'original':original,'source':matches[0][0],'start':matches[0].start(),'end':matches[0].end()})


def _terminal_punctuation_span(answer, text):
    punctuation = "。！？：；，.!?:;,"
    if len(text) < 8 or text[-1] not in punctuation:
        return None
    stem = text[:-1]
    if answer.count(stem) != 1:
        return None
    start = answer.index(stem)
    end = start + len(stem)
    if end >= len(answer) or answer[end] not in punctuation:
        return None
    return start, end + 1


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


def restore_tone_source(answer,payload,prose=None):
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
        _body_tone_edit(edit, prose, payload, index)
    return payload


def _body_tone_edit(edit, prose, payload, index):
    before = edit.get('before')
    if not prose or not isinstance(before, str) or before in prose:
        return
    plain, _ = _quote_projection(before, normalize_quotes=False)
    if plain == before or prose.count(plain) != 1:
        return
    for field in ('before', 'after'):
        original = edit.get(field)
        if isinstance(original, str):
            edit[field] = _quote_projection(original, normalize_quotes=False)[0]
    payload.setdefault('tone_presentation_recovery', []).append({
        'edit': index, 'projection': 'editor-blockquote-to-body', 'original_before': before})


def tone_text_matches_source(answer, text):
    if not isinstance(text, str) or not text.strip():
        return False
    return text in _quote_projection(answer, normalize_quotes=False)[0]


def restore_review_evidence(prose,payload):
    projected,offsets=_quote_projection(prose)
    for group in ('strengths','major_issues','optional_explorations','issue_progress'):
        for index,row in enumerate(payload.get(group) or []):
            evidence=row.get('evidence') if isinstance(row,dict) else None
            if not isinstance(evidence,str) or not evidence.strip() or evidence in prose:
                continue
            span=_literal_span(prose,evidence.strip(),projected,offsets) or _whitespace_evidence_span(prose,evidence)
            if span:
                row['evidence']=prose[span[0]:span[1]]
                payload.setdefault('review_format_recovery',[]).append({'group':group,'row':index,
                    'original':evidence,'body_start':span[0],'body_end':span[1],
                    'body_sha256':sha256(prose.encode('utf-8')).hexdigest()})
            else:
                _recover_quoted_prose(prose,payload,row,group,index,evidence)
    return payload


def _recover_quoted_prose(prose,payload,row,group,index,evidence):
    quoted=re.findall(r'“([^“”\n]+)”|"([^"\n]+)"',evidence)
    quotes={left or right for left,right in quoted if (left or right).strip() and prose.count(left or right)==1}
    if not quotes:
        return
    longest=max(map(len,quotes))
    choices=[quote for quote in quotes if len(quote)==longest]
    if len(choices)!=1:
        return
    quote=choices[0];row['evidence']=quote
    payload.setdefault('review_format_recovery',[]).append({'group':group,'row':index,
        'original':evidence,'body_start':prose.index(quote),'body_end':prose.index(quote)+len(quote),
        'body_sha256':sha256(prose.encode()).hexdigest(),'projection':'explicit-quoted-body-fragment'})


def _whitespace_evidence_span(prose,evidence):
    parts=re.split(r'\s+',evidence.strip())
    if len(parts)<2:
        return None
    matches=list(re.finditer(r'\s+'.join(map(re.escape,parts)),prose))
    return (matches[0].start(),matches[0].end()) if len(matches)==1 else None


def quoted_review_evidence(answer,evidence):
    if not isinstance(evidence,str) or not evidence.strip():
        return False
    if re.search(r'"evidence"\s*:\s*'+re.escape(json.dumps(evidence,ensure_ascii=False)),answer):
        return True
    if re.search(r'"path"\s*:\s*"/[^"\n]+/evidence"[^{}]*"value"\s*:\s*'
                 +re.escape(json.dumps(evidence,ensure_ascii=False)),answer):
        return True
    projected,offsets=_quote_projection(answer)
    span=_literal_span(answer,evidence.strip(),projected,offsets)
    if not span:
        return False
    if span[0]>0 and span[1]<len(answer) and answer[span[0]-1] in '\"\'“‘' and answer[span[1]] in '\"\'”’':
        return True
    line_start=answer.rfind('\n',0,span[0])+1
    prefix=answer[line_start:span[0]]
    return answer[span[0]:span[1]].lstrip().startswith('>') or bool(re.search(r'(?:^\s*>|(?:原文|证据|引句|引用)\s*[:：])',prefix))
