"""Typed literary task briefs compiled from already-authorized evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Mapping, Protocol

from ruamel.yaml import YAML

from ..contracts import TaskPackage
from .execution_context import ExecutionContextEnvelope
from .prompt_program import PromptEvidence


BRIEF_SCHEMA = "arcvellum/literary-brief/v1"


class LiteraryBrief(Protocol):
    kind: str

    def as_dict(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class SceneWritingBrief:
    kind: str
    scene_id: str
    objective: object
    conflict: object
    participant_states: tuple[object, ...]
    canon_evidence_ids: tuple[str, ...]
    rhythm: Mapping[str, object]
    bridge: Mapping[str, object]
    word_count: Mapping[str, object]
    style_evidence_ids: tuple[str, ...]
    forbidden: tuple[str, ...]
    output_contract: Mapping[str, object]
    provenance: Mapping[str, tuple[str, ...]]

    def as_dict(self) -> dict[str, object]:
        return _brief_dict(self)


@dataclass(frozen=True)
class ReviewBrief:
    kind: str
    scene_id: str
    candidate_evidence_ids: tuple[str, ...]
    deterministic_evidence_ids: tuple[str, ...]
    literary_evidence_ids: tuple[str, ...]
    review_requirements: tuple[str, ...]
    output_contract: Mapping[str, object]
    provenance: Mapping[str, tuple[str, ...]]

    def as_dict(self) -> dict[str, object]:
        return _brief_dict(self)


@dataclass(frozen=True)
class StateEvolutionBrief:
    kind: str
    scene_id: str
    proposed_changes: tuple[object, ...]
    character_evidence_ids: tuple[str, ...]
    canon_boundary_evidence_ids: tuple[str, ...]
    output_contract: Mapping[str, object]
    provenance: Mapping[str, tuple[str, ...]]

    def as_dict(self) -> dict[str, object]:
        return _brief_dict(self)


@dataclass(frozen=True)
class AssetBrief:
    kind: str
    asset_type: str
    objective: str
    source_evidence_ids: tuple[str, ...]
    constraints: tuple[str, ...]
    output_contract: Mapping[str, object]
    provenance: Mapping[str, tuple[str, ...]]

    def as_dict(self) -> dict[str, object]:
        return _brief_dict(self)


def compile_literary_brief(
    task: TaskPackage,
    task_context: Mapping[str, Any],
    envelope: ExecutionContextEnvelope,
    evidence: tuple[PromptEvidence, ...],
    output_contract: Mapping[str, object],
) -> LiteraryBrief | None:
    state = envelope.current_state.casefold()
    if envelope.task_kind == "prose":
        return _scene_brief(task_context, envelope, evidence, output_contract)
    if state == "state-agent-task" or "state-evol" in state:
        return _state_brief(envelope, evidence, output_contract)
    if envelope.task_kind == "review":
        return _review_brief(task_context, envelope, evidence, output_contract)
    if task.route == "character-and-world-assets" or "asset" in state:
        return _asset_brief(task, task_context, evidence, output_contract)
    return None


def _scene_brief(
    context: Mapping[str, Any],
    envelope: ExecutionContextEnvelope,
    evidence: tuple[PromptEvidence, ...],
    output: Mapping[str, object],
) -> SceneWritingBrief:
    scene = _first_mapping(evidence, "scene")
    composition = _first_mapping(evidence, "composition_contract")
    obligations = _mapping(composition.get("composition_obligations"))
    word_count = {
        **_mapping(context.get("word_count")),
        **_mapping(composition.get("word_budget_contract")),
    }
    participants = composition.get("characters")
    if not isinstance(participants, list):
        participants = [_structured(item) for item in evidence if item.role == "character_state"]
    return SceneWritingBrief(
        kind="scene-writing",
        scene_id=envelope.scene_id or str(scene.get("scene_id") or ""),
        objective=scene.get("scene_goal") or obligations.get("scene_goal") or "",
        conflict=scene.get("conflict") or obligations.get("conflict") or "",
        participant_states=tuple(item for item in participants if item),
        canon_evidence_ids=_ids(evidence, "canon", "scene_context"),
        rhythm=_mapping(composition.get("narrative_rhythm") or scene.get("narrative_rhythm")),
        bridge=_mapping(composition.get("scene_bridge") or scene.get("scene_bridge")),
        word_count=word_count,
        style_evidence_ids=_ids(evidence, "mounted_style", "creative_quality_profile"),
        forbidden=_unique((*_strings(context.get("hard_constraints")), *_strings(context.get("style_constraints")))),
        output_contract=output,
        provenance=_provenance(evidence),
    )


def _review_brief(
    context: Mapping[str, Any],
    envelope: ExecutionContextEnvelope,
    evidence: tuple[PromptEvidence, ...],
    output: Mapping[str, object],
) -> ReviewBrief:
    asset = _mapping(context.get("prompt_asset"))
    return ReviewBrief(
        kind="review",
        scene_id=envelope.scene_id,
        candidate_evidence_ids=_ids(evidence, "candidate"),
        deterministic_evidence_ids=_ids(evidence, "deterministic_evidence"),
        literary_evidence_ids=_ids(
            evidence, "scene", "composition_contract", "character_state", "canon",
            "mounted_style", "creative_quality_profile", "scene_context",
        ),
        review_requirements=_review_requirements(
            (*_strings(asset.get("review_requirements")), *_strings(context.get("validation_gates")))
        ),
        output_contract=output,
        provenance=_provenance(evidence),
    )


def _state_brief(
    envelope: ExecutionContextEnvelope,
    evidence: tuple[PromptEvidence, ...],
    output: Mapping[str, object],
) -> StateEvolutionBrief:
    proposed: list[object] = []
    for item in evidence:
        if item.role not in {"candidate", "drafting_material", "composition_contract"}:
            continue
        value = _structured(item)
        if isinstance(value, dict):
            for key in ("characters", "source_changes", "writeback_candidates", "unresolved_changes"):
                if value.get(key):
                    proposed.append({key: value[key]})
    return StateEvolutionBrief(
        kind="state-evolution",
        scene_id=envelope.scene_id,
        proposed_changes=tuple(proposed),
        character_evidence_ids=_ids(evidence, "character_state"),
        canon_boundary_evidence_ids=_ids(evidence, "canon", "scene", "scene_context"),
        output_contract=output,
        provenance=_provenance(evidence),
    )


def _asset_brief(
    task: TaskPackage,
    context: Mapping[str, Any],
    evidence: tuple[PromptEvidence, ...],
    output: Mapping[str, object],
) -> AssetBrief:
    asset = _mapping(context.get("prompt_asset"))
    return AssetBrief(
        kind="asset",
        asset_type=str(task.payload.get("asset_type") or task.payload.get("asset_kind") or ""),
        objective=str(asset.get("body") or "").strip(),
        source_evidence_ids=tuple(item.evidence_id for item in evidence),
        constraints=_unique((*_strings(context.get("hard_constraints")), *_strings(asset.get("hard_constraints")))),
        output_contract=output,
        provenance=_provenance(evidence),
    )


def _brief_dict(value: object) -> dict[str, object]:
    payload = asdict(value)
    payload["schema"] = BRIEF_SCHEMA
    return {key: item for key, item in payload.items() if item not in ("", (), [], {})}


def _first_mapping(evidence: tuple[PromptEvidence, ...], role: str) -> Mapping[str, Any]:
    for item in evidence:
        if item.role == role:
            value = _structured(item)
            if isinstance(value, Mapping):
                return value
    return {}


def _structured(evidence: PromptEvidence) -> object:
    if evidence.fidelity != "structured":
        return {}
    try:
        if evidence.body.lstrip().startswith(("{", "[")):
            return json.loads(evidence.body)
        return YAML(typ="safe").load(evidence.body)
    except (ValueError, TypeError):
        return {}


def _ids(evidence: tuple[PromptEvidence, ...], *roles: str) -> tuple[str, ...]:
    accepted = set(roles)
    return tuple(item.evidence_id for item in evidence if item.role in accepted)


def _provenance(evidence: tuple[PromptEvidence, ...]) -> Mapping[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for item in evidence:
        grouped.setdefault(item.role, []).append(item.evidence_id)
    return {key: tuple(values) for key, values in sorted(grouped.items())}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _review_requirements(values: tuple[str, ...]) -> tuple[str, ...]:
    """Keep literary review semantics, not duplicate transport receipts."""

    duplicate_fragments = (
        "cite the exact candidate path",
        "candidate_sha256 must equal",
        "scene_review.v1 json exists",
        "review cites exact candidate",
        "review conclusion is recorded",
        "new_character_register is recorded",
    )
    return _unique(
        tuple(
            value
            for value in values
            if not any(fragment in value.casefold() for fragment in duplicate_fragments)
        )
    )


__all__ = [
    "AssetBrief", "BRIEF_SCHEMA", "LiteraryBrief", "ReviewBrief",
    "SceneWritingBrief", "StateEvolutionBrief", "compile_literary_brief",
]
