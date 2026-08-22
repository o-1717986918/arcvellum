"""Digest-bound coordination for deterministic preflight repair turns."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ..contracts import TaskPackage
from ..preflight.common import PreflightIssue, PreflightResult
from .repair_rendering import (
    MAX_EXCERPT_CHARACTERS,
    MAX_TOTAL_EXCERPT_CHARACTERS,
    bounded_output_excerpt,
    render_repair_prompt,
)
from .repair_scope import repair_scope
from .repair_stability import regression_guard
from .repair_snapshots import (
    file_sha256,
    restore_outputs,
    snapshot_outputs,
)
from .sandbox import SandboxManifest
from .reasoning_policy import (
    ReasoningBudget,
    ReasoningUsage,
    decide_reasoning_action,
)


REPAIR_CONTEXT_SCHEMA = "arcvellum/repair-context/v1"
REPAIR_CONTEXT_REVISION = "2026-08-20.2"


@dataclass(frozen=True)
class PreparedRepairContext:
    """Prompt and audit identity for one repair turn."""

    prompt: str
    context_digest: str
    artifact_path: Path
    issue_ids: tuple[str, ...]
    write_scope_mode: str
    target_count: int
    protected_count: int
    excerpt_characters: int
    repair_targets: tuple[str, ...]
    repair_references: tuple[str, ...]
    reasoning_level: str

    def event_fields(self) -> dict[str, object]:
        return {
            "repair_context_digest": self.context_digest,
            "repair_prompt_characters": len(self.prompt),
            "repair_excerpt_characters": self.excerpt_characters,
            "repair_target_count": self.target_count,
            "repair_reference_count": len(self.repair_references),
            "repair_protected_count": self.protected_count,
            "repair_write_scope_mode": self.write_scope_mode,
            "repair_reasoning_level": self.reasoning_level,
            "repair_context_artifact": (
                f"repairs/{self.artifact_path.parent.name}/"
                f"{self.artifact_path.name}"
            ),
        }


class RepairContextCoordinator:
    """Prepare repair prompts and restore outputs that already passed."""

    def __init__(
        self,
        task: TaskPackage,
        sandbox: SandboxManifest,
        *,
        reasoning_budget: ReasoningBudget | None = None,
        same_session_required: bool = True,
    ) -> None:
        self.task = task
        self.sandbox = sandbox
        self.reasoning_budget = reasoning_budget
        self.same_session_required = same_session_required
        self._pending: dict[str, object] | None = None
        self._seen_issue_codes: set[str] = set()
        self._previous_target_digests: dict[str, str] = {}

    def prepare(
        self,
        result: PreflightResult,
        attempt: int,
        maximum: int,
    ) -> PreparedRepairContext:
        if self._pending is not None:
            raise RuntimeError("previous repair output protection was not finalized")
        write_scope_mode, targets, protected = repair_scope(
            self.task,
            result.issues,
        )
        attempt_root = _repair_attempt_root(self.sandbox.run_root, attempt)
        snapshot_root = attempt_root / "protected"
        snapshot = snapshot_outputs(
            self.sandbox.workspace,
            snapshot_root,
            protected,
        )
        issue_rows = _issue_rows(result.issues, targets)
        invalid_outputs, excerpt_characters = _invalid_output_rows(
            self.sandbox.workspace,
            targets,
            result.issues,
        )
        protected_outputs = _protected_output_rows(
            self.sandbox.workspace,
            protected,
        )
        stagnation, target_digests = _stagnation_contract(
            invalid_outputs, self._previous_target_digests
        )
        reasoning_contract = _reasoning_repair_contract(self.reasoning_budget, result, attempt)
        repair_references = _repair_reference_paths(
            self.task,
            result.issues,
            self.sandbox.workspace,
        )
        semantic_payload = _semantic_payload_with_guard(
            self.task,
            result,
            attempt,
            maximum,
            write_scope_mode,
            targets,
            issue_rows,
            invalid_outputs,
            protected_outputs,
            excerpt_characters,
            reasoning_contract,
            self._seen_issue_codes,
        )
        semantic_payload["repair_session"] = "same-session" if self.same_session_required else "fresh-bounded-session"
        semantic_payload["repair_references"] = list(repair_references)
        semantic_payload["stagnation"] = stagnation
        self._previous_target_digests = target_digests
        digest = _canonical_sha256(semantic_payload)
        payload = {**semantic_payload, "context_digest": digest}
        prompt = render_repair_prompt(payload)
        payload["transport"] = {
            "prompt_characters": len(prompt),
            "same_session_required": self.same_session_required,
            "full_task_replay": False,
        }
        artifact_path = _write_context_artifact(attempt_root, payload)
        self._pending = {
            "context_digest": digest,
            "snapshot": snapshot,
            "snapshot_root": snapshot_root,
        }
        return PreparedRepairContext(
            prompt=prompt,
            context_digest=digest,
            artifact_path=artifact_path,
            issue_ids=_issue_ids(issue_rows),
            write_scope_mode=write_scope_mode,
            target_count=len(targets),
            protected_count=len(protected),
            excerpt_characters=excerpt_characters,
            repair_targets=targets,
            repair_references=repair_references,
            reasoning_level=str(reasoning_contract.get("level") or ""),
        )

    def finalize(self) -> dict[str, object]:
        pending = self._pending
        if pending is None:
            return _empty_finalize_result()
        snapshot = pending["snapshot"]
        restored = restore_outputs(
            self.sandbox.workspace,
            Path(str(pending["snapshot_root"])),
            snapshot,
        )
        self._pending = None
        return {
            "repair_context_digest": str(
                pending["context_digest"]
            ),
            "protected_output_count": len(_mapping(snapshot)),
            "restored_output_count": len(restored),
            "restored_outputs": list(restored),
        }


def _repair_attempt_root(run_root: Path, attempt: int) -> Path:
    return run_root / "repairs" / f"attempt-{max(1, int(attempt)):02d}"


def _stagnation_contract(
    invalid_outputs: list[dict[str, object]],
    previous_target_digests: Mapping[str, str],
) -> tuple[dict[str, object], dict[str, str]]:
    target_digests = {
        str(item.get("path") or ""): str(item.get("sha256") or "")
        for item in invalid_outputs
        if str(item.get("path") or "")
    }
    unchanged = bool(
        previous_target_digests and target_digests == previous_target_digests
    )
    return {
        "active": unchanged,
        "target_digests": target_digests,
        "instruction": (
            "previous repair wrote the target without changing its bytes"
            if unchanged else ""
        ),
    }, target_digests


def _repair_reference_paths(
    task: TaskPackage,
    issues: tuple[PreflightIssue, ...],
    workspace: Path,
) -> tuple[str, ...]:
    needs_exact_source = any(
        "anti_evasion_rows" in f"{issue.message} {issue.repair}"
        or "exact-source" in f"{issue.message} {issue.repair}".casefold()
        or "exact source body" in f"{issue.message} {issue.repair}".casefold()
        for issue in issues
    )
    if not needs_exact_source:
        return ()
    source = str(task.payload.get("revision_source") or "").strip().replace("\\", "/")
    if not source or source.startswith("/") or ":" in source or ".." in source.split("/"):
        return ()
    authorized = {
        str(item).strip().replace("\\", "/")
        for key in ("agent_source_paths", "source_paths", "context_must_inline_paths")
        for item in (task.payload.get(key) or [])
        if str(item).strip()
    }
    if source not in authorized or not (workspace / Path(source)).is_file():
        return ()
    return (source,)


def _issue_ids(issue_rows: list[dict[str, str]]) -> tuple[str, ...]:
    return tuple(str(item["issue_id"]) for item in issue_rows)


def _semantic_payload(
    task: TaskPackage,
    result: PreflightResult,
    attempt: int,
    maximum: int,
    write_scope_mode: str,
    targets: tuple[str, ...],
    issue_rows: list[dict[str, str]],
    invalid_outputs: list[dict[str, object]],
    protected_outputs: list[dict[str, object]],
    excerpt_characters: int,
    reasoning_contract: Mapping[str, object],
) -> dict[str, object]:
    return {
        "schema": REPAIR_CONTEXT_SCHEMA,
        "revision": REPAIR_CONTEXT_REVISION,
        "task_id": task.task_id,
        "route": task.route,
        "current_state": task.current_state,
        "attempt": max(1, int(attempt)),
        "maximum_attempts": max(1, int(maximum)),
        "write_scope_mode": write_scope_mode,
        "repair_targets": list(targets),
        "issues": issue_rows,
        "invalid_outputs": invalid_outputs,
        "protected_outputs": protected_outputs,
        "budgets": {
            "maximum_excerpt_characters_per_output": (
                MAX_EXCERPT_CHARACTERS
            ),
            "maximum_total_excerpt_characters": (
                MAX_TOTAL_EXCERPT_CHARACTERS
            ),
            "actual_excerpt_characters": excerpt_characters,
            "reasoning": dict(reasoning_contract),
        },
        "preflight_issue_count": len(result.issues),
    }


def _semantic_payload_with_guard(
    task: TaskPackage,
    result: PreflightResult,
    attempt: int,
    maximum: int,
    write_scope_mode: str,
    targets: tuple[str, ...],
    issue_rows: list[dict[str, str]],
    invalid_outputs: list[dict[str, object]],
    protected_outputs: list[dict[str, object]],
    excerpt_characters: int,
    reasoning_contract: Mapping[str, object],
    seen_issue_codes: set[str],
) -> dict[str, object]:
    current_codes = {item.code for item in result.issues}
    payload = _semantic_payload(
        task, result, attempt, maximum, write_scope_mode, targets,
        issue_rows, invalid_outputs, protected_outputs, excerpt_characters,
        reasoning_contract,
    )
    payload["regression_guard"] = regression_guard(task, seen_issue_codes | current_codes)
    seen_issue_codes.update(current_codes)
    return payload


def _reasoning_repair_contract(
    budget: ReasoningBudget | None,
    result: PreflightResult,
    attempt: int,
) -> dict[str, object]:
    if budget is None:
        return {"status": "unavailable", "action": "keep"}
    decision = decide_reasoning_action(
        budget,
        current_level=budget.initial_level,
        attempt=max(1, int(attempt)),
        issue_categories=(item.code for item in result.issues),
        evidence_conflict=any("conflict" in item.code for item in result.issues),
        usage=ReasoningUsage(),
    )
    return {
        "status": "recommended",
        "initial_level": budget.initial_level,
        "maximum_level": budget.maximum_level,
        "remaining_escalations": budget.max_escalations,
        **decision.as_dict(),
    }


def _write_context_artifact(
    attempt_root: Path,
    payload: Mapping[str, object],
) -> Path:
    attempt_root.mkdir(parents=True, exist_ok=True)
    artifact_path = attempt_root / "repair-context.json"
    artifact_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return artifact_path


def _issue_rows(
    issues: tuple[PreflightIssue, ...],
    targets: tuple[str, ...],
) -> list[dict[str, str]]:
    allowed = set(targets)
    rows: list[dict[str, str]] = []
    for issue in issues:
        relative, selector = _split_issue_path(issue.path)
        rows.append(
            {
                "issue_id": _issue_id(issue),
                "code": issue.code,
                "path": issue.path,
                "output_path": relative if relative in allowed else "",
                "selector": selector if relative in allowed else "",
                "message": issue.message,
                "repair": issue.repair,
            }
        )
    return rows


def _invalid_output_rows(
    workspace: Path,
    targets: tuple[str, ...],
    issues: tuple[PreflightIssue, ...],
) -> tuple[list[dict[str, object]], int]:
    selectors = _selectors_by_target(issues, targets)
    remaining = MAX_TOTAL_EXCERPT_CHARACTERS
    rows: list[dict[str, object]] = []
    total = 0
    for relative in targets:
        path = workspace / Path(relative)
        budget = min(MAX_EXCERPT_CHARACTERS, max(0, remaining))
        excerpt = bounded_output_excerpt(
            path,
            selectors.get(relative, ()),
            budget,
        )
        excerpt_length = len(excerpt)
        remaining -= excerpt_length
        total += excerpt_length
        rows.append(
            {
                "path": relative,
                "status": "present" if path.is_file() else "missing",
                "sha256": file_sha256(path) if path.is_file() else "",
                "bytes": path.stat().st_size if path.is_file() else 0,
                "selectors": list(selectors.get(relative, ())),
                "excerpt": excerpt,
                "excerpt_characters": excerpt_length,
            }
        )
    return rows, total


def _protected_output_rows(
    workspace: Path,
    protected: tuple[str, ...],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for relative in protected:
        path = workspace / Path(relative)
        rows.append(
            {
                "path": relative,
                "status": "present" if path.is_file() else "missing",
                "sha256": file_sha256(path) if path.is_file() else "",
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return rows


def _selectors_by_target(
    issues: tuple[PreflightIssue, ...],
    targets: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    allowed = set(targets)
    collected: dict[str, list[str]] = {}
    for issue in issues:
        relative, selector = _split_issue_path(issue.path)
        if relative not in allowed or not selector:
            continue
        values = collected.setdefault(relative, [])
        if selector not in values:
            values.append(selector)
    return {
        path: tuple(values)
        for path, values in collected.items()
    }


def _issue_id(issue: PreflightIssue) -> str:
    identity = "\0".join(
        (
            issue.code.strip(),
            issue.path.replace("\\", "/").strip(),
            issue.message.strip(),
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    return f"{issue.code}-{digest}"


def _split_issue_path(value: str) -> tuple[str, str]:
    normalized = value.replace("\\", "/").strip()
    relative, separator, selector = normalized.partition("#")
    return relative, selector if separator else ""


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _empty_finalize_result() -> dict[str, object]:
    return {
        "repair_context_digest": "",
        "protected_output_count": 0,
        "restored_output_count": 0,
        "restored_outputs": [],
    }


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


__all__ = [
    "PreparedRepairContext",
    "REPAIR_CONTEXT_REVISION",
    "REPAIR_CONTEXT_SCHEMA",
    "RepairContextCoordinator",
]
