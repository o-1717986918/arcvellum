"""Record observable source/body anchors without pretending to measure literary utility."""
from hashlib import sha256
import json
from pathlib import Path
from copy import deepcopy
from collections import Counter


def annotate_material_usage(payload, root):
    index_path = root / "index.json"
    if not index_path.is_file():
        return
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entries = {row["candidate_id"]:row for row in index.get("entries",[])}
    prose = str(payload.get("prose") or "")
    for row in payload.get("material_decisions") or []:
        entry = entries.get(row.get("candidate_id"))
        if not entry:
            continue
        path = (root / entry["file"]).resolve()
        if path.parent != root.resolve():
            raise ValueError("material evidence path escapes its library")
        source = json.loads(path.read_text(encoding="utf-8"))
        row["body_sha256"] = sha256(prose.encode()).hexdigest()
        _annotate_anchors(row,source,prose)


def save_material_usage_audit(prose, root, decisions, output_root):
    """Recheck inherited choices against this body without changing author judgments."""
    body_sha = sha256(prose.encode()).hexdigest()
    rows = deepcopy(decisions)
    annotate_material_usage({'prose': prose, 'material_decisions': rows}, root)
    index_path = root / 'index.json'
    index = json.loads(index_path.read_text(encoding='utf-8')) if index_path.is_file() else {}
    identifiers = {row['candidate_id'] for row in index.get('entries', [])}
    judged = {row['candidate_id'] for row in rows if row.get('candidate_id') in identifiers}
    report = {'schema': 'arcvellum/material-usage-audit/v1', 'body_sha256': body_sha,
              'candidate_count': len(identifiers), 'judged_count': len(judged),
              'unjudged_candidate_ids': sorted(identifiers - judged),
              'decisions': rows, 'decision_counts': dict(Counter(row.get('decision') for row in rows)),
              'evidence_counts': dict(Counter(row.get('usage_evidence_status', 'not-recorded') for row in rows)),
              'interpretation': 'Explicit choices and literal anchors are evidence, not a semantic usefulness or waste rate.'}
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / (body_sha + '.json')
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
    return report


def _annotate_anchors(row,source,prose):
    row["source_excerpt_verified"] = bool(row.get("source_excerpt") and
        any(row["source_excerpt"] in text for text in _source_texts(source.get("content",source))))
    row["prose_excerpt_verified"] = bool(row.get("prose_excerpt") and row["prose_excerpt"] in prose)
    row["usage_evidence_status"] = ("indirect-described" if row.get("indirect_use") else
        "anchors-verified" if row["source_excerpt_verified"] and row["prose_excerpt_verified"] else
        "anchors-unverified" if row.get("source_excerpt") or row.get("prose_excerpt") else "not-recorded")


def _source_texts(value):
    if isinstance(value,str):
        yield value
    elif isinstance(value,dict):
        for item in value.values():
            yield from _source_texts(item)
    elif isinstance(value,list):
        for item in value:
            yield from _source_texts(item)
