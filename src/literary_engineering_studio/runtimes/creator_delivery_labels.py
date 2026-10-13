"""Resolve explicit participant names inside natural commission headings."""
import re

_LABEL = re.compile(
    r"(?:角色扮演器|角色扮演|扮演器|角色|人物描写器|人物描写|人物)"
    r"[（(](?:角色|人物)\s*[:：]\s*(?P<name>[^()（）]+)[）)]"
)


def resolve_creator_targets(payload, context):
    participants = (context.get("briefing") or {}).get("scene_brief", {}).get("participants", [])
    for index, request in enumerate(payload.get("material_requests") or []):
        if request.get("kind") not in {"actor", "character-description"}:
            continue
        original = request.get("target")
        match = _LABEL.fullmatch(original) if isinstance(original, str) else None
        if match and match["name"].strip() in participants:
            request["target"] = match["name"].strip()
            payload.setdefault("target_label_recovery", []).append({"request_index": index,
                "original": original, "participant": request["target"]})
    return payload


def recover_style_preset_id(answer, payload, context):
    original = payload.get('preset_id')
    allowed = context.get('preset_ids') or []
    if original in allowed:
        return True
    if not isinstance(original, str) or original not in answer:
        return False
    matches = [identifier for identifier in allowed if re.search(
        r'(?<![\w-])' + re.escape(identifier) + r'(?![\w-])', original)]
    if len(matches) != 1:
        return False
    payload['preset_id'] = matches[0]
    payload['preset_label_recovery'] = {'original': original, 'preset_id': matches[0],
        'start': answer.index(original), 'end': answer.index(original)+len(original)}
    return True


def recover_style_reference_ids(answer, payload, context):
    """Expand only an exact decorated ID list present in the original source."""
    allowed=set(context.get('reference_ids') or [])
    values=payload.get('reference_ids')
    if not isinstance(values,list):
        return
    recovered=[]
    for value in values:
        if isinstance(value,str) and value not in allowed and value in answer:
            plain=value.strip().strip('*`')
            ids=re.findall(r'(?<![A-Za-z0-9_])(?:R|S)\d{2}(?![A-Za-z0-9_])',plain)
            if ids and all(identifier in allowed for identifier in ids):
                recovered.extend(ids)
                payload.setdefault('reference_label_recovery',[]).append({'original':value,
                    'reference_ids':ids,'start':answer.index(value),'end':answer.index(value)+len(value)})
                continue
        recovered.append(value)
    payload['reference_ids']=list(dict.fromkeys(recovered)) if all(isinstance(item,str) for item in recovered) else recovered


def recover_style_list_format(answer,payload):
    for key in ('literary_mode','reason'):
        value=payload.get(key)
        if not isinstance(value,str) or value in answer or '\n' not in value:
            continue
        lines=value.splitlines()
        pattern=r'(?m)^'+r'\r?\n'.join(r'(?:[-*] )?'+re.escape(line) for line in lines)
        matches=list(re.finditer(pattern,answer))
        if len(matches)==1:
            match=matches[0]
            payload[key]=match[0]
            payload.setdefault('style_list_format_recovery',[]).append({'field':key,'original':value,
                'start':match.start(),'end':match.end()})
