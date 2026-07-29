"""Engine-owned first-turn context contracts for high-cost scene tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from ...literary.review.context_evidence import (
    scene_review_context_declaration,
)
from ...tasking.context_contract import CONTEXT_CONTRACT_SCHEMA

CONTEXT_CONTRACT_REVISION = "scene-v2"
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
    contract = {
        "context_contract_required": True,
        "context_contract_schema": CONTEXT_CONTRACT_SCHEMA,
        "context_contract_revision": CONTEXT_CONTRACT_REVISION,
        "context_contract_status": _contract_status(state),
        "context_must_inline_paths": list(mandatory),
    }
    if state == "candidate-review":
        contract["context_exact_on_demand_paths"] = list(
            _candidate_review_exact_paths(scene_id, sources, core_outputs)
        )
        contract["context_excluded_paths"] = list(
            _candidate_review_excluded_paths(
                scene_id,
                task,
                sources,
            )
        )
        contract["context_evidence_contract"] = _review_evidence_declaration(
            task,
            scene_id,
            core_outputs,
        )
    return contract


def _candidate_review_excluded_paths(
    scene_id: str,
    task: Mapping[str, object],
    sources: tuple[str, ...],
) -> tuple[str, ...]:
    candidate = str(task.get("candidate") or "").replace("\\", "/")
    candidate_manifest = (
        Path(candidate).with_suffix(".json").as_posix()
        if candidate
        else ""
    )
    covered_by_compact_evidence = {
        candidate_manifest,
        f"memory/context_packets/{scene_id}.trace.json",
        "plot/word_budget/word_budget.json",
    }
    return tuple(
        path
        for path in sources
        if path in covered_by_compact_evidence
    )


def _candidate_review_exact_paths(
    scene_id: str,
    sources: tuple[str, ...],
    core_outputs: tuple[str, ...],
) -> tuple[str, ...]:
    context_packet = f"memory/context_packets/{scene_id}.md"
    return _unique(
        (
            *(
                path
                for path in core_outputs
                if path.endswith(".agent_tasks.md")
            ),
            *(
                path
                for path in sources
                if path == context_packet
            ),
        )
    )


def _contract_status(state: str) -> str:
    return "bounded-ready" if state == "candidate-review" else "shadow-ready"


def _mandatory_candidates(
    state: str,
    scene_id: str,
    task: Mapping[str, object],
    sources: tuple[str, ...],
    core_outputs: tuple[str, ...],
) -> tuple[str, ...]:
    common = (
        f"scenes/{scene_id}.yaml",
        f"memory/context_packets/{scene_id}.md",
        "style/creative_quality_profile.json",
        "style/style-profile.md",
    )
    sidecars = tuple(
        path for path in core_outputs if path.endswith(".agent_tasks.md")
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
            *sidecars,
            f"branches/{scene_id}/branch_selection.md",
            f"drafts/compositions/{scene_id}_composition.md",
            f"drafts/compositions/{scene_id}_composition.json",
            f"drafts/compositions/{scene_id}_composition_review.json",
            *chapter_obligations,
        )
    if state == "candidate-review":
        compact = tuple(
            path
            for path in core_outputs
            if path.startswith("reviews/agent/")
            and path.endswith("_scene_review.context.json")
        )
        return (
            *_candidate_markdown_sources(sources),
            f"scenes/{scene_id}.yaml",
            "style/creative_quality_profile.json",
            "style/style-profile.md",
            *compact,
            f"drafts/compositions/{scene_id}_composition_review.json",
            f"branches/{scene_id}/branch_selection.md",
        )
    return (
        *_revision_source(task, sources),
        *_review_evidence_sources(sources),
        *common,
        *sidecars,
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
    if (
        state != "candidate-review"
        and not any(path.endswith(".agent_tasks.md") for path in mandatory)
    ):
        raise ValueError(
            f"{state} context contract requires a CLI-owned task sidecar"
        )
    if state == "candidate-review":
        _validate_candidate_review_evidence(task, mandatory)
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


def _validate_candidate_review_evidence(
    task: Mapping[str, object],
    mandatory: tuple[str, ...],
) -> None:
    core_outputs = _strings(task.get("core_managed_outputs"))
    if not any(path.endswith(".agent_tasks.md") for path in core_outputs):
        raise ValueError(
            "candidate-review context contract requires a CLI-owned task sidecar"
        )
    if not _candidate_markdown_sources(mandatory):
        raise ValueError(
            "candidate-review context contract requires the exact candidate Markdown"
        )
    if not any(
        path.endswith("_scene_review.context.json")
        for path in mandatory
    ):
        raise ValueError(
            "candidate-review context contract requires compact review evidence"
        )


def _review_evidence_declaration(
    task: Mapping[str, object],
    scene_id: str,
    core_outputs: tuple[str, ...],
) -> dict[str, object]:
    expected = _strings(task.get("expected_outputs"))
    candidate = str(task.get("candidate") or "").replace("\\", "/")
    artifact = _single_path(
        core_outputs,
        suffix="_scene_review.context.json",
        label="compact review evidence",
    )
    sidecar = _single_path(
        core_outputs,
        suffix=".agent_tasks.md",
        label="review sidecar",
    )
    review_json = _single_path(
        expected,
        suffix="_scene_review.json",
        label="review JSON",
    )
    report = _single_path(
        tuple(
            path
            for path in expected
            if path.endswith("_scene_review.md")
            and not path.endswith(".agent_tasks.md")
        ),
        suffix="_scene_review.md",
        label="review report",
    )
    if not candidate:
        raise ValueError(
            "candidate-review context contract requires a candidate path"
        )
    return scene_review_context_declaration(
        scene_id=scene_id,
        candidate_path=candidate,
        artifact_path=artifact,
        sidecar_path=sidecar,
        review_json_path=review_json,
        review_report_path=report,
    )


def _single_path(
    paths: tuple[str, ...],
    *,
    suffix: str,
    label: str,
) -> str:
    matches = tuple(path for path in paths if path.endswith(suffix))
    if len(matches) != 1:
        raise ValueError(
            f"candidate-review context contract requires one {label}"
        )
    return matches[0]


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
