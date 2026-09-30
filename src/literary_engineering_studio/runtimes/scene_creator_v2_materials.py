"""Dormant v2 material dispatch: creator prompts, frozen sources, and call evidence."""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from literary_engineering_studio_engine.public.literary import (
    CreatorMaterialPlanV1, SceneMaterialRequestV3, assert_required_material_calls,
    ActorCharacterCardV1, parse_actor_character_card, render_actor_character_card,
)

from .scene_creator_workspace import SceneCreatorWorkspace


_KIND_ROLE = {
    "actor": "character-actor",
    "environment": "environment-writer",
    "character-description": "character-describer",
    "event-narration": "event-narrator",
    "scene-description": "scene-describer",
}
_PENDING = "[PENDING_PROMPT_DESIGN:"


@dataclass(frozen=True)
class MaterialInvocationV2:
    role: str
    initialization: str
    prompt: str
    request_id: str
    attachment_manifest: tuple[dict[str, Any], ...]
    history: tuple[tuple[str, str], ...] = ()
    initialization_answer: str = ""
    character_card_digest: str = ""


def assert_v2_prompts_ready(layers: Mapping[str, str]) -> None:
    required = (
        "scene.v2.creator.identity", "scene.v2.creator.protocol", "scene.v2.creator.bootstrap", "scene.v2.creator.create",
        "scene.v2.creator.revise", "scene.v2.creator.delegation", "scene.v2.creator.archive",
        "scene.v2.creator.actor-card",
        "scene.v2.creator.sandbox", "scene.v2.creator.selection",
        "scene.v2.review", "scene.v2.review.protocol",
        "scene.v2.material.shared.protocol", "scene.v2.material.output.protocol",
        *(f"scene.v2.material.{kind}" for kind in _KIND_ROLE),
        "project_agent.creator_persona.v2",
    )
    pending = [key for key in required if not str(layers.get(key) or "").strip()
               or _PENDING in str(layers[key])]
    if pending:
        raise RuntimeError("scene creator v2 prompt design is incomplete: " + ", ".join(pending))


def render_material_invocation(
    request: SceneMaterialRequestV3, attachments: list[dict[str, Any]],
    layers: Mapping[str, str], *, scene_id: str,
) -> MaterialInvocationV2:
    request_id = sha256(json.dumps([scene_id, request.to_dict(), attachments],
                                   ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:20]
    known = [entry for entry in attachments if entry.get("knowledge") == "known"]
    reference = [entry for entry in attachments if entry.get("knowledge") == "reference"]
    general = [entry for entry in attachments if not entry.get("knowledge")]
    material_template = str(layers[f"scene.v2.material.{request.kind}"])
    shared = str(layers["scene.v2.material.shared.protocol"])
    output = str(layers["scene.v2.material.output.protocol"])
    card_digest = ""
    if request.kind == "actor":
        if request.character_card is None:
            raise ValueError("actor request needs a creator-authored character_card")
        material_template = render_actor_character_card(material_template, request.character_card)
        card_digest = _card_digest(request.character_card)
    task = {
        "schema": "arcvellum/material-invocation/v2",
        "scene_id": scene_id,
        "kind": request.kind,
        "target": request.target,
        "purpose": request.purpose,
        "scene_moment": request.scene_moment,
        "cue": request.cue,
        "author_prompt": request.author_prompt,
        "beat_id": request.beat_id,
        "scene_change": request.scene_change,
        "role_known_archive": known,
        "director_reference_archive": reference,
        "other_archive": general,
    }
    manifest = tuple({key: entry.get(key) for key in (
        "path", "line_range", "status", "knowledge", "file_sha256", "content_sha256",
    )} for entry in attachments)
    return MaterialInvocationV2(
        _KIND_ROLE[request.kind], shared + "\n\n" + material_template + "\n\n" + output,
        json.dumps(task, ensure_ascii=False), request_id, manifest,
        character_card_digest=card_digest,
    )


class SceneCreatorV2MaterialCoordinator:
    """Persist request snapshots and verify actual consultations before prose."""

    def __init__(self, root: Path, workspace: SceneCreatorWorkspace, layers: Mapping[str, str],
                 *, scene_id: str, actor_personas: Mapping[str, str] | None = None):
        self.root = root
        self.workspace = workspace
        self.layers = layers
        self.scene_id = scene_id
        self.actor_personas = actor_personas or {}

    def save_plan(self, plan: CreatorMaterialPlanV1) -> None:
        path = self.root / "material_plan.json"
        if path.is_file():
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved != plan.to_dict():
                raise ValueError("scene creator material plan is frozen for this transaction")
            return
        self._write(path, plan.to_dict())

    def execute(
        self, request: SceneMaterialRequestV3,
        invoke: Callable[[MaterialInvocationV2], Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        if not (self.root / "material_plan.json").is_file():
            raise ValueError("scene creator must save a material plan before calling an agent")
        if request.kind == "actor":
            request = replace(request, character_card=self._resolve_actor_card(request))
        request_key = sha256(json.dumps([self.scene_id, request.to_dict()],
                                        ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:20]
        record_path = self.root / "calls" / (request_key + ".json")
        if record_path.is_file():
            saved = json.loads(record_path.read_text(encoding="utf-8"))
            return list(saved["candidates"])
        attachments = self._prepared_attachments(request, request_key)
        call = render_material_invocation(request, attachments, self.layers, scene_id=self.scene_id)
        history_rows = self._history(request.kind, request.target)
        call = replace(call, history=tuple((row["prompt"], row["answer"]) for row in history_rows[-12:]),
                       initialization_answer=(str(history_rows[-1].get("initialization_answer") or "")
                                              if history_rows else ""))
        response = invoke(call)
        candidates = _parse_candidates(response, request, call.request_id)
        sequence = len(list((self.root / "calls").glob("*.json"))) + 1
        self._write(record_path, {
            "schema": "arcvellum/material-call/v2", "scene_id": self.scene_id,
            "sequence": sequence,
            "request": request.to_dict(), "request_id": call.request_id, "role": call.role,
            "attachment_manifest": list(call.attachment_manifest),
            "attachments": attachments, "prompt_sha256": sha256(call.prompt.encode("utf-8")).hexdigest(),
            "initialization_sha256": sha256(call.initialization.encode("utf-8")).hexdigest(),
            "character_card_digest": call.character_card_digest,
            "prompt": call.prompt, "answer": str(response.get("__answer") or ""),
            "initialization_answer": str(response.get("__initialization_answer") or ""),
            "invoked": True, "candidates": candidates,
        })
        self._write_candidate_library()
        return candidates

    def _resolve_actor_card(self, request: SceneMaterialRequestV3) -> ActorCharacterCardV1:
        filename = sha256(request.target.encode("utf-8")).hexdigest()[:24] + ".json"
        path = self.root / "actor-cards" / filename
        if path.is_file():
            saved = parse_actor_character_card(json.loads(path.read_text(encoding="utf-8")), request.target)
            if request.character_card is not None and request.character_card != saved:
                raise ValueError("character_card is frozen for this actor and scene transaction")
            return saved
        if request.character_card is None:
            raise ValueError("first actor request needs a creator-authored character_card")
        self._write(path, request.character_card.to_dict())
        return request.character_card

    def creator_card_context(self) -> dict[str, Any]:
        cards = []
        for path in sorted((self.root / "actor-cards").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            card = parse_actor_character_card(payload, str(payload.get("target") or ""))
            cards.append({"digest": _card_digest(card), "card": card.to_dict()})
        return {"stable_persona_sources": dict(self.actor_personas), "frozen_scene_cards": cards}

    def _prepared_attachments(self, request: SceneMaterialRequestV3, request_key: str) -> list[dict[str, Any]]:
        path = self.root / "prepared" / (request_key + ".json")
        if path.is_file():
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved.get("request") != request.to_dict() or not isinstance(saved.get("attachments"), list):
                raise ValueError("prepared material request is inconsistent")
            return saved["attachments"]
        attachments = self.workspace.freeze_attachments(
            [item.to_dict() for item in request.archive_attachments], kind=request.kind,
        )
        self._write(path, {"schema": "arcvellum/material-request-prepared/v1",
                           "request": request.to_dict(), "attachments": attachments})
        return attachments

    def completed_kinds(self) -> tuple[str, ...]:
        kinds = []
        for file in sorted((self.root / "calls").glob("*.json")):
            record = json.loads(file.read_text(encoding="utf-8"))
            if record.get("invoked") is True:
                kinds.append(str(record.get("request", {}).get("kind") or ""))
        return tuple(kinds)

    def _history(self, kind: str, target: str) -> list[dict[str, Any]]:
        rows = []
        for file in sorted((self.root / "calls").glob("*.json")):
            record = json.loads(file.read_text(encoding="utf-8"))
            request = record.get("request") or {}
            if request.get("kind") == kind and request.get("target") == target and record.get("answer"):
                rows.append(record)
        return sorted(rows, key=lambda row: int(row.get("sequence") or 0))

    def assert_ready_for_prose(self) -> None:
        path = self.root / "material_plan.json"
        if not path.is_file():
            raise ValueError("scene creator material plan is missing")
        saved = json.loads(path.read_text(encoding="utf-8"))
        plan = CreatorMaterialPlanV1(tuple(saved["required_kinds"]), str(saved["reason"]))
        assert_required_material_calls(plan, self.completed_kinds())

    def _write_candidate_library(self) -> None:
        directory = self.root / "materials"
        directory.mkdir(parents=True, exist_ok=True)
        entries = []
        for file in sorted((self.root / "calls").glob("*.json")):
            record = json.loads(file.read_text(encoding="utf-8"))
            for candidate in record["candidates"]:
                identifier = candidate["candidate_id"]
                filename = sha256(identifier.encode("utf-8")).hexdigest()[:24] + ".json"
                self._write(directory / filename, {
                    "schema": "arcvellum/scene-material/v1", "candidate_id": identifier,
                    "kind": candidate["kind"], "target": candidate["target"],
                    "purpose": candidate["purpose"], "scene_moment": candidate["scene_moment"],
                    "content": candidate,
                })
                entries.append({key: candidate[key] for key in (
                    "candidate_id", "kind", "target", "purpose", "scene_moment",
                )} | {"file": filename})
        self._write(directory / "index.json", {
            "schema": "arcvellum/scene-material-library/v1", "entries": entries,
        })

    @staticmethod
    def _write(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)


def _parse_candidates(response: Mapping[str, Any], request: SceneMaterialRequestV3,
                      request_id: str) -> list[dict[str, Any]]:
    raw = response.get("candidates")
    if not isinstance(raw, list) or len(raw) > 3:
        raise ValueError("material agent must return at most three candidates")
    if not raw and not str(response.get("no_material_reason") or "").strip():
        raise ValueError("empty material response needs a reason")
    result = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, Mapping):
            raise ValueError("material candidate must be an object")
        actor_fields = _actor_fields(item) if request.kind == "actor" else {}
        text, focus = _candidate_text_focus(item, actor_fields)
        candidate = {"candidate_id": f"v2:{request_id}:{index}", "kind": request.kind,
                     "target": request.target, "purpose": request.purpose,
                     "scene_moment": request.scene_moment, "text": text, "focus": focus}
        candidate.update(actor_fields)
        if request.kind == "event-narration":
            candidate.update(_event_fields(item))
        result.append(candidate)
    return result


def _card_digest(card: ActorCharacterCardV1) -> str:
    return sha256(json.dumps(card.to_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _candidate_text_focus(item: Mapping[str, Any], actor_fields: Mapping[str, str]) -> tuple[str, str]:
    text = str(item.get("text") or "").strip() or "\n".join(
        part for part in (actor_fields.get("first_person_action"), actor_fields.get("spoken")) if part
    )
    focus = str(item.get("focus") or "").strip()
    if not 5 <= len(text) <= 2400 or not 1 <= len(focus) <= 200:
        raise ValueError("material candidate needs bounded literary text and focus")
    return text, focus


def _actor_fields(item: Mapping[str, Any]) -> dict[str, str]:
    spoken = str(item.get("spoken") or "").strip()
    action = str(item.get("first_person_action") or "").strip()
    if not (spoken or action):
        raise ValueError("actor candidate needs speech or first-person action")
    return {"spoken": spoken[:1200], "first_person_action": action[:1200],
            "private_impulse": str(item.get("private_impulse") or "").strip()[:800]}


def _event_fields(item: Mapping[str, Any]) -> dict[str, str]:
    basis = str(item.get("basis") or "")
    note = str(item.get("source_note") or "").strip()
    if basis not in {"confirmed", "attributed", "proposed"} or not note:
        raise ValueError("event candidate needs basis and source_note")
    return {"basis": basis, "source_note": note[:500]}


__all__ = [
    "MaterialInvocationV2", "SceneCreatorV2MaterialCoordinator",
    "assert_v2_prompts_ready", "render_material_invocation",
]
