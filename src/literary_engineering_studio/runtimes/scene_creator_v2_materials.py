"""Dormant v2 material dispatch: creator prompts, frozen sources, and call evidence."""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from literary_engineering_studio_engine.public.literary import (
    CreatorMaterialPlanV1, SceneMaterialRequestV3, SceneMaterialRequestV4,
    assert_required_material_calls,
    ActorCharacterCardV1, parse_actor_character_card, render_actor_character_card,
)

from .scene_creator_workspace import SceneCreatorWorkspace
from .scene_creator_material_context import (
    freeze_material_candidate, natural_material_invitation,
    validate_material_context_budget,
)
from .scene_natural_output import NATURAL_RESPONSE_MODE, render_style
from .event_material_provenance import event_fields as _event_fields


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
    response_mode: str = ""


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
    if "scene.v2.transport.extractor" in layers:
        required = tuple(key for key in required if key not in {
            "scene.v2.material.shared.protocol", "scene.v2.material.output.protocol"}) + ("scene.v2.transport.extractor",)
    pending = [key for key in required if not str(layers.get(key) or "").strip()
               or _PENDING in str(layers[key])]
    if pending:
        raise RuntimeError("scene creator v2 prompt design is incomplete: " + ", ".join(pending))


def render_material_invocation(
    request: SceneMaterialRequestV3, attachments: list[dict[str, Any]],
    layers: Mapping[str, str], *, scene_id: str,
    material_attachments: list[dict[str, Any]] | None = None,
) -> MaterialInvocationV2:
    selected_materials = material_attachments or []
    request_id = sha256(json.dumps([scene_id, request.to_dict(), attachments, selected_materials],
                                   ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:20]
    known = [entry for entry in attachments if entry.get("knowledge") == "known"]
    reference = [entry for entry in attachments if entry.get("knowledge") == "reference"]
    general = [entry for entry in attachments if not entry.get("knowledge")]
    natural = "scene.v2.transport.extractor" in layers
    system, card_digest = _material_system(request, layers, natural)
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
    if isinstance(request, SceneMaterialRequestV4):
        task["working_context"] = request.working_context
        task["selected_materials"] = selected_materials
    manifest = tuple({key: entry.get(key) for key in (
        "path", "line_range", "status", "knowledge", "file_sha256", "content_sha256",
    )} for entry in attachments) + tuple({key: entry.get(key) for key in (
        "candidate_id", "kind", "target", "status", "char_range", "content_sha256",
    )} for entry in selected_materials)
    return MaterialInvocationV2(
        _KIND_ROLE[request.kind], system,
        natural_material_invitation(task) if natural else json.dumps(task, ensure_ascii=False), request_id, manifest,
        character_card_digest=card_digest,
        response_mode=NATURAL_RESPONSE_MODE if natural else "",
    )


def _material_system(request, layers, natural):
    template = str(layers[f"scene.v2.material.{request.kind}"])
    digest = ""
    if request.kind == "actor":
        if request.character_card is None:
            raise ValueError("actor request needs a creator-authored character_card")
        template = render_actor_character_card(template, request.character_card)
        digest = _card_digest(request.character_card)
    elif natural:
        template = render_style(template, request.style_direction)
    if natural:
        return template, digest
    return "\n\n".join((layers["scene.v2.material.shared.protocol"], template,
                         layers["scene.v2.material.output.protocol"])), digest


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
            if set(saved["required_kinds"]) != set(plan.required_kinds):
                raise ValueError("scene creator material plan is frozen for this transaction")
            return
        self._write(path, plan.to_dict())

    def plan_context(self) -> dict[str, Any] | None:
        path = self.root / "material_plan.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def validate_request_archives(self, requests) -> None:
        for request in requests:
            try:
                self.workspace.freeze_attachments(
                    [item.to_dict() for item in request.archive_attachments], kind=request.kind)
            except OSError as error:
                raise ValueError(f"material archive selection is unreadable: {error}") from error

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
        selected_materials = self._prepared_material_attachments(request, request_key)
        validate_material_context_budget(request, attachments, selected_materials)
        call = render_material_invocation(
            request, attachments, self.layers, scene_id=self.scene_id,
            material_attachments=selected_materials,
        )
        history_rows = self._history(request.kind, request.target)
        history = (tuple(("角色此前呈现的台词与动作", row["answer"])
                         for row in history_rows[-12:]) if request.kind == "actor" else ())
        call = replace(call, history=history,
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
            "attachments": attachments, "material_attachments": selected_materials,
            "prompt_sha256": sha256(call.prompt.encode("utf-8")).hexdigest(),
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
        self._publish_actor_card(request.character_card)
        return request.character_card

    def _publish_actor_card(self, card: ActorCharacterCardV1) -> None:
        work_id = self.workspace.scratch_root.name
        data_root = self.workspace.scratch_root.parent.parent
        self._write(data_root / "character-card-library" / work_id / (_card_digest(card) + ".json"),
            {"card": card.to_dict(), "scene_id": self.scene_id, "digest": _card_digest(card)})

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

    def _prepared_material_attachments(
        self, request: SceneMaterialRequestV3, request_key: str,
    ) -> list[dict[str, Any]]:
        refs = getattr(request, "material_attachments", ())
        path = self.root / "prepared-material" / (request_key + ".json")
        if path.is_file():
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved.get("request") != request.to_dict() or not isinstance(saved.get("attachments"), list):
                raise ValueError("prepared material selection is inconsistent")
            return saved["attachments"]
        candidates = self._candidate_lookup() if refs else {}
        attachments = [freeze_material_candidate(ref, candidates) for ref in refs]
        self._write(path, {"schema": "arcvellum/material-selection-prepared/v1",
                           "request": request.to_dict(), "attachments": attachments})
        return attachments

    def _candidate_lookup(self) -> dict[str, dict[str, Any]]:
        found: dict[str, dict[str, Any]] = {}
        for file in sorted((self.root / "calls").glob("*.json")):
            record = json.loads(file.read_text(encoding="utf-8"))
            for candidate in record.get("candidates") or []:
                identifier = str(candidate.get("candidate_id") or "")
                if identifier:
                    found[identifier] = candidate
        return found

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


__all__ = [
    "MaterialInvocationV2", "SceneCreatorV2MaterialCoordinator",
    "assert_v2_prompts_ready", "render_material_invocation",
]
