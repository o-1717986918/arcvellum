"""Versioned work-level scene creator persona, separate from Canon and prose."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from ..project_agent.scope import work_id_for_root


_SCHEMA = "arcvellum/scene-creator-persona/v1"


class CreatorPersonaStore:
    def __init__(self, data_root: Path):
        self._root = data_root.expanduser().resolve() / "scene-creator-personas"

    def _path(self, project_root: Path) -> Path:
        root = project_root.expanduser().resolve()
        if not (root / "project.yaml").is_file():
            raise ValueError("creator persona requires a work project")
        return self._root / (work_id_for_root(root) + ".json")

    def source_digest(self, project_root: Path) -> str:
        root = project_root.expanduser().resolve()
        sources = [root / "project.yaml", root / "workflow/studio/user_directions.jsonl"]
        digest = sha256()
        for path in sources:
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes() if path.is_file() else b"<missing>")
        return digest.hexdigest()

    def direction_digest(self, project_root: Path) -> str:
        path = project_root.expanduser().resolve() / "workflow/studio/user_directions.jsonl"
        return sha256(path.read_bytes() if path.is_file() else b"<missing>").hexdigest()

    def read(self, project_root: Path) -> dict[str, Any]:
        path = self._path(project_root)
        if not path.is_file():
            return {"schema": _SCHEMA, "status": "missing", "active_version": 0,
                    "source_digest": self.source_digest(project_root), "versions": []}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema") != _SCHEMA:
            raise ValueError("creator persona record has an unknown schema")
        return {**payload, "status": "ready", "source_digest": self.source_digest(project_root)}

    def read_current(self, project_root: Path) -> dict[str, Any]:
        payload = self.read(project_root)
        versions = payload.get("versions") or []
        return {"schema": _SCHEMA, "status": payload["status"],
                "active_version": payload["active_version"],
                "source_digest": payload["source_digest"],
                "active": versions[-1] if versions else None,
                "history": [{"version": item["version"], "created_at": item["created_at"],
                             "source_digest": item["source_digest"]} for item in versions]}

    def save(self, project_root: Path, text: str, *, reason: str) -> dict[str, Any]:
        clean = text.strip()
        reason = reason.strip()
        if not 20 <= len(clean) <= 4000 or not 6 <= len(reason) <= 1000:
            raise ValueError("creator persona needs bounded content and a reason")
        path = self._path(project_root)
        prior = self.read(project_root)
        source_digest = self.source_digest(project_root)
        direction_digest = self.direction_digest(project_root)
        versions = list(prior.get("versions") or [])
        if versions and versions[-1].get("direction_digest") == direction_digest:
            raise ValueError("creator persona changes require a changed user direction")
        version = len(versions) + 1
        record = {"version": version, "text": clean, "reason": reason,
                  "source_digest": source_digest, "direction_digest": direction_digest,
                  "created_at": datetime.now(timezone.utc).isoformat()}
        versions.append(record)
        payload = {"schema": _SCHEMA, "active_version": version, "versions": versions}
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return record


__all__ = ["CreatorPersonaStore"]
