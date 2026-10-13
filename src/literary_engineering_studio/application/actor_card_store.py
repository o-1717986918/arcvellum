"""Versioned creator-authored work cards; committed experiences remain separate."""
from hashlib import sha256
import json
from pathlib import Path
from literary_engineering_studio_engine.public.literary import parse_actor_character_card
from literary_engineering_studio_engine.public.projects import atomic_write_batch
from ..project_agent.scope import work_id_for_root


class ActorCardStore:
    def __init__(self, data_root):
        self.data_root = Path(data_root).resolve()

    def save(self, root, payload, *, provenance):
        root = Path(root).resolve()
        card = parse_actor_character_card(payload, payload.get("target", ""))
        digest = sha256(json.dumps(card.to_dict(), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        key = sha256(card.target.encode()).hexdigest()[:24]
        row = {"schema": "arcvellum/work-actor-card/v1", "card": card.to_dict(), "digest": digest,
               "scene_id": "work-persona-rebuild", "provenance": provenance}
        text = json.dumps(row, ensure_ascii=False, indent=2) + "\n"
        directory = root / "characters/role-cards"
        atomic_write_batch({directory / (key + ".json"): text,
            directory / "history" / (digest + ".json"): text,
            self.data_root / "character-card-library" / work_id_for_root(root) / (digest + ".json"): text})
        return row

    @staticmethod
    def read(root, target):
        key = sha256(target.encode()).hexdigest()[:24]
        path = Path(root) / "characters/role-cards" / (key + ".json")
        if not path.is_file():
            return None
        row = json.loads(path.read_text(encoding="utf-8"))
        card = parse_actor_character_card(row["card"], target)
        digest = sha256(json.dumps(card.to_dict(), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if row["digest"] != digest:
            raise ValueError("work actor card digest mismatch")
        return row
