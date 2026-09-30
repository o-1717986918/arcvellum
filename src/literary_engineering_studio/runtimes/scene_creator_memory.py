"""Bounded, transaction-local memory for independent scene creator calls."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.public.literary import CreativeIntentV1, SceneBrief


@dataclass
class SceneCreatorMemoryV1:
    scene_id: str
    intent: CreativeIntentV1 | None = None
    intent_source: str = ""
    candidate_ids: list[str] = field(default_factory=list)
    material_decisions: list[dict[str, str]] = field(default_factory=list)
    material_skip_reason: str = ""
    unresolved_questions: list[str] = field(default_factory=list)
    public_stage: list[dict[str, str]] = field(default_factory=list)
    phase: str = "opening"
    prompt_digest: str = ""
    pending_request: dict[str, Any] | None = None

    SCHEMA = "arcvellum/scene-creator-memory/v1"

    @classmethod
    def load(cls, path: Path, scene_id: str, *, request_limit_chars: int = 8_000) -> SceneCreatorMemoryV1:
        if not path.is_file():
            return cls(scene_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema") != cls.SCHEMA or payload.get("scene_id") != scene_id:
            raise ValueError("scene creator memory does not match the transaction scene")
        intent_payload = payload.get("intent")
        intent = None
        if isinstance(intent_payload, dict):
            parsed = CreativeIntentV1.from_payload(intent_payload)
            intent = CreativeIntentV1(
                parsed.reader_experience, parsed.reader_knows, parsed.reader_misreads,
                parsed.withheld, int(intent_payload.get("revision") or 1),
            )
        return cls(
            scene_id=scene_id, intent=intent,
            intent_source=str(payload.get("intent_source") or ""),
            candidate_ids=_texts(payload.get("candidate_ids"), limit=80, size=80),
            material_decisions=_decisions(payload.get("material_decisions")),
            material_skip_reason=str(payload.get("material_skip_reason") or "")[:300],
            unresolved_questions=_texts(payload.get("unresolved_questions"), limit=8, size=240),
            public_stage=_public_stage(payload.get("public_stage")),
            phase=str(payload.get("phase") or "opening")[:40],
            prompt_digest=str(payload.get("prompt_digest") or "")[:64],
            pending_request=_pending_request(payload.get("pending_request"), limit_chars=request_limit_chars),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA, "scene_id": self.scene_id,
            "intent": self.intent.to_dict() if self.intent else None,
            "intent_source": self.intent_source,
            "candidate_ids": self.candidate_ids[-80:],
            "material_decisions": self.material_decisions[-40:],
            "material_skip_reason": self.material_skip_reason,
            "unresolved_questions": self.unresolved_questions[-8:],
            "public_stage": self.public_stage[-16:],
            "phase": self.phase, "prompt_digest": self.prompt_digest,
            "pending_request": self.pending_request,
        }

    def render_context(self) -> str:
        context = self.to_dict()
        context.pop("schema")
        context.pop("scene_id")
        # Rehearsal speech and description remain in read-only material files.
        context.pop("public_stage")
        return json.dumps(context, ensure_ascii=False, separators=(",", ":"))[:5_000]

    def digest(self) -> str:
        return hashlib.sha256(self.render_context().encode("utf-8")).hexdigest()[:12]

    def record_creator(self, payload: dict[str, Any], brief: SceneBrief, *, prompt: str,
                       request_limit_chars: int = 8_000) -> None:
        proposed = payload.get("creative_intent")
        if proposed is not None:
            revised = CreativeIntentV1.from_payload(proposed, prior=self.intent)
            if self.intent is None or _intent_text(revised) != _intent_text(self.intent):
                self.intent = revised
            self.intent_source = "creator"
        elif self.intent is None:
            # Old cached/test responses remain readable; new prompts require an explicit intent.
            self.intent = CreativeIntentV1.from_payload({"reader_experience": brief.scene_function or brief.objective})
            self.intent_source = "brief-compatibility"
        self.material_decisions = [*self.material_decisions, *_decisions(payload.get("material_decisions"))][-40:]
        if payload.get("material_skip_reason"):
            self.material_skip_reason = str(payload["material_skip_reason"]).strip()[:300]
        if "unresolved_questions" in payload:
            self.unresolved_questions = _texts(payload["unresolved_questions"], limit=8, size=240)
        self.phase = "requesting-material" if payload.get("material_requests") else "drafted"
        self.prompt_digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        self.pending_request = (_pending_request(payload, limit_chars=request_limit_chars)
                                if payload.get("material_requests") else None)

    def record_materials(self, materials: str) -> None:
        try:
            packet = json.loads(materials.rsplit("\n", 1)[1])
        except (IndexError, json.JSONDecodeError):
            return
        if not isinstance(packet, dict):
            return
        self.candidate_ids = list(dict.fromkeys([*self.candidate_ids, *_material_ids(packet)]))[-80:]
        stage = _public_stage(packet.get("actor_entries"))
        if stage:
            self.public_stage = stage
        self.phase = "material-ready"
        self.pending_request = None


def _intent_text(intent: CreativeIntentV1) -> tuple[str, str, str, str]:
    return intent.reader_experience, intent.reader_knows, intent.reader_misreads, intent.withheld


def _texts(value: object, *, limit: int, size: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip()[:size] for item in value[:limit] if isinstance(item, str) and item.strip()]


def _decisions(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows = []
    for item in value[:40]:
        if not isinstance(item, dict):
            continue
        identifier = str(item.get("candidate_id") or "")[:80].strip()
        decision = str(item.get("decision") or "").strip()
        reason = str(item.get("reason") or "")[:240].strip()
        if identifier and decision in {"use", "discard", "adapt"} and reason:
            rows.append({"candidate_id": identifier, "decision": decision, "reason": reason})
    return rows


def _public_stage(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [{key: str(item[key])[:300] for key in ("speaker", "spoken", "first_person_action") if item.get(key)}
            for item in value[-16:] if isinstance(item, dict)]


def _material_ids(packet: dict[str, Any]) -> list[str]:
    candidates = [*(packet.get("actor_entries") or []), *(packet.get("description_candidates") or [])]
    ids = [str(item.get("entry_id") or item.get("candidate_id") or "")[:80]
           for item in candidates if isinstance(item, dict)]
    environment = packet.get("environment_candidates")
    passages = environment.get("passages", []) if isinstance(environment, dict) else []
    ids.extend(str(item.get("candidate_id") or f"environment:{index}")[:80]
               for index, item in enumerate(passages, 1) if isinstance(item, dict))
    return [identifier for identifier in ids if identifier]


def _pending_request(value: object, *, limit_chars: int = 8_000) -> dict[str, Any] | None:
    if not isinstance(value, dict) or not isinstance(value.get("material_requests"), list):
        return None
    requests = value["material_requests"]
    if not requests or len(requests) > 8:
        raise ValueError("scene material request batch must contain one to eight requests")
    encoded = json.dumps(requests, ensure_ascii=False)
    if len(encoded) > limit_chars:
        raise ValueError("scene material request batch exceeds memory limit")
    return {"material_requests": requests}
