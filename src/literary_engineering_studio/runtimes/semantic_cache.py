"""Stable scene cache identities bind literary inputs, excluding execution effort."""
from hashlib import sha256
import json


def semantic_cache_digest(phase, *, brief, result, verification, briefing, snapshot,
                          sources=None, continuity=None, review=None, attempt=None):
    value = {"processor":"cost-v4","phase":phase,"brief":brief.to_dict(),
        "result":result.to_dict(),"verification":verification.to_dict(),
        "briefing":briefing,"prompt_contract":snapshot.get("digest"),
        "prompt_texts":snapshot.get("texts"),"sources":sources,
        "continuity":{key:value for key,value in (continuity or {}).items()
                      if key not in {"completed_reviews","completed_revisions"}},
        "review":review,"attempt":attempt}
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:24]


def prior_review_context(continuity):
    previous = continuity.get("previous")
    return {"previous":previous,"open_issues":[row for row in (previous or {}).get("issues",[])
                                               if row.get("status") != "resolved"],
            "ambiguous_legacy_reviews":continuity.get("ambiguous_legacy_reviews",[])}
