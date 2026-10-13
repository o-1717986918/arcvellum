"""Detach explicitly labelled technical notes while retaining the exact story prefix."""
from copy import deepcopy
from hashlib import sha256
import re


def detach_creator_notes(payload):
    prose=payload.get('prose')
    if not isinstance(prose,str):
        return payload
    match=re.search(r'(?m)^#{1,6}[ \t]+(?:[一二三四五六七八九十\d]+[、.．· \t-]+)?(?:素材使用札记|素材取舍札记|取舍札记|创作札记)[^\n]*$',prose)
    if match is None or not re.search(r'v2:[\w-]+:[1-9]\d*',prose[match.end():]):
        return payload
    body=prose[:match.start()].rstrip()
    if body.endswith('\n---'):
        body=body[:-4].rstrip()
    if not body:
        return payload
    result=deepcopy(payload)
    result['prose']=body
    result['detached_creator_notes']=prose[len(body):]
    result['prose_boundary_recovery']={'original_prose_sha256':sha256(prose.encode()).hexdigest(),
        'body_sha256':sha256(body.encode()).hexdigest(),'operation':'literal-prefix-before-explicit-material-notes'}
    return result
