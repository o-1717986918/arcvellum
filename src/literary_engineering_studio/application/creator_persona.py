"""Versioned work-level scene creator persona, separate from Canon and prose."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from pathlib import Path
from typing import Any

from ..project_agent.scope import work_id_for_root
from .direction_provenance import author_intent_bytes


_SCHEMA = "arcvellum/scene-creator-persona/v1"


def persona_text_is_instruction(text):
    return isinstance(text, str) and not re.search(r"<[^>]*(?:DSML|tool_call|invoke)[^>]*>", text, re.IGNORECASE)


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
            digest.update(author_intent_bytes(root) if path.name == "user_directions.jsonl" else path.read_bytes() if path.is_file() else b"<missing>")
        return digest.hexdigest()

    def direction_digest(self, project_root: Path) -> str:
        path = project_root.expanduser().resolve() / "workflow/studio/user_directions.jsonl"
        return sha256(author_intent_bytes(path.parent.parent.parent)).hexdigest()

    def read(self, project_root: Path) -> dict[str, Any]:
        path = self._path(project_root)
        if not path.is_file():
            return {"schema": _SCHEMA, "status": "missing", "active_version": 0,
                    "source_digest": self.source_digest(project_root), "versions": []}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema") != _SCHEMA:
            raise ValueError("creator persona record has an unknown schema")
        versions = payload.get("versions") or []
        status = "ready" if versions and persona_text_is_instruction(versions[-1].get("text")) else "needs-repair"
        review_path = path.with_suffix(".review.json")
        review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.is_file() else {}
        if review.get("version") == payload["active_version"] and review.get("decision") == "revise":
            status = "needs-repair"
        return {**payload, "status": status, "literary_review": review, "source_digest": self.source_digest(project_root)}

    def read_current(self, project_root: Path) -> dict[str, Any]:
        payload = self.read(project_root)
        versions = payload.get("versions") or []
        return {"schema": _SCHEMA, "status": payload["status"],
                "active_version": payload["active_version"],
                "source_digest": payload["source_digest"],
                "active": versions[-1] if versions and payload["status"] == "ready" else None,
                "last_generated": versions[-1] if versions else None,
                "literary_review": payload.get("literary_review", {}),
                "history": [{"version": item["version"], "created_at": item["created_at"],
                             "source_digest": item["source_digest"], "text": item["text"], "reason": item["reason"]} for item in versions]}

    def save(self, project_root: Path, text: str, *, reason: str) -> dict[str, Any]:
        clean = text.strip()
        reason = reason.strip()
        if not 20 <= len(clean) <= 4000 or not 6 <= len(reason) <= 1000:
            raise ValueError("creator persona needs bounded content and a reason")
        if not persona_text_is_instruction(clean):
            raise ValueError("creator persona contains tool-call transport instead of persona instructions")
        path = self._path(project_root)
        prior = self.read(project_root)
        source_digest = self.source_digest(project_root)
        direction_digest = self.direction_digest(project_root)
        versions = list(prior.get("versions") or [])
        if versions and prior["status"] == "ready" and versions[-1].get("direction_digest") == direction_digest:
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

    def request_repair(self, project_root, *, expected_version, reason, evidence):
        prior = self.read(project_root)
        if prior['active_version'] != expected_version or not reason.strip() or not evidence:
            raise ValueError('persona repair requires the current version and literary evidence')
        review = {'schema': 'arcvellum/creator-persona-literary-review/v1', 'version': expected_version,
                  'decision': 'revise', 'reason': reason, 'evidence': evidence, 'reviewer': 'code-agent'}
        path = self._path(project_root).with_suffix('.review.json')
        path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding='utf-8')
        return self.read_current(project_root)

    def save_as_author(self, project_root, text, *, reason, expected_version):
        from .project_manager import record_direction
        if self.read(project_root)['active_version'] != expected_version:
            raise ValueError('主创人格版本已变化，请刷新后再保存。')
        if not 20 <= len(text.strip()) <= 4000 or not 6 <= len(reason.strip()) <= 1000 or not persona_text_is_instruction(text):
            raise ValueError('请填写有效的人格正文与修改理由。')
        record_direction(project_root, '主创人格设定：\n' + text.strip(), source_kind='author_intent',
                         evidence=['作者在作品创作链设置中保存了这份人格正文与修改理由：' + reason.strip()])
        self.save(project_root, text, reason=reason)
        return self.read_current(project_root)


__all__ = ["CreatorPersonaStore"]
