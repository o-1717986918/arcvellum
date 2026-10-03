"""File adapter for private character chats and creator-authored card snapshots."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from ..project_agent.scope import work_id_for_root

class FileCharacterChatRepository:
    def __init__(self, data_root: Path):
        self.root = data_root.resolve()

    def _directory(self, project_root: Path) -> Path:
        return self.root / "character-chat" / work_id_for_root(project_root.resolve())

    def _path(self, project_root: Path, session_id: str) -> Path:
        if str(UUID(session_id)) != session_id:
            raise ValueError("invalid character chat session ID")
        return self._directory(project_root) / (session_id + ".json")

    def list(self, project_root: Path) -> list[dict[str, Any]]:
        items = []
        for path in self._directory(project_root).glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append({key: data[key] for key in ("session_id", "target", "created_at", "updated_at")})
        return sorted(items, key=lambda item: item["updated_at"], reverse=True)

    def read(self, project_root: Path, session_id: str) -> dict[str, Any]:
        data = json.loads(self._path(project_root, session_id).read_text(encoding="utf-8"))
        if data.get("schema") != "arcvellum/character-chat/v1" or data.get("project_root") != str(project_root.resolve()):
            raise ValueError("character chat belongs to a different work")
        return data

    def save(self, project_root: Path, session: dict[str, Any]) -> None:
        path = self._path(project_root, session["session_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def cards(self, project_root: Path) -> list[dict[str, Any]]:
        directory = self.root / "character-card-library" / work_id_for_root(project_root.resolve())
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))]

