"""Canonicalize explicitly labelled attachment partition names, retaining their source labels."""
from .natural_transport_repair import NaturalSourceClarificationError
import re
_ALIASES = {
    'known': 'known', 'character_known': 'known', 'character_knowledge': 'known',
    'role_known_archive': 'known', '角色可知区': 'known', '角色可知': 'known',
    '已知': 'known',
    'reference': 'reference', 'creator_reference': 'reference', 'director_reference_archive': 'reference',
    '主创参考区': 'reference', '主创参考': 'reference', '仅供扮演参考': 'reference',
    '参考': 'reference',
}


def require_source_partition_choice(answer, payload):
    fields=[]
    for request_index,request in enumerate(payload.get('material_requests') or []):
        if request.get('kind') == 'actor':
            for attachment_index,item in enumerate(request.get('archive_attachments') or []):
                value = item.get('knowledge')
                if _partition(value) is None:
                    fields.append(f"/material_requests/{request_index}/archive_attachments/{attachment_index}/knowledge")
    if fields:
        raise NaturalSourceClarificationError('actor attachment must state known or reference; clarify the original source partition',
            fields=tuple(fields),payload=payload)


def _partition(value):
    if not isinstance(value,str):
        return None
    if value in _ALIASES:
        return _ALIASES[value]
    # An explicit label may carry its author's rationale after a colon/parenthesis.
    match=re.match(r'^(known|reference|角色可知区|角色可知|已知|主创参考区|主创参考|参考)(?=\s*[:：（(])',value)
    return _ALIASES.get(match[1]) if match else None


def normalize_archive_partitions(payload):
    for request in payload.get('material_requests') or []:
        for item in request.get('archive_attachments') or []:
            if not isinstance(item,dict):
                continue
            prior = item.get('knowledge')
            canonical = _partition(prior)
            if request.get('kind') != 'actor':
                canonical = ''
            if canonical is not None and canonical != prior:
                item['knowledge'] = canonical
                payload.setdefault('attachment_partition_recovery',[]).append({'kind':request.get('kind'),
                    'target':request.get('target'),'path':item.get('path'),'original':prior,'canonical':canonical})
    return payload
