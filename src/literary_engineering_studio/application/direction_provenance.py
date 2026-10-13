"""Separate author intent, agent interpretation and continuity evidence."""
from hashlib import sha256
import json

KINDS = {"author_intent", "agent_judgment", "continuity"}


def classify_direction(record):
    kind = record.get("source_kind") or ("author_intent" if record.get("actor", "user") == "user" else "agent_judgment")
    ident = record.get("record_id") or sha256(json.dumps(record, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
    return {**record, "source_kind": kind, "record_id": ident}


def project_direction_records(records):
    rows = [classify_direction(row) for row in records]
    replaced = {ident: row["record_id"] for row in rows for ident in row.get("supersedes", [])}
    return [{**row, "status": "superseded" if row["record_id"] in replaced else "active",
             "superseded_by": replaced.get(row["record_id"], "")} for row in rows]


def author_intent_bytes(root):
    path = root / "workflow/studio/user_directions.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []
    selected = [{"message": row["message"], "record_id": row["record_id"]}
                for row in project_direction_records(rows) if row["source_kind"] == "author_intent" and row["status"] == "active"]
    return json.dumps(selected, ensure_ascii=False, sort_keys=True).encode()
