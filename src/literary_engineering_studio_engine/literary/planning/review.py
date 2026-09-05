"""Digest-bound independent reviews for longform planning candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from ...agent_tasks import agent_task_completion_status, write_agent_tasks
from ...atomic_io import atomic_write_text


REVIEW_SCHEMA = "literary-engineering-workbench/longform-planning-review/v1"
TERMINAL_VERDICTS = {"pass", "revise", "block"}


@dataclass(frozen=True)
class LongformReviewSpec:
    kind: str
    label: str
    candidate: str
    author_task: str
    review: str
    report: str
    review_task: str
    author_states: tuple[str, ...]
    dimensions: tuple[str, ...]


@dataclass(frozen=True)
class LongformReviewPreparation:
    kind: str
    candidate_path: Path
    review_path: Path
    report_path: Path
    task_path: Path
    candidate_sha256: str
    writer_session_id: str


_SPECS = {
    "budget": LongformReviewSpec(
        kind="budget",
        label="word-budget expansion",
        candidate="plot/candidates/outlines/word_budget_expansion.md",
        author_task="plot/word_budget/word_budget.agent_tasks.md",
        review="reviews/word_budget/word_budget_review.json",
        report="reviews/word_budget/word_budget_review.md",
        review_task="reviews/word_budget/word_budget_review.agent_tasks.md",
        author_states=("budget-agent-task", "budget-revision"),
        dimensions=(
            "target_reconciliation",
            "causal_event_inventory",
            "volume_and_chapter_load",
            "character_and_relationship_change",
            "setup_and_payoff_capacity",
            "anti_padding",
        ),
    ),
    "scene_inventory": LongformReviewSpec(
        kind="scene_inventory",
        label="scene inventory",
        candidate="plot/candidates/scenes/word_budget_scene_inventory.md",
        author_task="plot/word_budget/scene_inventory_expansion.agent_tasks.md",
        review="reviews/word_budget/scene_inventory_review.json",
        report="reviews/word_budget/scene_inventory_review.md",
        review_task="reviews/word_budget/scene_inventory_review.agent_tasks.md",
        author_states=("scene-inventory-agent-task", "scene-inventory-revision"),
        dimensions=(
            "machine_readable_rows",
            "scene_count_reconciliation",
            "character_count_reconciliation",
            "scene_function_density",
            "causal_handoffs",
            "participant_identity_hygiene",
        ),
    ),
    "chapter_obligation": LongformReviewSpec(
        kind="chapter_obligation",
        label="chapter obligation plan",
        candidate="plot/candidates/chapters/chapter_obligation_plan.md",
        author_task="plot/chapter_obligations/chapter_obligations.agent_tasks.md",
        review="reviews/word_budget/chapter_obligation_review.json",
        report="reviews/word_budget/chapter_obligation_review.md",
        review_task="reviews/word_budget/chapter_obligation_review.agent_tasks.md",
        author_states=("chapter-obligation-agent-task", "chapter-obligation-revision"),
        dimensions=(
            "chapter_coverage",
            "reader_questions",
            "promise_and_payoff",
            "withheld_information",
            "chapter_change",
            "anti_summary",
        ),
    ),
}


def review_spec(kind: str) -> LongformReviewSpec:
    normalized = str(kind or "").strip().lower().replace("-", "_")
    try:
        return _SPECS[normalized]
    except KeyError as exc:
        raise ValueError(
            "longform review kind must be budget, scene_inventory, or chapter_obligation"
        ) from exc


def prepare_longform_review(
    project_root: Path, kind: str
) -> LongformReviewPreparation:
    root = project_root.resolve()
    spec = review_spec(kind)
    candidate = root / spec.candidate
    if not candidate.is_file():
        raise FileNotFoundError(f"longform planning candidate is missing: {spec.candidate}")
    author_ok, author_message = planning_candidate_status(root, spec.kind)
    if not author_ok:
        raise ValueError(author_message)

    digest = _sha256(candidate)
    writer = candidate_writer_identity(root, spec.kind)
    if not writer:
        raise ValueError(f"{spec.label} has no completed writer identity")
    target = root / spec.review
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_json(target)
    if (
        existing.get("schema") != REVIEW_SCHEMA
        or str(existing.get("review_kind") or "") != spec.kind
        or str(existing.get("candidate_sha256") or "") != digest
        or str(existing.get("writer_session_id") or "") != writer
    ):
        payload = {
            "schema": REVIEW_SCHEMA,
            "review_kind": spec.kind,
            "status": "pending_agent_judgment",
            "candidate_path": spec.candidate,
            "candidate_sha256": digest,
            "writer_session_id": writer,
            "reviewer_session_id": "",
            "verdict": "pending",
            "summary": "",
            "evidence_paths": [spec.candidate, "plot/word_budget/word_budget.json"],
            "findings": [],
            "required_changes": [],
            "checked_dimensions": list(spec.dimensions),
            "created_at": _now(),
        }
        atomic_write_text(target, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    sidecar = root / spec.review_task
    report = root / spec.report
    write_agent_tasks(
        sidecar,
        title=f"{spec.label} independent review",
        root=root,
        source_paths=[
            root / "project.yaml",
            root / "plot" / "word_budget" / "word_budget.json",
            candidate,
            target,
        ],
        tasks=[(
            f"independently review the exact {spec.label} candidate",
            _review_instruction(spec, digest),
        )],
        notes=[
            "Reviewer session must differ from the Writer identity already locked in the JSON template.",
            "The JSON verdict is authoritative. The Markdown report explains the judgment to users and cannot override JSON.",
            "Use revise whenever a required change remains; do not hide required work in a passing note.",
        ],
    )
    return LongformReviewPreparation(
        kind=spec.kind,
        candidate_path=candidate,
        review_path=target,
        report_path=report,
        task_path=sidecar,
        candidate_sha256=digest,
        writer_session_id=writer,
    )


def planning_candidate_status(project_root: Path, kind: str) -> tuple[bool, str]:
    root = project_root.resolve()
    spec = review_spec(kind)
    candidate = root / spec.candidate
    marker = agent_task_completion_status(root / spec.author_task, root=root)
    if marker.get("complete") is not True:
        return False, f"{spec.label} author task is incomplete: {marker.get('message')}"
    if not candidate.is_file() or not candidate.read_text(encoding="utf-8", errors="ignore").strip():
        return False, f"{spec.label} candidate is missing or empty: {spec.candidate}"
    return True, f"{spec.label} candidate is complete"


def planning_review_prepare_status(project_root: Path, kind: str) -> tuple[bool, str]:
    root = project_root.resolve()
    spec = review_spec(kind)
    candidate_ok, message = planning_candidate_status(root, spec.kind)
    if not candidate_ok:
        return False, message
    candidate = root / spec.candidate
    review = root / spec.review
    sidecar = root / spec.review_task
    payload = _read_json(review)
    expected_writer = candidate_writer_identity(root, spec.kind)
    if payload.get("schema") != REVIEW_SCHEMA:
        return False, f"{spec.label} review template is missing or invalid"
    if str(payload.get("review_kind") or "") != spec.kind:
        return False, f"{spec.label} review kind is invalid"
    if str(payload.get("candidate_path") or "") != spec.candidate:
        return False, f"{spec.label} review targets the wrong candidate"
    if str(payload.get("candidate_sha256") or "") != _sha256(candidate):
        return False, f"{spec.label} review must be prepared for the exact current candidate"
    if not expected_writer or str(payload.get("writer_session_id") or "") != expected_writer:
        return False, f"{spec.label} review writer identity is stale"
    if not sidecar.is_file():
        return False, f"{spec.label} independent review task sidecar is missing"
    return True, f"{spec.label} independent review is prepared"


def planning_review_status(
    project_root: Path, kind: str
) -> tuple[bool, str, str]:
    root = project_root.resolve()
    spec = review_spec(kind)
    prepared, message = planning_review_prepare_status(root, spec.kind)
    if not prepared:
        return False, message, ""
    payload = _read_json(root / spec.review)
    verdict = str(payload.get("verdict") or "").strip().lower()
    errors = _review_payload_errors(spec, payload)
    if not (root / spec.report).is_file():
        errors.append(f"human-readable review report is missing: {spec.report}")
    if errors:
        return False, f"{spec.label} review invalid: " + "; ".join(errors), verdict
    return True, f"{spec.label} independent review recorded: {verdict}", verdict


def planning_revision_review_status(
    project_root: Path, kind: str, prior_candidate_sha256: str
) -> tuple[bool, str]:
    """Validate the independent review that authorized a candidate revision.

    The candidate is expected to have changed by the time this gate runs, so
    validation binds to the pre-revision digest captured in the formal task
    instead of incorrectly comparing the review with the new candidate body.
    """

    root = project_root.resolve()
    spec = review_spec(kind)
    payload = _read_json(root / spec.review)
    errors: list[str] = []
    if payload.get("schema") != REVIEW_SCHEMA:
        errors.append("review schema is missing or invalid")
    if str(payload.get("review_kind") or "") != spec.kind:
        errors.append("review kind is invalid")
    if str(payload.get("candidate_path") or "") != spec.candidate:
        errors.append("review targets the wrong candidate")
    prior = str(prior_candidate_sha256 or "").strip().lower()
    if not prior or str(payload.get("candidate_sha256") or "").strip().lower() != prior:
        errors.append("review is not bound to the pre-revision candidate digest")
    errors.extend(_review_payload_errors(spec, payload))
    if str(payload.get("verdict") or "").strip().lower() != "revise":
        errors.append("candidate revision requires a completed revise verdict")
    if not (root / spec.report).is_file():
        errors.append(f"human-readable review report is missing: {spec.report}")
    marker = agent_task_completion_status(root / spec.review_task, root=root)
    if marker.get("complete") is not True:
        errors.append(f"review sidecar is incomplete: {marker.get('message')}")
    if errors:
        return False, f"{spec.label} pre-revision review invalid: " + "; ".join(errors)
    return True, f"{spec.label} revision is authorized by the exact prior review"


def planning_review_task_status(
    project_root: Path, kind: str
) -> tuple[bool, str, str]:
    root = project_root.resolve()
    spec = review_spec(kind)
    marker = agent_task_completion_status(root / spec.review_task, root=root)
    if marker.get("complete") is not True:
        return False, f"{spec.label} review sidecar is incomplete: {marker.get('message')}", ""
    return planning_review_status(root, spec.kind)


def planning_review_pass_status(project_root: Path, kind: str) -> tuple[bool, str]:
    complete, message, verdict = planning_review_task_status(project_root, kind)
    if not complete:
        return False, message
    if verdict != "pass":
        return False, f"{review_spec(kind).label} review verdict is {verdict}"
    return True, message


def all_planning_reviews_pass(project_root: Path) -> tuple[bool, str]:
    messages: list[str] = []
    for kind in _SPECS:
        passed, message = planning_review_pass_status(project_root, kind)
        if not passed:
            return False, message
        messages.append(message)
    return True, "; ".join(messages)


def planning_candidate_evidence_paths(project_root: Path, kind: str) -> list[str]:
    """Return portable evidence needed to identify a planning candidate writer."""

    root = project_root.resolve()
    spec = review_spec(kind)
    paths = [
        spec.candidate,
        spec.author_task,
        _completion_marker_relative(spec.author_task),
    ]
    writer_task = candidate_writer_task_path(root, spec.kind)
    if writer_task:
        paths.append(writer_task)
    return list(dict.fromkeys(paths))


def planning_review_evidence_paths(project_root: Path, kind: str) -> list[str]:
    """Return the complete sandbox-portable evidence set for one review."""

    spec = review_spec(kind)
    return list(
        dict.fromkeys(
            [
                *planning_candidate_evidence_paths(project_root, spec.kind),
                spec.review,
                spec.report,
                spec.review_task,
                _completion_marker_relative(spec.review_task),
            ]
        )
    )


def all_planning_review_evidence_paths(project_root: Path) -> list[str]:
    """Return all review evidence needed by materialization and scene gates."""

    paths: list[str] = []
    for kind in _SPECS:
        paths.extend(planning_review_evidence_paths(project_root, kind))
    return list(dict.fromkeys(paths))


def review_machine_contract(project_root: Path, kind: str) -> dict[str, str]:
    root = project_root.resolve()
    spec = review_spec(kind)
    payload = _read_json(root / spec.review)
    return {
        "review_kind": spec.kind,
        "candidate_path": spec.candidate,
        "candidate_sha256": str(payload.get("candidate_sha256") or ""),
        "writer_session_id": str(payload.get("writer_session_id") or ""),
    }


def candidate_writer_identity(project_root: Path, kind: str) -> str:
    task_path = candidate_writer_task_path(project_root, kind)
    if task_path:
        payload = _read_json(project_root.resolve() / task_path)
        identifier = str(payload.get("task_id") or Path(task_path).stem)
        return f"studio:writer:{identifier}"
    root = project_root.resolve()
    spec = review_spec(kind)
    marker = agent_task_completion_status(root / spec.author_task, root=root)
    if marker.get("complete") is True:
        digest = str(marker.get("task_digest") or "")[:16]
        return f"sidecar:writer:{spec.kind}:{digest}"
    return ""


def candidate_writer_task_path(project_root: Path, kind: str) -> str:
    """Return the latest completed formal task that wrote the candidate."""

    root = project_root.resolve()
    spec = review_spec(kind)
    completed: list[tuple[str, str]] = []
    for path in (root / "workflow" / "tasks").glob("*.task.json"):
        payload = _read_json(path)
        if (
            payload.get("status") == "complete"
            and str(payload.get("current_state") or "") in spec.author_states
            and spec.candidate in [str(item).replace("\\", "/") for item in payload.get("expected_outputs") or []]
        ):
            completed.append((str(payload.get("completed_at") or ""), path.relative_to(root).as_posix()))
    if completed:
        _completed_at, relative = max(completed)
        return relative
    return ""


def _completion_marker_relative(task_relative: str) -> str:
    if not task_relative.endswith(".agent_tasks.md"):
        raise ValueError(f"agent task path has unsupported suffix: {task_relative}")
    return task_relative[: -len(".agent_tasks.md")] + ".agent_completion.json"


def _review_instruction(spec: LongformReviewSpec, digest: str) -> str:
    dimensions = ", ".join(spec.dimensions)
    return (
        f"Review `{spec.candidate}` at SHA-256 `{digest}`. Fill `{spec.review}` and write the readable explanation to `{spec.report}`. "
        "Do not edit the candidate. The JSON must use status=complete and verdict=pass/revise/block. "
        "A pass requires no required_changes; revise/block requires concrete required_changes. "
        f"Check every declared dimension: {dimensions}. Cite exact project paths in evidence_paths and explain the judgment in summary. "
        "Machine-owned candidate identity, digest, writer identity, reviewer identity, and schema are normalized by Studio; do not invent them."
    )


def _review_payload_errors(spec: LongformReviewSpec, payload: dict[str, Any]) -> list[str]:
    return [
        *_review_identity_errors(payload),
        *_review_judgment_errors(payload),
        *_review_dimension_errors(spec, payload),
    ]


def _review_identity_errors(payload: dict[str, Any]) -> list[str]:
    writer = str(payload.get("writer_session_id") or "").strip()
    reviewer = str(payload.get("reviewer_session_id") or "").strip()
    errors: list[str] = []
    if str(payload.get("status") or "").strip().lower() != "complete":
        errors.append("status must be complete")
    if not reviewer or reviewer == writer:
        errors.append("reviewer session must be non-empty and independent from writer session")
    return errors


def _review_judgment_errors(payload: dict[str, Any]) -> list[str]:
    verdict = str(payload.get("verdict") or "").strip().lower()
    errors: list[str] = []
    if verdict not in TERMINAL_VERDICTS:
        errors.append("verdict must be pass, revise, or block")
    if not str(payload.get("summary") or "").strip():
        errors.append("summary must explain the review judgment")
    findings = payload.get("findings")
    required_changes = payload.get("required_changes")
    if not isinstance(findings, list):
        errors.append("findings must be a list")
    if not isinstance(required_changes, list):
        errors.append("required_changes must be a list")
    elif verdict == "pass" and required_changes:
        errors.append("a passing review cannot retain required_changes")
    elif verdict in {"revise", "block"} and not [
        item for item in required_changes if str(item).strip()
    ]:
        errors.append(f"{verdict} requires concrete required_changes")
    return errors


def _review_dimension_errors(spec: LongformReviewSpec, payload: dict[str, Any]) -> list[str]:
    checked = {str(item) for item in payload.get("checked_dimensions") or []}
    missing_dimensions = [item for item in spec.dimensions if item not in checked]
    if missing_dimensions:
        return ["checked_dimensions missing: " + ", ".join(missing_dimensions)]
    return []


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "LongformReviewPreparation",
    "LongformReviewSpec",
    "REVIEW_SCHEMA",
    "all_planning_review_evidence_paths",
    "all_planning_reviews_pass",
    "candidate_writer_identity",
    "candidate_writer_task_path",
    "planning_candidate_evidence_paths",
    "planning_candidate_status",
    "planning_review_evidence_paths",
    "planning_review_pass_status",
    "planning_review_prepare_status",
    "planning_revision_review_status",
    "planning_review_status",
    "planning_review_task_status",
    "prepare_longform_review",
    "review_machine_contract",
    "review_spec",
]
