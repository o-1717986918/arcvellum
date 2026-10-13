"""Exact evidence comes from an author-selected paragraph of the frozen current body."""
from hashlib import sha256
from copy import deepcopy
import re
from .natural_transport_repair import NaturalExtractionError


def prose_evidence_source(prose):
    blocks=[]
    for index,match in enumerate(re.finditer(r'\S[^\n]*(?:\n(?!\s*\n)[^\n]*)*',prose),1):
        blocks.append({'id':f'p{index:04d}','text':match[0],'start':match.start(),'end':match.end()})
    return {'sha256':sha256(prose.encode()).hexdigest(),'blocks':blocks}


def resolve_evidence_patches(reply,prose,allowed):
    result=deepcopy(reply)
    for patch in result.get('patches') or []:
        path=patch.get('path') if isinstance(patch,dict) else None
        value=patch.get('value') if isinstance(patch,dict) else None
        if path in allowed and path.split('/')[1] in {'strengths', 'major_issues', 'optional_explorations',
                                                     'issue_progress', 'consistency_checks'}:
            patch['value'] = _nested_review_evidence(value, prose_evidence_source(prose), allowed)
            value = patch['value']
        if path not in allowed or not path.endswith('/evidence') or not isinstance(value,dict):
            continue
        source=prose_evidence_source(prose)
        block=next((row for row in source['blocks'] if row['id']==value.get('prose_block')),None)
        if set(value)!={'prose_sha256','prose_block'} or value.get('prose_sha256')!=source['sha256'] or block is None:
            raise NaturalExtractionError('evidence reference does not match the frozen current prose',fields=allowed)
        patch['value']=block['text']
    return result


def _nested_review_evidence(value, source, allowed):
    if isinstance(value, list):
        return [_nested_review_evidence(row, source, allowed) for row in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {'prose_sha256', 'prose_block'}:
        block = next((row for row in source['blocks'] if row['id'] == value['prose_block']), None)
        if value['prose_sha256'] != source['sha256'] or block is None:
            raise NaturalExtractionError('review evidence reference does not match current prose', fields=allowed)
        return block['text']
    return {key: _nested_review_evidence(item, source, allowed)
            if key in {'evidence', 'counter_excerpt'} else item for key, item in value.items()}
