"""Complete, read-only material inspection for both scene transaction runtimes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

from ..application.scene_transaction import SceneTransaction


def material_directory(data_root: Path, transaction_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", transaction_id):
        raise ValueError("invalid scene transaction identity")
    root = (data_root / "scene-transactions").resolve()
    directory = (root / transaction_id).resolve()
    if not directory.is_relative_to(root):
        raise ValueError("scene material path escapes transaction storage")
    return directory


def scene_material_detail(data_root: Path, transactions: Iterable[SceneTransaction], transaction_id: str) -> dict[str, Any]:
    transaction = next((item for item in transactions if item.transaction_id == transaction_id), None)
    if transaction is None:
        raise ValueError("scene material does not belong to this project")
    directory = material_directory(data_root, transaction_id)
    warnings: list[str] = []
    memory = _object(directory / "scene_creator_memory.json", directory, warnings)
    if not memory:
        memory = _object(directory / "v2" / "scene_creator_memory.json", directory, warnings)
    decisions = {row.get("candidate_id"): row for row in memory.get("material_decisions", []) if isinstance(row, dict)}
    calls = _v2_calls(directory, warnings)
    if not calls:
        calls = _legacy_calls(directory, warnings)
    materials = _v2_materials(calls, decisions) if any(call.get("runtime") == "v2" for call in calls) else _legacy_materials(directory, calls, decisions, warnings)
    return {"schema": "arcvellum/scene-material-inspection/v1", "transaction_id": transaction_id,
            "scene_id": transaction.scene_id, "intent": memory.get("intent"),
            "calls": calls, "materials": materials, "warnings": warnings,
            "transport": _transport_summary(directory, warnings),
            "candidate_count": len(materials)}


def _object(path: Path, directory: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        return {}
    if not path.resolve().is_relative_to(directory.resolve()):
        warnings.append(f"无法读取越出交易目录的记录：{path.name}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        warnings.append(f"记录暂时无法读取：{path.name}")
        return {}
    return value if isinstance(value, dict) else {}


def _transport_summary(directory, warnings):
    records = []
    for path in sorted(directory.glob('**/*.transport.json')):
        record = _object(path, directory, warnings)
        if record.get('schema') == 'arcvellum/natural-transport/v1':
            records.append({key: record.get(key) for key in ('record_id', 'source_sha256', 'operation', 'mode',
                'initial_mode', 'model_calls', 'reuse_count', 'requested_thinking', 'error')})
    if not records:
        return None
    return {'records': records, 'model_calls': sum(row['model_calls'] or 0 for row in records),
            'reuse_count': sum(row['reuse_count'] or 0 for row in records),
            'local_records': sum(row['initial_mode'] == 'local' for row in records)}


def _v2_calls(directory: Path, warnings: list[str]) -> list[dict[str, Any]]:
    calls = []
    for path in sorted((directory / "v2" / "calls").glob("*.json")):
        record = _object(path, directory, warnings)
        request = record.get("request")
        if not isinstance(request, dict):
            continue
        calls.append({"call_id": str(record.get("request_id") or path.stem), "runtime": "v2",
                      "sequence": record.get("sequence", 0), "request": _request(request),
                      "attachments": record.get("attachment_manifest", []),
                      "raw_response": str(record.get("answer") or ""),
                      "candidates": record.get("candidates", [])})
    return sorted(calls, key=lambda item: item["sequence"])


def _request(request: dict[str, Any]) -> dict[str, Any]:
    return {key: request.get(key, "") for key in
            ("kind", "target", "purpose", "scene_moment", "cue", "author_prompt", "style_direction")}


def _legacy_calls(directory: Path, warnings: list[str]) -> list[dict[str, Any]]:
    calls: dict[str, dict[str, Any]] = {}
    paths = sorted((directory / "creator-answers").glob("*.md"), key=lambda path: path.stat().st_mtime)
    for path in paths:
        answer = _object(path, directory, warnings)
        for request in answer.get("material_requests", []):
            if not isinstance(request, dict):
                continue
            digest = hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]
            calls.setdefault(digest, {"call_id": digest, "runtime": "v1", "sequence": len(calls) + 1,
                                      "request": _request(request), "attachments": [], "raw_response": ""})
    _received_calls(directory, calls, warnings)
    return list(calls.values())


def _received_calls(directory: Path, calls: dict[str, dict[str, Any]], warnings: list[str]) -> None:
    for path in sorted(directory.glob("*.received.json"), key=lambda path: path.stat().st_mtime):
        record = _object(path, directory, warnings)
        request = record.get("request")
        if not isinstance(request, dict):
            continue
        projected = _request(request)
        existing = next((call for call in calls.values() if call["request"] == projected), None)
        if existing is None:
            existing = {"call_id": path.stem, "runtime": "v1", "sequence": len(calls) + 1,
                        "request": projected, "attachments": []}
            calls[path.stem] = existing
        existing["raw_response"] = str(record.get("answer") or "")
        existing["delivery_status"] = "validated" if path.with_name(path.name.replace(".received.json", ".json")).is_file() else "received"


def _v2_materials(calls: list[dict[str, Any]], decisions: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for call in calls:
        for candidate in call.pop("candidates", []):
            if isinstance(candidate, dict):
                row = _material(candidate, call["request"], decisions)
                result.append({**row, "call_id": call["call_id"], "attachments": call["attachments"]})
    return result


def _legacy_materials(directory: Path, calls: list[dict[str, Any]], decisions: dict[str, Any], warnings: list[str]) -> list[dict[str, Any]]:
    entries = _indexed_materials(directory, warnings)
    entries.extend(_session_materials(directory, warnings))
    result, seen = [], set()
    for entry in entries:
        content = entry.get("content", entry)
        if not isinstance(content, dict):
            continue
        digest = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        identity = (content.get("candidate_id", content.get("entry_id")), digest)
        if identity in seen:
            continue
        seen.add(identity)
        request = {**entry, "kind": entry.get("kind", content.get("kind", "actor")),
                   "target": entry.get("target", content.get("speaker", ""))}
        call = _matching_call(calls, request)
        if call:
            request = {**call["request"], **{key: value for key, value in request.items() if value}}
        result.append({**_material(content, request, decisions), "call_id": call["call_id"] if call else "",
                       "content_sha256": digest, "attachments": []})
    return result


def _matching_call(calls: list[dict[str, Any]], request: dict[str, Any]) -> dict[str, Any] | None:
    matching = [call for call in calls if all(not request.get(key) or call["request"].get(key) == request[key]
                                             for key in ("kind", "target", "purpose", "scene_moment"))]
    return matching[0] if len(matching) == 1 else None


def _indexed_materials(directory: Path, warnings: list[str]) -> list[dict[str, Any]]:
    entries = []
    index = _object(directory / "materials" / "index.json", directory, warnings)
    for item in index.get("entries", []):
        if not isinstance(item, dict) or item.get("kind") == "scene-context":
            continue
        filename = str(item.get("file") or "")
        if not re.fullmatch(r"[a-f0-9]{24}\.json", filename):
            warnings.append(f"素材文件索引无效：{item.get('candidate_id', '')}")
            continue
        value = _object(directory / "materials" / filename, directory, warnings)
        if value.get("candidate_id") != item.get("candidate_id"):
            warnings.append(f"素材与索引不一致：{item.get('candidate_id', '')}")
            continue
        entries.append(value)
    return entries


def _session_materials(directory: Path, warnings: list[str]) -> list[dict[str, Any]]:
    entries = []
    for path in sorted(directory.glob("performance-interaction-session-*.json")):
        state = _object(path, directory, warnings)
        for actor in state.get("actor_entries", []):
            if isinstance(actor, dict):
                entries.append({"kind": "actor", "target": actor.get("speaker", ""), "content": actor})
        environment = state.get("environment", {})
        for candidate in environment.get("passages", []) if isinstance(environment, dict) else []:
            if isinstance(candidate, dict):
                entries.append({"kind": "environment", "content": candidate})
        for candidate in state.get("description_candidates", []):
            if isinstance(candidate, dict):
                entries.append(candidate)
    return entries


def _material(content: dict[str, Any], request: dict[str, Any], decisions: dict[str, Any]) -> dict[str, Any]:
    identity = str(content.get("candidate_id") or content.get("entry_id") or "")
    decision = decisions.get(identity, {})
    shared = {key: str(content.get(key) or request.get(key) or "") for key in ("kind", "target", "purpose", "scene_moment")}
    fields = {key: str(content.get(key) or "") for key in
              ("spoken", "first_person_action", "private_impulse", "focus", "basis", "source_note")}
    return {"candidate_id": identity, **shared, **fields,
            "text": str(content.get("text") or content.get("description") or ""),
            "decision": str(decision.get("decision") or ""), "decision_reason": str(decision.get("reason") or ""),
            "usage_evidence":{key:decision.get(key) for key in
                ("source_excerpt","prose_excerpt","prose_location","indirect_use","body_sha256",
                 "source_excerpt_verified","prose_excerpt_verified","usage_evidence_status")},
            "complete": True}


__all__ = ["scene_material_detail", "material_directory"]
