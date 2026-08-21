"""Derived state for project-level canon and committee review."""
from __future__ import annotations

from pathlib import Path

from ..agent_tasks import agent_task_completion_status
from ..canon_evolver import canon_patch_backlog_items
from .state_common import _file_step, _read_json, _rel
def _review_audit_state(root: Path) -> dict[str, object]:
    canon_lint_json = root / "reviews" / "canon_lint.json"
    canon_review_json = root / "reviews" / "agent" / "canon_review.json"
    canon_review_md = canon_review_json.with_suffix(".md")
    canon_review_task = canon_review_json.with_suffix(".agent_tasks.md")
    canon_review_completion = canon_review_json.with_suffix(
        ".agent_completion.json"
    )
    committee_json = root / "reviews" / "agent" / "committee_project-final-audit.json"
    committee_md = committee_json.with_suffix(".md")
    committee_task = committee_json.with_suffix(".agent_tasks.md")
    committee_completion = committee_json.with_suffix(".agent_completion.json")
    longform_json = root / "reviews" / "longform" / "longform_audit.json"
    canon_backlog = _canon_backlog_step(root)
    review_resets = [
        marker
        for marker in (canon_review_completion, committee_completion)
        if _is_recheck_required(marker)
    ]
    steps = [
        canon_backlog,
        _canon_lint_step(root, canon_lint_json, refresh_after=review_resets),
        _fresh_file_step(
            root,
            "canon-review-task-file",
            canon_review_task,
            "run agent-canon-review to create the platform-agent canon review sidecar",
            refresh_after=[canon_lint_json],
        ),
        _review_agent_step(root, "canon-review-agent-task", canon_review_task, canon_review_json, canon_review_md, "complete canon review sidecar, JSON, Markdown, and completion marker"),
        _canon_review_pass_step(root, canon_review_json),
        _fresh_file_step(
            root,
            "longform-audit-file",
            longform_json,
            "run longform-audit to create structural longform audit JSON/Markdown",
            refresh_after=[canon_review_completion, *review_resets],
        ),
        _fresh_file_step(
            root,
            "committee-task-file",
            committee_task,
            "run agent-committee --subject project-final-audit --source reviews/agent/canon_review.md",
            refresh_after=[canon_review_completion, longform_json],
        ),
        _review_agent_step(root, "committee-agent-task", committee_task, committee_json, committee_md, "complete committee sidecar, JSON, Markdown, and completion marker"),
        _committee_pass_step(root, committee_json),
    ]
    first_open = next((step for step in steps if step["status"] != "pass"), None)
    return {
        "target_id": "project-review",
        "scene_id": "project-review",
        "patch": str(canon_backlog.get("patch") or ""),
        "patch_id": str(canon_backlog.get("patch_id") or ""),
        "candidate_sha256": str(canon_backlog.get("candidate_sha256") or ""),
        "approval_decision": str(canon_backlog.get("approval_decision") or ""),
        "status": "ready" if first_open is None else "blocked",
        "current_step": first_open["key"] if first_open else "ready",
        "next_action": first_open["next_action"] if first_open else "",
        "steps": steps,
    }


def _canon_backlog_step(root: Path) -> dict[str, object]:
    pending = [
        item
        for item in canon_patch_backlog_items(root)
        if str(item.get("status") or "") not in {"applied", "not_applicable"}
    ]
    if not pending:
        return {
            "key": "canon-patch-backlog",
            "status": "pass",
            "path": "canon/patches",
            "message": "no unapplied canon patch candidates",
            "next_action": "",
        }

    item = pending[0]
    patch = str(item.get("patch") or "")
    patch_id = str(item.get("approval_run_id") or Path(patch).stem)
    status = str(item.get("status") or "invalid")
    decision = str(item.get("approval_decision") or "").strip().lower()
    approval_current = item.get("approval_current") is True
    if status in {"invalid", "task_incomplete"} or (approval_current and decision in {"revise", "reject"}):
        key = "canon-patch-revision"
        message = str(item.get("message") or "canon patch requires revision")
        if approval_current and decision in {"revise", "reject"}:
            message = f"current canon patch was {decision}: {item.get('approval_notes') or 'revision requested'}"
        next_action = "revise the canon patch candidate and its report, then complete its sidecar before requesting fresh approval"
    elif approval_current and decision == "defer":
        key = "canon-patch-deferred"
        message = "canon patch is intentionally deferred for later user decision"
        next_action = "resume this canon patch from the decision panel when the project is ready to approve, revise, or reject it"
    elif status == "needs_approval":
        key = "canon-patch-approval"
        message = "canon patch requires a decision bound to its current content"
        next_action = f"record approve, revise, reject, or defer for canon patch `{patch_id}`"
    elif status == "pending_apply":
        key = "canon-patch-apply"
        message = "canon patch is approved and ready for durable ledger apply"
        next_action = f"run canon-apply for `{patch}` with approval run_id `{patch_id}`"
    else:
        key = "canon-patch-revision"
        message = str(item.get("message") or status)
        next_action = "repair the canon patch candidate before project-level review"
    return {
        "key": key,
        "status": status,
        "path": patch,
        "patch": patch,
        "patch_id": patch_id,
        "candidate_sha256": str(item.get("candidate_sha256") or ""),
        "approval_decision": decision,
        "message": message,
        "next_action": next_action,
    }


def _canon_lint_step(
    root: Path,
    json_path: Path,
    *,
    refresh_after: list[Path] | None = None,
) -> dict[str, object]:
    report = json_path.with_suffix(".md")
    if not json_path.exists() or not report.exists():
        return {
            "key": "canon-lint-file",
            "status": "missing",
            "path": _rel(json_path, root),
            "message": "missing canon lint report or JSON",
            "next_action": "run canon-lint before platform-agent canon review",
        }
    stale_source = _newer_source(json_path, refresh_after or [])
    if stale_source is not None:
        return {
            "key": "canon-lint-file",
            "status": "stale",
            "path": _rel(json_path, root),
            "message": (
                "canon lint predates project repair reset: "
                f"{_rel(stale_source, root)}"
            ),
            "next_action": "rerun canon-lint against the repaired project targets",
        }
    payload = _read_json(json_path)
    status = str(payload.get("status") or "").strip().lower()
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    blocking = int(summary.get("blocking_count", 0) or 0)
    return {
        "key": "canon-lint-file",
        "status": "pass" if status in {"pass", "pass_with_warnings"} and blocking == 0 else status or "blocked",
        "path": _rel(json_path, root),
        "message": f"status={status or 'missing'}; blocking={blocking}; warning={summary.get('warning_count', 0)}",
        "next_action": "" if status in {"pass", "pass_with_warnings"} and blocking == 0 else "fix canon-lint blocking issues before Agent canon review",
    }


def _review_agent_step(root: Path, key: str, task_path: Path, json_path: Path, report_path: Path, next_action: str) -> dict[str, object]:
    state = agent_task_completion_status(task_path, root=root)
    missing = [_rel(path, root) for path in (json_path, report_path) if not path.exists()]
    complete = state.get("complete") is True and not missing
    message = str(state.get("message") or "")
    if missing:
        message = (message + "; " if message else "") + "missing " + ", ".join(missing)
    stale = _newer_source(json_path, [task_path]) or _newer_source(
        report_path, [task_path]
    )
    if stale is not None:
        complete = False
        message = (message + "; " if message else "") + (
            "review artifacts predate current sidecar"
        )
    return {
        "key": key,
        "status": "pass" if complete else str(state.get("status") or "pending"),
        "path": _rel(task_path, root),
        "completion": state.get("completion", ""),
        "message": message,
        "next_action": "" if complete else next_action,
    }


def _fresh_file_step(
    root: Path,
    key: str,
    path: Path,
    next_action: str,
    *,
    refresh_after: list[Path],
) -> dict[str, object]:
    step = _file_step(key, path, next_action)
    if step["status"] != "pass":
        return step
    stale_source = _newer_source(path, refresh_after)
    if stale_source is None:
        return step
    return {
        **step,
        "status": "stale",
        "message": f"artifact predates {_rel(stale_source, root)}",
        "next_action": next_action,
    }


def _newer_source(target: Path, sources: list[Path]) -> Path | None:
    if not target.is_file():
        return None
    target_time = target.stat().st_mtime_ns
    return next(
        (
            source
            for source in sources
            if source.is_file() and source.stat().st_mtime_ns > target_time
        ),
        None,
    )


def _is_recheck_required(path: Path) -> bool:
    payload = _read_json(path)
    return str(payload.get("status") or "").strip().lower() == "recheck_required"


def _canon_review_pass_step(root: Path, json_path: Path) -> dict[str, object]:
    payload = _read_json(json_path)
    conclusion = str(payload.get("conclusion") or "").strip().lower()
    blocking = payload.get("blocking_issues") if isinstance(payload.get("blocking_issues"), list) else []
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    unresolved = payload.get("unresolved_facts") if isinstance(payload.get("unresolved_facts"), list) else []
    timeline = payload.get("timeline_risks") if isinstance(payload.get("timeline_risks"), list) else []
    passed = conclusion == "pass" and not blocking and not warnings and not unresolved and not timeline
    message = f"conclusion={conclusion or 'missing'}; blocking={len(blocking)}; warnings={len(warnings)}; unresolved={len(unresolved)}; timeline={len(timeline)}"
    return {
        "key": "canon-review-pass",
        "status": "pass" if passed else conclusion or "missing",
        "path": _rel(json_path, root),
        "message": message,
        "next_action": (
            ""
            if passed
            else "repair every finding at its declared target_path, refresh canon-lint, reset review evidence, and run a fresh independent canon review"
        ),
    }


def _committee_pass_step(root: Path, json_path: Path) -> dict[str, object]:
    payload = _read_json(json_path)
    recommendation = str(payload.get("final_recommendation") or "").strip().lower()
    action_items = payload.get("action_items") if isinstance(payload.get("action_items"), list) else []
    disagreements = payload.get("disagreements") if isinstance(payload.get("disagreements"), list) else []
    passed = recommendation == "approve" and not action_items and not disagreements
    return {
        "key": "committee-pass",
        "status": "pass" if passed else recommendation or "missing",
        "path": _rel(json_path, root),
        "message": f"final_recommendation={recommendation or 'missing'}; action_items={len(action_items)}; disagreements={len(disagreements)}",
        "next_action": (
            ""
            if passed
            else "repair declared project targets, refresh deterministic audits, reset canon/committee evidence, and rerun both independent reviews"
        ),
    }
