"""Correct annotation block numbers only from two globally unique source anchors."""
from literary_engineering_studio_engine.public.literary import natural_source_index


def recover_reference_ranges(raw,answer):
    index=natural_source_index(answer)
    if raw.get('source_sha256')!=index['sha256']:
        return raw
    records=[]
    value=_walk(raw,answer,index,records)
    if records:
        value['source_block_recovery']=records
    return value


def _walk(value,answer,index,records):
    if isinstance(value,list):
        return [_walk(row,answer,index,records) for row in value]
    if not isinstance(value,dict):
        return value
    if set(value)=={'$source'} and isinstance(value['$source'],dict):
        return {'$source':_recover(value['$source'],answer,index,records)}
    return {key:_walk(row,answer,index,records) for key,row in value.items()}


def _recover(ref,answer,index,records):
    anchors=[ref.get('start_anchor'),ref.get('end_anchor')]
    if ref.get('sha256',index['sha256'])!=index['sha256'] or not all(isinstance(a,str) and a for a in anchors):
        return ref
    first,last=ref.get('first_block'),ref.get('last_block') or ref.get('first_block')
    if _current_range_contains(index,answer,first,last,anchors):
        return ref
    if not all(answer.count(anchor)==1 for anchor in anchors):
        return ref
    start,end=answer.index(anchors[0]),answer.index(anchors[1])+len(anchors[1])
    if end<=start:
        return ref
    covered=[row for row in index['blocks'] if row['end']>start and row['start']<end]
    if not covered:
        return ref
    corrected={**ref,'first_block':covered[0]['id'],'last_block':covered[-1]['id']}
    records.append({'original_first':first,'original_last':last,'corrected_first':corrected['first_block'],
        'corrected_last':corrected['last_block'],'source_sha256':index['sha256'],'start':start,'end':end})
    return corrected


def _current_range_contains(index,answer,first,last,anchors):
    blocks={row['id']:row for row in index['blocks']}
    if first not in blocks or last not in blocks:
        return False
    region=answer[blocks[first]['start']:blocks[last]['end']]
    return all(region.count(anchor)==1 for anchor in anchors)
