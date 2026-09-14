"""Controlled Project Agent actions backed by existing application services."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from ..application.failures import present_run
from .contracts import ProjectAgentActionDependencies


RecordDirection = Callable[..., dict[str, Any]]


def dependencies_from_actions(
    *,
    record_direction: RecordDirection,
    autopilot: Any,
    config: dict[str, Any] | None = None,
    current_choices: Callable[..., dict[str, Any]] | None = None,
    record_choice: Callable[..., dict[str, Any]] | None = None,
    save_quality: Callable[..., dict[str, Any]] | None = None,
    save_rhythm: Callable[..., dict[str, Any]] | None = None,
    style_mounts: Any | None = None,
    candidate_promotions: Any | None = None,
    launch_worker: Callable[[dict[str, str]], dict[str, Any]] | None = None,
    invalidate_project: Callable[[Path, str], Any] | None = None,
) -> ProjectAgentActionDependencies:
    settings = config or {}

    def save_direction(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        message = str(arguments.get("message") or "").strip()
        if not message:
            raise ValueError("project_record_direction requires a message")
        result = record_direction(root, message, actor="project-agent")
        record = result.get("record") if isinstance(result.get("record"), dict) else {}
        return {
            "ok": True,
            "operation": "record_direction",
            "record": record,
            "digest": str(result.get("digest") or ""),
            "receipt": _receipt("record_direction", record),
        }

    def control_creation(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        operation = str(arguments.get("operation") or "").strip().lower()
        if operation not in {"start", "pause", "resume"}:
            raise ValueError("creation_control operation must be start, pause, or resume")
        if operation == "start":
            policy = autopilot.policy(root).get("policy", {})
            if str(policy.get("literary_kernel") or "") != "lean-v2":
                autopilot.migrate_kernel(root, target_kernel="lean-v2")
            run = autopilot.start(root)
        else:
            status = autopilot.status(root)
            active = status.get("run") if isinstance(status.get("run"), dict) else {}
            run_id = str(active.get("run_id") or "").strip()
            if not run_id:
                raise ValueError("creation_control requires an existing creation run")
            if operation == "pause":
                reason = str(arguments.get("reason") or "project-agent-user-request").strip()
                run = autopilot.pause(run_id, reason=reason[:500])
            else:
                run = autopilot.resume(run_id, authorized=True)
        presented = present_run(run)
        return {
            "ok": True,
            "operation": operation,
            "literary_kernel": str(
                (run.get("policy") if isinstance(run.get("policy"), dict) else {}).get("literary_kernel")
                or autopilot.policy(root).get("policy", {}).get("literary_kernel")
                or ""
            ),
            "run": presented,
            "receipt": _receipt(f"creation_{operation}", presented),
        }

    def resolve_decision(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if current_choices is None or record_choice is None:
            raise RuntimeError("Project Agent decision service is unavailable")
        choice_id = str(arguments.get("choice_id") or "").strip()
        selected = str(arguments.get("selected") or "").strip()
        if not choice_id or not selected:
            raise ValueError("project_decision_resolve requires choice_id and selected")
        available = current_choices(settings, root)
        rows = available.get("choices") if isinstance(available.get("choices"), list) else []
        choice = next(
            (item for item in rows if isinstance(item, dict) and str(item.get("choice_id") or "") == choice_id),
            None,
        )
        if choice is None:
            raise ValueError("the requested project decision is no longer pending")
        option_ids = {
            str(item.get("id") or item.get("label") or "").strip()
            for item in choice.get("options", [])
            if isinstance(item, dict)
        }
        if selected not in option_ids:
            raise ValueError("selected decision option is not available")
        payload = {
            **choice,
            "selected": selected,
            "rationale": str(arguments.get("rationale") or "项目 Agent 根据当前创作目标完成选择。").strip(),
            "actor": "project-agent",
        }
        result = record_choice(settings, root, payload)
        if invalidate_project is not None:
            invalidate_project(root, "project-agent-decision")
        _resume_after_decision(autopilot, root, result)
        return {
            "ok": True,
            "operation": "resolve_decision",
            "choice_id": choice_id,
            "selected": selected,
            "consumed": bool(result.get("consumed")),
            "effect": result.get("effect") or {},
            "receipt": _receipt("resolve_decision", result),
        }

    def update_quality(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if save_quality is None:
            raise RuntimeError("Project Agent quality service is unavailable")
        profile = arguments.get("profile")
        if not isinstance(profile, dict):
            raise ValueError("project_quality_update requires a profile object")
        saved = save_quality(root, profile, updated_by="project-agent")
        if invalidate_project is not None:
            invalidate_project(root, "project-agent-quality")
        return {
            "ok": True,
            "operation": "update_quality",
            "profile": saved,
            "effect": "future-candidates",
            "receipt": _receipt("update_quality", saved),
        }

    def update_rhythm(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if save_rhythm is None:
            raise RuntimeError("Project Agent rhythm service is unavailable")
        entries = arguments.get("entries")
        if not isinstance(entries, list):
            raise ValueError("project_rhythm_update requires an entries array")
        book_profile = arguments.get("book_profile")
        saved = save_rhythm(
            root,
            entries,
            updated_by="project-agent",
            book_profile=book_profile if isinstance(book_profile, dict) else None,
        )
        if invalidate_project is not None:
            invalidate_project(root, "project-agent-rhythm")
        return {
            "ok": True,
            "operation": "update_rhythm",
            "plan": saved,
            "effect": "future-candidates",
            "receipt": _receipt("update_rhythm", saved),
        }

    def mount_style(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if style_mounts is None:
            raise RuntimeError("Project Agent style mount service is unavailable")
        identity = {
            field: str(arguments.get(field) or "").strip()
            for field in ("style_id", "version_id", "content_hash")
        }
        if not all(identity.values()):
            raise ValueError("project_style_mount requires exact style_id, version_id, and content_hash")
        preview = style_mounts.preview(root, **identity)
        result = style_mounts.mount_confirmed(
            root,
            **identity,
            preview_revision=str(preview.get("revision") or ""),
            scope=str(arguments.get("scope") or "project"),
            priority=str(arguments.get("priority") or "highest"),
        )
        if invalidate_project is not None:
            invalidate_project(root, "project-agent-style")
        return {
            "ok": True,
            "operation": "mount_style",
            "style_id": identity["style_id"],
            "version_id": identity["version_id"],
            "status": result.get("status"),
            "impact": result.get("impact") or {},
            "receipt": _receipt("mount_style", result),
        }

    def promote_asset(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if candidate_promotions is None or launch_worker is None:
            raise RuntimeError("Project Agent asset promotion service is unavailable")
        candidate_id = str(arguments.get("candidate_id") or "").strip()
        if not candidate_id:
            raise ValueError("project_asset_promote requires candidate_id")
        detail = candidate_promotions.detail(root, candidate_id)
        request = candidate_promotions.worker_request(
            root,
            candidate_id,
            preview_digest=str(detail.get("preview_digest") or ""),
        )
        job = launch_worker(request)
        return {
            "ok": True,
            "operation": "promote_asset",
            "candidate_id": candidate_id,
            "job_id": str(job.get("job_id") or ""),
            "status": str(job.get("status") or "queued"),
            "receipt": _receipt("promote_asset", job),
        }

    return ProjectAgentActionDependencies(
        save_direction,
        control_creation,
        resolve_decision,
        update_quality,
        update_rhythm,
        mount_style,
        promote_asset,
    )


def _resume_after_decision(autopilot: Any, root: Path, result: Mapping[str, Any]) -> None:
    if result.get("consumed") is not True:
        return
    status = autopilot.status(root)
    run = status.get("run") if isinstance(status.get("run"), dict) else {}
    if run.get("status") == "paused" and run.get("stop_reason") in {
        "human-decision-required",
        "steward-escalation",
        "lean-scene-approval-required",
    }:
        autopilot.resume(str(run.get("run_id") or ""), authorized=True)


def _receipt(operation: str, value: Mapping[str, Any]) -> dict[str, str]:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return {
        "operation": operation,
        "token": sha256(payload.encode("utf-8")).hexdigest()[:20],
    }


__all__ = ["dependencies_from_actions"]
