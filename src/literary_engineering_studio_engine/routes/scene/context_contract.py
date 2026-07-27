"""Engine-owned first-turn context contracts for high-cost scene tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from ...tasking.context_contract import CONTEXT_CONTRACT_SCHEMA

CONTEXT_CONTRACT_REVISION = "scene-v1"
CONTEXT_CONTRACT_STATUS = "shadow-ready"
CONTEXT_CONTRACT_STATES = {
    "candidate-generation-provenance",
    "candidate-review",
    "candidate-revision",
    "static-revision",
}
PUNCTUATION_STANDARD = "references/punctuation-standard.md"


def scene_context_contract(
    root: Path,
    task: Mapping[str, object],
) -> dict[str, object]:
    """Return a deterministic mandatory-context contract for selected states."""

    state = str(task.get("current_state") or "")
    if state not in CONTEXT_CONTRACT_STATES:
        return {}
    scene_id = str(task.get("scene_id") or "")
    sources = _strings(task.get("agent_source_paths"))
    core_outputs = _strings(task.get("core_managed_outputs"))
    required_reading = _strings(task.get("required_reading"))
    allowed = set((*sources, *core_outputs, *required_reading))
    candidates = _mandatory_candidates(state, scene_id, task, sources, core_outputs)
    mandatory = tuple(
        path
        for path in _unique((*candidates, PUNCTUATION_STANDARD))
        if path in allowed
        and (
            path in core_outputs
            or path == PUNCTUATION_STANDARD
            or (root / Path(path)).is_file()
        )
    )
    _validate_primary_evidence(state, task, mandatory)
    return {
        "context_contract_required": True,
        "context_contract_schema": CONTEXT_CONTRACT_SCHEMA,
        "context_contract_revision": CONTEXT_CONTRACT_REVISION,
        "context_contract_status": CONTEXT_CONTRACT_STATUS,
        "context_must_inline_paths": list(mandatory),
    }


def _mandatory_candidates(
    state: str,
    scene_id: str,
    task: Mapping[str, object],
    sources: tuple[str, ...],
    core_outputs: tuple[str, ...],
) -> tuple[str, ...]:
    sidecars = tuple(
        path for path in core_outputs if path.endswith(".agent_tasks.md")
    )
    common = (
        f"scenes/{scene_id}.yaml",
        f"memory/context_packets/{scene_id}.md",
        "style/creative_quality_profile.json",
        "style/style-profile.md",
        *sidecars,
    )
    if state == "candidate-generation-provenance":
        chapter_obligations = tuple(
            path
            for path in sources
            if path.startswith("plot/chapter_obligations/")
            and path.endswith(".json")
        )
        return (
            *common,
            f"branches/{scene_id}/branch_selection.md",
            f"drafts/compositions/{scene_id}_composition.md",
            f"drafts/compositions/{scene_id}_composition.json",
            f"drafts/compositions/{scene_id}_composition_review.json",
            *chapter_obligations,
        )
    if state == "candidate-review":
        return (
            *_candidate_markdown_sources(sources),
            *common,
            f"drafts/compositions/{scene_id}_composition_review.json",
            f"branches/{scene_id}/branch_selection.md",
        )
    return (
        *_revision_source(task, sources),
        *_review_evidence_sources(sources),
        *common,
    )


def _candidate_markdown_sources(sources: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        path
        for path in sources
        if path.endswith(".md")
        and path.startswith(("drafts/candidates/", "drafts/revisions/"))
        and not path.endswith("_report.md")
    )


def _revision_source(
    task: Mapping[str, object],
    sources: tuple[str, ...],
) -> tuple[str, ...]:
    declared = str(task.get("revision_source") or "").replace("\\", "/")
    if declared and declared in sources:
        return (declared,)
    return tuple(
        path
        for path in sources
        if path.endswith(".md")
        and path.startswith(
            ("drafts/candidates/", "drafts/revisions/", "drafts/scenes/")
        )
        and not path.endswith("_report.md")
    )


def _review_evidence_sources(sources: tuple[str, ...]) -> tuple[str, ...]:
    agent_json = tuple(
        path
        for path in sources
        if path.startswith("reviews/agent/") and path.endswith(".json")
    )
    if agent_json:
        return agent_json
    return tuple(
        path
        for path in sources
        if path.startswith("reviews/") and path.endswith((".json", ".md"))
    )


def _validate_primary_evidence(
    state: str,
    task: Mapping[str, object],
    mandatory: tuple[str, ...],
) -> None:
    if not any(path.endswith(".agent_tasks.md") for path in mandatory):
        raise ValueError(
            f"{state} context contract requires a CLI-owned task sidecar"
        )
    if state == "candidate-review" and not _candidate_markdown_sources(mandatory):
        raise ValueError(
            "candidate-review context contract requires the exact candidate Markdown"
        )
    if state in {"candidate-revision", "static-revision"}:
        revision_source = str(task.get("revision_source") or "").replace("\\", "/")
        if not revision_source or revision_source not in mandatory:
            raise ValueError(
                f"{state} context contract requires the exact revision source"
            )
        if not any(path.startswith("reviews/") for path in mandatory):
            raise ValueError(
                f"{state} context contract requires exact review evidence"
            )


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return _unique(str(item) for item in value if str(item).strip())


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            normalized
            for value in values
            if (normalized := str(value).strip().replace("\\", "/"))
        )
    )
