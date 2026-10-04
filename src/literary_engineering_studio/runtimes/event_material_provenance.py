"""Source-bound event metadata shared by extraction and candidate admission."""
from hashlib import sha256


def recover_event_source_status(answer, payload):
    digest = sha256(answer.encode("utf-8")).hexdigest()
    for index, candidate in enumerate(payload.get("candidates") or []):
        if not isinstance(candidate, dict):
            continue
        basis = candidate.get("basis")
        recognized = basis is None or isinstance(basis, str) and basis in {"", "confirmed", "attributed", "proposed"}
        if recognized and not str(candidate.get("source_note") or "").strip():
            payload.setdefault("source_status_recovery", []).append({"candidate_index": index,
                "extracted_basis": candidate.get("basis"), "reason": "missing-source-note", "source_sha256": digest})
            candidate["basis"] = "proposed"
            candidate["source_note"] = f"本次事件取材的创作候选，档案依据待主创核实。来源原文 SHA-256：{digest}"
    return payload


def event_fields(item):
    basis = str(item.get("basis") or "")
    note = str(item.get("source_note") or "").strip()
    if basis not in {"confirmed", "attributed", "proposed"} or not note:
        raise ValueError("event candidate needs basis and source_note")
    return {"basis": basis, "source_note": note[:500]}
