"""Exact evidence comes from an author-selected paragraph of the frozen current body."""
from hashlib import sha256
from copy import deepcopy
import re
from .natural_transport_repair import NaturalExtractionError

_REVIEW_FIELDS = {'strengths', 'major_issues', 'optional_explorations', 'issue_progress', 'consistency_checks'}


def prose_evidence_source(prose):
    blocks=[]
    for index,match in enumerate(re.finditer(r'\S[^\n]*(?:\n(?!\s*\n)[^\n]*)*',prose),1):
        blocks.append({'id':f'p{index:04d}','text':match[0],'start':match.start(),'end':match.end()})
    return {'sha256':sha256(prose.encode()).hexdigest(),'blocks':blocks}


def resolve_evidence_patches(reply,prose,allowed):
    result=deepcopy(reply)
    source=prose_evidence_source(prose)
    issues,fields=[],[]
    for patch in result.get('patches') or []:
        path=patch.get('path') if isinstance(patch,dict) else None
        value=patch.get('value') if isinstance(patch,dict) else None
        if path not in allowed:
            continue
        if path.split('/')[1] in _REVIEW_FIELDS or path.endswith('/evidence'):
            patch['value']=_resolve_review_evidence(value,source,path,issues,fields)
    _raise_reference_errors(issues,fields)
    return result


def resolve_review_record_evidence(record, prose):
    issues,fields=[],[]
    result=_resolve_review_evidence(record,prose_evidence_source(prose),'',issues,fields)
    _raise_reference_errors(issues,fields)
    return result


def _resolve_review_evidence(value, source, path, issues, fields):
    if isinstance(value, list):
        return [_resolve_review_evidence(row,source,path+'/'+str(index),issues,fields)
                for index,row in enumerate(value)]
    if not isinstance(value, dict):
        return value
    if 'prose_sha256' in value or 'prose_block' in value:
        return _resolve_reference(value,source,path,issues,fields)
    return {key: _resolve_review_evidence(item,source,path+'/'+key,issues,fields)
            if key in {'evidence','counter_excerpt'} or not path and key in _REVIEW_FIELDS else deepcopy(item)
            for key,item in value.items()}


def _resolve_reference(value, source, path, issues, fields):
    if set(value) != {'prose_sha256','prose_block'}:
        issues.append(path+': evidence reference requires prose_sha256 and prose_block')
        fields.append(path)
        return deepcopy(value)
    block=next((row for row in source['blocks'] if row['id']==value['prose_block']),None)
    if value['prose_sha256']!=source['sha256']:
        issues.append(path+': evidence reference does not match current prose; current prose_sha256='+source['sha256'])
        fields.append(path+'/prose_sha256')
    if block is None:
        issues.append(path+': evidence paragraph is absent from current prose')
        fields.append(path+'/prose_block')
    if value['prose_sha256']!=source['sha256'] or block is None:
        return deepcopy(value)
    return block['text']


def _raise_reference_errors(issues, fields):
    if issues:
        raise NaturalExtractionError('\n'.join(issues),fields=tuple(dict.fromkeys(fields)))
