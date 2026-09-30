"""Pure v2 scene creator delegation contract; no file access or model calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .character_card import ActorCharacterCardV1, parse_actor_character_card


MATERIAL_KINDS_V3 = frozenset({
    "actor", "environment", "character-description", "event-narration", "scene-description",
})


@dataclass(frozen=True)
class ArchiveAttachmentRefV1:
    path: str
    start_line: int | None = None
    end_line: int | None = None
    knowledge: str = ""

    def to_dict(self) -> dict[str, str | int | None]:
        return {"path": self.path, "start_line": self.start_line,
                "end_line": self.end_line, "knowledge": self.knowledge}


@dataclass(frozen=True)
class SceneMaterialRequestV3:
    kind: str
    target: str
    purpose: str
    scene_moment: str
    cue: str
    author_prompt: str
    archive_attachments: tuple[ArchiveAttachmentRefV1, ...] = ()
    beat_id: str = ""
    scene_change: str = ""
    character_card: ActorCharacterCardV1 | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {"kind": self.kind, "target": self.target, "purpose": self.purpose,
                "scene_moment": self.scene_moment, "cue": self.cue,
                "author_prompt": self.author_prompt,
                "archive_attachments": [item.to_dict() for item in self.archive_attachments],
                "beat_id": self.beat_id, "scene_change": self.scene_change}
        if self.character_card is not None:
            result["character_card"] = self.character_card.to_dict()
        return result


@dataclass(frozen=True)
class CreatorMaterialPlanV1:
    required_kinds: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"required_kinds": list(self.required_kinds), "reason": self.reason}


def parse_creator_material_plan(payload: Mapping[str, Any]) -> CreatorMaterialPlanV1:
    raw = payload.get("material_plan")
    if not isinstance(raw, Mapping):
        raise ValueError("scene creator v2 needs a material_plan before prose")
    kinds = raw.get("required_kinds")
    if (not isinstance(kinds, list) or not kinds or len(kinds) > len(MATERIAL_KINDS_V3)
            or any(not isinstance(item, str) or item not in MATERIAL_KINDS_V3 for item in kinds)
            or len(kinds) != len(set(kinds))):
        raise ValueError("material_plan needs one or more distinct supported kinds")
    reason = str(raw.get("reason") or "").strip()
    if not reason or len(reason) > 1000:
        raise ValueError("material_plan needs a concise literary reason")
    return CreatorMaterialPlanV1(tuple(kinds), reason)


def parse_scene_material_requests_v3(
    payload: Mapping[str, Any], participants: tuple[str, ...] | list[str],
) -> tuple[SceneMaterialRequestV3, ...]:
    raw = payload.get("material_requests", [])
    if not isinstance(raw, list) or len(raw) > 8:
        raise ValueError("material_requests must have at most eight requests")
    return tuple(_parse_request(item, set(participants)) for item in raw)


def _parse_request(raw: Any, participants: set[str]) -> SceneMaterialRequestV3:
    if not isinstance(raw, Mapping):
        raise ValueError("material request must be an object")
    fields = {key: str(raw.get(key) or "").strip() for key in (
        "kind", "target", "purpose", "scene_moment", "cue", "author_prompt", "beat_id", "scene_change",
    )}
    kind, target = fields["kind"], fields["target"]
    _validate_common_request(fields)
    _validate_target(kind, target, fields["scene_change"], participants)
    attachments = raw.get("archive_attachments", [])
    if not isinstance(attachments, list) or len(attachments) > 20:
        raise ValueError("archive_attachments must have at most twenty entries")
    card = _request_card(raw.get("character_card"), kind, target)
    return SceneMaterialRequestV3(
        kind, target, fields["purpose"], fields["scene_moment"], fields["cue"], fields["author_prompt"],
        tuple(_parse_attachment(item, kind) for item in attachments),
        fields["beat_id"], fields["scene_change"], card,
    )


def _request_card(raw: Any, kind: str, target: str) -> ActorCharacterCardV1 | None:
    if raw is None:
        return None
    if kind != "actor":
        raise ValueError("character_card only applies to actor requests")
    return parse_actor_character_card(raw, target)


def _validate_common_request(fields: Mapping[str, str]) -> None:
    kind = fields["kind"]
    if kind not in MATERIAL_KINDS_V3:
        raise ValueError("unsupported material kind")
    if any(not fields[key] for key in ("purpose", "scene_moment", "cue", "author_prompt")):
        raise ValueError("material request needs purpose, moment, cue, and author_prompt")
    limits = {"target": 120, "purpose": 500, "scene_moment": 300, "cue": 1200,
              "author_prompt": 6000, "scene_change": 800}
    if any(len(fields[key]) > limit for key, limit in limits.items()):
        raise ValueError("material request exceeds a field limit")


def _validate_target(kind: str, target: str, scene_change: str, participants: set[str]) -> None:
    if kind in {"actor", "character-description"} and target not in participants:
        raise ValueError("actor and character-description target must be a scene participant")
    if kind == "event-narration" and not target:
        raise ValueError("event-narration requires a subject")
    if kind != "actor" and scene_change:
        raise ValueError("scene_change only applies to actor requests")


def _parse_attachment(raw: Any, kind: str) -> ArchiveAttachmentRefV1:
    if not isinstance(raw, Mapping):
        raise ValueError("archive attachment must be an object")
    path = str(raw.get("path") or "").strip()
    start, end = raw.get("start_line"), raw.get("end_line")
    knowledge = str(raw.get("knowledge") or "").strip()
    if not path or len(path) > 500:
        raise ValueError("archive attachment needs a relative path")
    _validate_line_range(start, end)
    _validate_knowledge(kind, knowledge)
    return ArchiveAttachmentRefV1(path, start, end, knowledge)


def _validate_line_range(start: Any, end: Any) -> None:
    if (start is None) != (end is None):
        raise ValueError("archive attachment needs both line endpoints")
    if start is None:
        return
    if not isinstance(start, int) or isinstance(start, bool):
        raise ValueError("archive attachment line range is invalid")
    if not isinstance(end, int) or isinstance(end, bool) or start < 1 or end < start:
        raise ValueError("archive attachment line range is invalid")


def _validate_knowledge(kind: str, knowledge: str) -> None:
    if kind == "actor" and knowledge not in {"known", "reference"}:
        raise ValueError("actor attachment must state known or reference")
    if kind != "actor" and knowledge:
        raise ValueError("only actor attachments have a knowledge partition")


def assert_required_material_calls(
    plan: CreatorMaterialPlanV1, completed_kinds: tuple[str, ...] | list[str],
) -> None:
    missing = sorted(set(plan.required_kinds) - set(completed_kinds))
    if missing:
        raise ValueError("required material kinds were not called: " + ", ".join(missing))


__all__ = [
    "ArchiveAttachmentRefV1", "CreatorMaterialPlanV1", "MATERIAL_KINDS_V3",
    "SceneMaterialRequestV3", "assert_required_material_calls",
    "parse_creator_material_plan", "parse_scene_material_requests_v3",
]
