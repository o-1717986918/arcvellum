"""Transaction-local, read-only candidate files for the scene creator."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class SceneMaterialLibrary:
    SCHEMA = "arcvellum/scene-material-library/v1"

    def __init__(self, root: Path):
        self.root = root

    def write(self, rendered_materials: str) -> str:
        """Persist visible candidates, then return a prose-free lookup directory."""

        packet = _material_packet(rendered_materials)
        entries = _entries(packet)
        self.root.mkdir(parents=True, exist_ok=True)
        index: list[dict[str, str]] = []
        for entry in entries:
            candidate_id = entry["candidate_id"]
            filename = hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:24] + ".json"
            _atomic_json(self.root / filename, entry)
            index.append({key: entry[key] for key in ("candidate_id", "kind", "target", "purpose", "scene_moment")}
                         | ({"basis": entry["basis"]} if entry.get("basis") else {})
                         | {"file": filename})
        _atomic_json(self.root / "index.json", {"schema": self.SCHEMA, "entries": index})
        return self.index_prompt()

    def index_prompt(self) -> str:
        path = self.root / "index.json"
        if not path.is_file():
            return "本场尚无取材文件；如需一级素材，请按文学目的请求相应 agent。"
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema") != self.SCHEMA:
            raise ValueError("scene material index is invalid")
        rows = value.get("entries")
        if not isinstance(rows, list):
            raise ValueError("scene material entries are invalid")
        visible = [{key: row[key] for key in ("candidate_id", "kind", "target", "purpose", "scene_moment")}
                   | ({"basis": row["basis"]} if row.get("basis") else {}) for row in rows]
        return "可用素材文件目录（仅元数据，不含候选正文）：" + json.dumps(visible, ensure_ascii=False, separators=(",", ":"))


def _material_packet(rendered_materials: str) -> dict[str, Any]:
    if not rendered_materials:
        return {}
    try:
        value = json.loads(rendered_materials.rsplit("\n", 1)[1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise ValueError("scene material packet is malformed") from exc
    if not isinstance(value, dict):
        raise ValueError("scene material packet must be an object")
    return value


def _entries(packet: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    context = {key: packet.get(key) for key in ("beats", "director_turns", "material_notices")}
    if any(context.values()):
        entries.append(_entry("scene-context", "scene-context", "", "", "", context))
    entries.extend(_actor_entries(packet.get("actor_entries")))
    entries.extend(_environment_entries(packet.get("environment_candidates")))
    entries.extend(_description_entries(packet.get("description_candidates")))
    ids = [item["candidate_id"] for item in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("scene material candidate IDs must be unique")
    return entries


def _actor_entries(actors: Any) -> list[dict[str, Any]]:
    entries = []
    for actor in actors or []:
        if isinstance(actor, dict) and actor.get("entry_id"):
            entries.append(_entry(str(actor["entry_id"]), "actor", str(actor.get("speaker") or ""), "", "", actor))
    return entries


def _environment_entries(environment: Any) -> list[dict[str, Any]]:
    if not isinstance(environment, dict):
        return []
    entries = []
    for passage in environment.get("passages") or []:
        if isinstance(passage, dict) and passage.get("candidate_id"):
            entries.append(_entry(str(passage["candidate_id"]), "environment", "", "", "", passage))
    return entries


def _description_entries(candidates: Any) -> list[dict[str, Any]]:
    entries = []
    for candidate in candidates or []:
        if isinstance(candidate, dict) and candidate.get("candidate_id"):
            entry = _entry(str(candidate["candidate_id"]), str(candidate.get("kind") or "description"),
                           str(candidate.get("target") or ""), str(candidate.get("purpose") or ""),
                           str(candidate.get("scene_moment") or ""), candidate)
            if candidate.get("kind") == "event-narration":
                entry["basis"] = str(candidate.get("basis") or "")
            entries.append(entry)
    return entries


def _entry(candidate_id: str, kind: str, target: str, purpose: str, scene_moment: str,
           content: dict[str, Any]) -> dict[str, Any]:
    if not candidate_id or len(candidate_id) > 120:
        raise ValueError("scene material candidate ID is invalid")
    return {"schema": "arcvellum/scene-material/v1", "candidate_id": candidate_id,
            "kind": kind, "target": target, "purpose": purpose, "scene_moment": scene_moment,
            "content": content}


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


__all__ = ["SceneMaterialLibrary"]
