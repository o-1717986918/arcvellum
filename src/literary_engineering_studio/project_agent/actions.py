"""Controlled Project Agent actions backed by existing application services."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ..application.failures import present_run
from .action_receipts import action_receipt, goal_result
from .contracts import ProjectAgentActionDependencies
from .scope import work_reference


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
    create_project: Callable[..., dict[str, Any]] | None = None,
    goal_evidence: Callable[[Path], Mapping[str, Any]] | None = None,
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
            "receipt": action_receipt("record_direction", record),
        }

    def control_creation(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        operation = str(arguments.get("operation") or "").strip().lower()
        if operation not in {"start", "pause", "resume"}:
            raise ValueError("creation_control operation must be start, pause, or resume")
        if operation == "start":
            run = _start_creation(root, autopilot)
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
            "receipt": action_receipt(f"creation_{operation}", presented),
        }

    def resolve_decision(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        return _resolve_decision(
            root,
            arguments,
            settings=settings,
            current_choices=current_choices,
            record_choice=record_choice,
            invalidate_project=invalidate_project,
            autopilot=autopilot,
        )

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
            "receipt": action_receipt("update_quality", saved),
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
            "receipt": action_receipt("update_rhythm", saved),
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
            "receipt": action_receipt("mount_style", result),
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
            "receipt": action_receipt("promote_asset", job),
        }

    def create_work(_root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if create_project is None:
            raise RuntimeError("Project Agent project creation service is unavailable")
        title = str(arguments.get("title") or "").strip()
        if not title:
            raise ValueError("project_create requires a title")
        created = create_project(
            title=title,
            folder_name="",
            work_type=str(arguments.get("work_type") or "novel").strip() or "novel",
            target_length=max(1000, int(arguments.get("target_length") or 30000)),
            target_chapters=max(0, int(arguments.get("target_chapters") or 0)),
            target_scenes=max(0, int(arguments.get("target_scenes") or 0)),
            premise=str(arguments.get("premise") or "").strip(),
            genre=str(arguments.get("genre") or "").strip(),
        )
        reference = work_reference(created)
        return {
            "ok": True,
            "operation": "create_project",
            "work": reference,
            "receipt": action_receipt("create_project", reference),
        }

    def manage_goal(root: Path, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        result = _manage_goal(
            root,
            arguments,
            record_direction=record_direction,
            autopilot=autopilot,
            current_choices=current_choices,
            settings=settings,
        )
        if result.get("ok") is not True or goal_evidence is None:
            return result
        reader = goal_evidence(root)
        units = reader.get("units") if isinstance(reader.get("units"), list) else []
        return {
            **result,
            "formal_work": {
                "source": "reader-manifest",
                "unit_count": int(reader.get("unit_count") or len(units)),
                "chinese_content_chars": int(reader.get("total_chinese_content_chars") or 0),
            },
        }

    return ProjectAgentActionDependencies(
        save_direction,
        control_creation,
        resolve_decision,
        update_quality,
        update_rhythm,
        mount_style,
        promote_asset,
        create_work if create_project is not None else None,
        manage_goal,
    )


def _resolve_decision(
    root: Path,
    arguments: Mapping[str, Any],
    *,
    settings: dict[str, Any],
    current_choices: Callable[..., dict[str, Any]] | None,
    record_choice: Callable[..., dict[str, Any]] | None,
    invalidate_project: Callable[[Path, str], Any] | None,
    autopilot: Any,
) -> Mapping[str, Any]:
    if current_choices is None or record_choice is None:
        raise RuntimeError("Project Agent decision service is unavailable")
    choice_id = str(arguments.get("choice_id") or "").strip()
    selected = str(arguments.get("selected") or "").strip()
    if not choice_id or not selected:
        raise ValueError("project_decision_resolve requires choice_id and selected")
    choice = _find_pending_choice(current_choices(settings, root), choice_id)
    if selected not in _decision_option_ids(choice):
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
    value = {
        "ok": True,
        "operation": "resolve_decision",
        "choice_id": choice_id,
        "selected": selected,
        "consumed": bool(result.get("consumed")),
        "effect": result.get("effect") or {},
    }
    return {**value, "receipt": action_receipt("resolve_decision", result)}


def _start_creation(root: Path, autopilot: Any) -> dict[str, Any]:
    kernel = str(autopilot.policy(root).get("policy", {}).get("literary_kernel") or "")
    historical = _has_unmigrated_formal_work(root)
    if kernel == "lean-v2" and historical:
        raise ValueError("历史正式正文尚未转换为轻事务回执；请先完成作品迁移，不能直接按轻内核续跑。")
    if kernel != "lean-v2" and not historical:
        autopilot.migrate_kernel(root, target_kernel="lean-v2")
    return autopilot.start(root)


def _find_pending_choice(available: Mapping[str, Any], choice_id: str) -> dict[str, Any]:
    rows = available.get("choices") if isinstance(available.get("choices"), list) else []
    choice = next(
        (item for item in rows if isinstance(item, dict) and str(item.get("choice_id") or "") == choice_id),
        None,
    )
    if choice is None:
        raise ValueError("the requested project decision is no longer pending")
    return choice


def _decision_option_ids(choice: Mapping[str, Any]) -> set[str]:
    return {
        str(item.get("id") or item.get("label") or "").strip()
        for item in choice.get("options", [])
        if isinstance(item, dict)
    }


def _manage_goal(
    root: Path,
    arguments: Mapping[str, Any],
    *,
    record_direction: RecordDirection,
    autopilot: Any,
    current_choices: Callable[..., dict[str, Any]] | None,
    settings: dict[str, Any],
) -> Mapping[str, Any]:
    operation = str(arguments.get("operation") or "start").strip().lower()
    if operation not in {"start", "pause", "resume", "recover"}:
        raise ValueError("project_goal_manage operation must be start, pause, resume, or recover")
    objective = str(arguments.get("objective") or "").strip()
    if operation == "start":
        return _start_goal(
            root,
            objective,
            record_direction,
            autopilot,
            stop_after_formal_units=max(
                0, int(arguments.get("stop_after_formal_units") or 0)
            ),
        )
    return _continue_goal(
        root,
        operation,
        objective,
        record_direction=record_direction,
        autopilot=autopilot,
        current_choices=current_choices,
        settings=settings,
    )


def _start_goal(
    root: Path,
    objective: str,
    record_direction: RecordDirection,
    autopilot: Any,
    *,
    stop_after_formal_units: int = 0,
) -> Mapping[str, Any]:
    if not objective:
        raise ValueError("project_goal_manage start requires an objective")
    record_direction(root, f"长期创作目标：{objective}", actor="project-agent")
    current = autopilot.policy(root).get("policy", {})
    if str(current.get("literary_kernel") or "") == "lean-v2" and _has_unmigrated_formal_work(root):
        raise ValueError("历史正式正文尚未转换为轻事务回执；请先完成作品迁移，不能直接按轻内核续跑。")
    kernel = (
        "strict-v1"
        if _has_unmigrated_formal_work(root)
        and str(current.get("literary_kernel") or "") != "lean-v2"
        else "lean-v2"
    )
    goal_policy = {
        "mode": "full_auto",
        "literary_kernel": kernel,
        "scene_execution_mode": str(current.get("scene_execution_mode") or "standard"),
        "release_policy": "delegated",
        "limits": {"stop_after_formal_units": stop_after_formal_units},
    }
    start_goal = getattr(autopilot, "start_managed_goal", None)
    if callable(start_goal):
        run = start_goal(root, goal_policy)
    else:
        autopilot.save_policy(root, goal_policy)
        run = autopilot.start(root)
    return goal_result(root, "start", run, "accepted")


def _continue_goal(
    root: Path,
    operation: str,
    objective: str,
    *,
    record_direction: RecordDirection,
    autopilot: Any,
    current_choices: Callable[..., dict[str, Any]] | None,
    settings: dict[str, Any],
) -> Mapping[str, Any]:
    status = autopilot.status(root)
    run = status.get("run") if isinstance(status.get("run"), dict) else {}
    run_id = str(run.get("run_id") or "").strip()
    if not run_id:
        if operation == "recover" and objective:
            return _start_goal(root, objective, record_direction, autopilot)
        raise ValueError("project_goal_manage requires an existing long-running goal")
    if operation == "pause":
        paused = autopilot.pause(run_id, reason="project-agent-goal-paused")
        return goal_result(root, operation, paused, "accepted")
    run_status = str(run.get("status") or "")
    if run_status == "complete":
        return goal_result(root, operation, run, "already_complete")
    if run_status == "running":
        return goal_result(root, operation, run, "already_running")
    if not _is_managed_goal(run):
        return _non_goal_result(root, operation, objective, record_direction, autopilot)
    pending = _pending_choices(settings, root, current_choices) if operation == "recover" else []
    if pending:
        return _decision_required_result(root, pending)
    resumed = autopilot.resume(run_id, authorized=True)
    return goal_result(root, operation, resumed, "accepted")


def _non_goal_result(
    root: Path,
    operation: str,
    objective: str,
    record_direction: RecordDirection,
    autopilot: Any,
) -> Mapping[str, Any]:
    if operation == "recover" and objective:
        return _start_goal(root, objective, record_direction, autopilot)
    return {
        "ok": False,
        "operation": f"goal_{operation}",
        "status": "goal_objective_required",
        "work_id": work_reference(root)["work_id"],
        "message": "当前运行不是长期目标；请提供 objective 后启动目标模式。",
        "recommended_tool": "project_goal_manage",
    }


def _pending_choices(
    settings: dict[str, Any],
    root: Path,
    current_choices: Callable[..., dict[str, Any]] | None,
) -> list[Mapping[str, Any]]:
    if current_choices is None:
        return []
    pending = current_choices(settings, root).get("choices", [])
    return [item for item in pending if isinstance(item, Mapping)] if isinstance(pending, list) else []


def _decision_required_result(
    root: Path,
    pending: list[Mapping[str, Any]],
) -> Mapping[str, Any]:
    return {
        "ok": False,
        "operation": "recover_goal",
        "status": "decision_required",
        "work_id": work_reference(root)["work_id"],
        "pending_choice_ids": [
            str(item.get("choice_id") or "")
            for item in pending
        ],
        "recommended_tool": "project_decision_resolve",
    }


def _is_managed_goal(run: Mapping[str, Any]) -> bool:
    policy = run.get("policy") if isinstance(run.get("policy"), Mapping) else {}
    return (
        str(policy.get("mode") or run.get("mode") or "") == "full_auto"
        and str(policy.get("literary_kernel") or "") in {"lean-v2", "strict-v1"}
        and str(policy.get("release_policy") or "") == "delegated"
    )


def _has_unmigrated_formal_work(root: Path) -> bool:
    receipts = root / "workflow" / "scene_commits"
    for draft in (root / "drafts" / "scenes").glob("*.md"):
        if not (receipts / f"{draft.stem}.json").is_file():
            return True
    if (root / "plot" / "lean_project_plan.json").is_file():
        return False
    for scene in (root / "scenes").glob("scene_*.yaml"):
        for line in scene.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("scene_id:") and line.partition(":")[2].strip().strip("\"'"):
                return True
    return False


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


__all__ = ["dependencies_from_actions"]
