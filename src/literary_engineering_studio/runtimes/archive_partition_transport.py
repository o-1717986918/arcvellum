"""Canonicalize explicitly labelled attachment partition names, retaining their source labels."""
_ALIASES = {
    'known': 'known', 'character_known': 'known', 'character_knowledge': 'known',
    'role_known_archive': 'known', '角色可知区': 'known', '角色可知': 'known',
    'reference': 'reference', 'creator_reference': 'reference', 'director_reference_archive': 'reference',
    '主创参考区': 'reference', '主创参考': 'reference', '仅供扮演参考': 'reference',
}


def normalize_archive_partitions(payload):
    for request in payload.get('material_requests') or []:
        for item in request.get('archive_attachments') or []:
            if not isinstance(item,dict):
                continue
            prior = item.get('knowledge')
            canonical = _ALIASES.get(prior) if isinstance(prior,str) else None
            if request.get('kind') != 'actor':
                canonical = ''
            if canonical is not None and canonical != prior:
                item['knowledge'] = canonical
                payload.setdefault('attachment_partition_recovery',[]).append({'kind':request.get('kind'),
                    'target':request.get('target'),'path':item.get('path'),'original':prior,'canonical':canonical})
    return payload
