"""Canon writeback candidate tasks for formal scene development."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ....agent_tasks import agent_task_completion_status, write_agent_tasks
from ....atomic_io import atomic_write_batch
from ....semantic_task_contracts import semantic_artifact_relative_path, write_semantic_artifact_template
from ....semantic_task_contracts import semantic_artifact_errors
from ...scene.facts import load_scene_facts
from .apply_status import canon_application_status
from .approval import approval_matches_patch, approval_record_for_run, patch_requires_approval
from .paths import (
    canon_apply_manifest_path,
    canon_apply_report_path,
    canon_patch_path,
)
from .contracts import (
    CANON_PATCH_SCHEMA,
    canon_patch_candidate_issues,
)


CANON_APPLY_SCHEMA = "literary-engineering-workbench/canon-patch-apply/v0.1"
CANON_BACKLOG_SCHEMA = "literary-engineering-workbench/canon-patch-backlog/v0.1"


@dataclass(frozen=True)
class CanonPatchTaskResult:
    project_root: Path
    scene_id: str
    task_path: Path
    json_path: Path
    report_path: Path
    source_path: Path


@dataclass(frozen=True)
class CanonBacklogResult:
    project_root: Path
    output_path: Path
    json_path: Path
    pending_count: int
    applied_count: int


@dataclass(frozen=True)
class CanonApplyResult:
    project_root: Path
    patch_path: Path
    report_path: Path
    json_path: Path
    changelog_path: Path
    status: str
    applied_count: int


def build_canon_patch_task(
    project_root: Path,
    *,
    scene: Path | None = None,
    source: Path | None = None,
    output: Path | None = None,
    json_output: Path | None = None,
) -> CanonPatchTaskResult:
    """Create a platform-agent sidecar for canon writeback candidates.

    This command never applies canon. It only asks the platform agent to decide
    whether the promoted scene introduced durable world facts, then to write a
    candidate patch or an explicit no-change rationale.
    """

    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    scene_path = _resolve_scene(root, scene)
    scene_id = _scene_id(scene_path)
    source_path = _resolve_source(root, scene_id, source)
    out_dir = root / "canon" / "patches"
    report = _resolve(root, output, out_dir / f"{scene_id}_canon_patch.md")
    json_path = _resolve(root, json_output, out_dir / f"{scene_id}_canon_patch.json")
    task_path = json_path.with_suffix(".agent_tasks.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    if not json_path.exists():
        json_path.write_text(json.dumps(_initial_patch_payload(root, scene_id, scene_path, source_path), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not report.exists():
        report.write_text(_initial_report(root, scene_id, scene_path, source_path), encoding="utf-8")
    review_rel = semantic_artifact_relative_path("canon-agent-task", scene_id)
    write_semantic_artifact_template(
        root,
        "canon-agent-task",
        scene_id,
        source=_rel(json_path, root),
        # Keep the prior review as auditable stale evidence.  The semantic
        # validator will reject it if the patch digest no longer matches.
        overwrite=False,
    )

    sources = [
        scene_path,
        source_path,
        root / "canon",
        root / "characters",
        root / "plot",
        root / "drafts" / "promotions" / f"{scene_id}_promotion.json",
        root / "reviews" / "agent" / f"{scene_id}_scene_review.json",
        root / review_rel,
    ]
    write_agent_tasks(
        task_path,
        title=f"canon-evolve {scene_id}",
        root=root,
        source_paths=sources,
        notes=[
            "本任务只生成 canon 写回候选，不得直接修改 canon/world_rules.yaml、canon/forbidden_changes.yaml 或正式世界观文件。",
            "如果没有 canon 变化，也必须写出 no_canon_change_reason，避免静默跳过。",
            f"候选生成与独立审查分属两个状态；候选作者不得写 `{review_rel}` 或 completion marker。",
        ],
        tasks=[
            (
                "判断本场是否产生 canon 变化",
                """读取 promoted draft、scene.yaml、promotion manifest、AgentReview、state patch 和 canon 目录。区分人物临时状态、关系变化、场景事实、世界规则、组织/地点/历史事实、伏笔状态。只有会跨场景持续约束未来创作的事实才属于 canon_change=true。""",
            ),
            (
                "写入 canon patch JSON",
                f"""创建或覆盖 `{_rel(json_path, root)}`。若没有 canon 变化，写 `canon_change=false`、`no_canon_change_reason` 和空 `items`。若有变化，写 `canon_change=true`，并把每条变化列入 `items`，字段至少包括 type、summary、source_evidence、target_files、risk_level、requires_user_approval。不得把候选写成已应用。""",
            ),
            (
                "写入 canon patch 报告",
                f"""创建或覆盖 `{_rel(report, root)}`，用普通语言说明：本场是否产生持续世界事实、证据来自哪段正文、会影响哪些未来创作、为什么暂不直接写入 canon、是否需要用户审批。不要写入 `[AGENT_TASK: ...]`。候选写完后交还 Studio，由下一状态的独立 Reviewer 写 `{review_rel}` 并完成 sidecar。""",
            ),
        ],
    )
    return CanonPatchTaskResult(root, scene_id, task_path, json_path, report, source_path)


def build_canon_patch_backlog(
    project_root: Path,
    *,
    output: Path | None = None,
    json_output: Path | None = None,
) -> CanonBacklogResult:
    """Render the current canon patch backlog for dashboards and formal routes."""

    root = project_root.resolve()
    out_dir = root / "canon" / "patches"
    report = _resolve(root, output, out_dir / "canon_backlog.md")
    json_path = _resolve(root, json_output, out_dir / "canon_backlog.json")
    report.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    items = canon_patch_backlog_items(root)
    pending = [item for item in items if item["status"] in {"pending_apply", "needs_approval", "invalid", "task_incomplete"}]
    applied = [item for item in items if item["status"] == "applied"]
    payload = {
        "schema": CANON_BACKLOG_SCHEMA,
        "project_root": str(root),
        "generated_at": _now(),
        "summary": {
            "patch_count": len(items),
            "pending_count": len(pending),
            "applied_count": len(applied),
        },
        "items": items,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report.write_text(_render_backlog(payload, root), encoding="utf-8")
    return CanonBacklogResult(root, report, json_path, len(pending), len(applied))


def canon_patch_backlog_items(project_root: Path) -> list[dict[str, Any]]:
    """Return content-bound canon patch states for workflow routing."""

    root = project_root.resolve()
    return [_patch_backlog_item(root, path) for path in _canon_patch_paths(root)]


def apply_canon_patch(
    project_root: Path,
    *,
    patch: Path | None = None,
    approval_run_id: str = "",
    allow_unapproved: bool = False,
    output: Path | None = None,
    json_output: Path | None = None,
) -> CanonApplyResult:
    """Apply an approved canon patch into the durable canon change ledger."""

    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    patch_path = _resolve_patch_path(root, patch)
    payload = _read_json(patch_path)
    errors = _canon_patch_payload_errors(root, patch_path, payload)
    if errors:
        raise ValueError("canon patch is not apply-ready: " + "; ".join(errors))
    patch_id = patch_path.stem
    required_approval = patch_requires_approval(payload)
    approval_id = approval_run_id.strip() or patch_id
    approval = approval_record_for_run(root, approval_id)
    approval_matches = approval_matches_patch(approval, patch_path)
    if required_approval and (str(approval.get("decision") or "") != "approve" or not approval_matches) and not allow_unapproved:
        raise RuntimeError(f"canon-apply requires approve record for run_id {approval_id}; got {approval.get('decision') or 'missing'}")

    report = _resolve(root, output, canon_apply_report_path(root, patch_id))
    json_path = _resolve(root, json_output, canon_apply_manifest_path(root, patch_id))
    changelog = root / "canon" / "canon_change_log.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    changelog.parent.mkdir(parents=True, exist_ok=True)
    applied_at = _now()
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    candidate_sha256 = hashlib.sha256(patch_path.read_bytes()).hexdigest()
    apply_payload = {
        "schema": CANON_APPLY_SCHEMA,
        "patch": _rel(patch_path, root),
        "patch_id": patch_id,
        "scene_id": payload.get("scene_id", ""),
        "status": "applied",
        "applied_at": applied_at,
        "approval_run_id": approval_id,
        "approval": approval or {"decision": "allow_unapproved" if allow_unapproved else "not_required"},
        "candidate_sha256": candidate_sha256,
        "allow_unapproved": allow_unapproved,
        "applied_count": len(items),
        "application_boundary": "ledger_only",
        "changelog": _rel(changelog, root),
        "items": items,
    }
    applied_patch = dict(payload)
    applied_patch["status"] = "applied"
    applied_patch["applied"] = True
    applied_patch["applied_at"] = applied_at
    applied_patch["approval_run_id"] = approval_id
    applied_patch["apply_manifest"] = _rel(json_path, root)
    applied_patch["canon_change_log"] = _rel(changelog, root)
    applied_patch_text = json.dumps(applied_patch, ensure_ascii=False, indent=2) + "\n"
    apply_payload["applied_patch_sha256"] = hashlib.sha256(applied_patch_text.encode("utf-8")).hexdigest()
    previous_changelog = changelog.read_text(encoding="utf-8") if changelog.exists() else "# Canon Change Log\n\n"
    atomic_write_batch(
        {
            json_path: json.dumps(apply_payload, ensure_ascii=False, indent=2) + "\n",
            report: _render_apply_report(apply_payload, root),
            changelog: previous_changelog.rstrip() + "\n\n" + _render_changelog_entry(patch_id, payload, apply_payload),
            patch_path: applied_patch_text,
        }
    )

    return CanonApplyResult(root, patch_path, report, json_path, changelog, "applied", len(items))


def canon_writeback_status(
    root: Path,
    scene_id: str,
    *,
    require_review: bool = True,
) -> dict[str, Any]:
    """Inspect canon writeback state for route/status gates."""

    json_path = canon_patch_path(root, scene_id)
    report_path = json_path.with_suffix(".md")
    task_path = json_path.with_suffix(".agent_tasks.md")
    candidate_manifest = _candidate_manifest(root, scene_id)
    promotion_manifest = _read_json(root / "drafts" / "promotions" / f"{scene_id}_promotion.json")
    # The exact-candidate independent review is the final semantic authority.
    # Candidate manifests are writer-owned declarations and can legitimately
    # change during revision; using them first can silently drop a reviewer-
    # confirmed canon change.  Promotion binds the exact candidate digest, so
    # only accept a review that matches that same digest.
    declaration = (
        _review_canon_declaration(root, scene_id, promotion_manifest)
        or _canon_declaration(promotion_manifest)
        or _canon_declaration(candidate_manifest)
    )
    payload = _read_json(json_path)
    completion = agent_task_completion_status(task_path, root=root)
    result: dict[str, Any] = {
        "schema": "literary-engineering-workbench/canon-writeback-status/v0.1",
        "scene_id": scene_id,
        "json": _rel(json_path, root),
        "report": _rel(report_path, root),
        "agent_tasks": _rel(task_path, root),
        "agent_task_completion": completion,
        "declaration": declaration,
        "status": "not_required",
        "message": "no canon writeback declaration found; legacy scene treated as not required",
    }
    if declaration.get("canon_change") is None:
        if json_path.exists():
            result["status"] = "unknown"
            result["message"] = "canon patch file exists but candidate/promotion did not declare canon_change"
        return result
    if declaration.get("canon_change") is False:
        reason = str(declaration.get("no_canon_change_reason") or "").strip()
        if reason:
            result["status"] = "pass"
            result["message"] = "scene declared no canon change with rationale"
        else:
            result["status"] = "missing_reason"
            result["message"] = "canon_change=false requires no_canon_change_reason"
        return result
    if declaration.get("canon_change") == "unknown":
        result["status"] = "unknown"
        result["message"] = "candidate manifest still has canon_change=unknown; run canon-evolve"
        return result
    if declaration.get("canon_change") is True:
        if not json_path.exists() or not report_path.exists() or not task_path.exists():
            result["status"] = "missing_patch"
            result["message"] = "canon_change=true requires canon-evolve JSON/report/sidecar"
            return result
        patch_change = _canon_change_value(payload.get("canon_change"))
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        if patch_change is not True or not items:
            result["status"] = "invalid_patch"
            result["message"] = "canon patch must contain canon_change=true and at least one item"
            return result
        item_errors = _canon_patch_item_errors(items)
        if item_errors:
            result["status"] = "invalid_patch"
            result["message"] = "canon patch items are incomplete: " + "; ".join(item_errors[:6])
            return result
        if payload.get("applied") is True:
            return canon_application_status(root, json_path, payload, result)
        if not require_review:
            result["status"] = "pass"
            result["message"] = "canon change candidate patch is ready for independent review"
            return result
        if completion.get("complete") is not True:
            result["status"] = "task_incomplete"
            result["message"] = f"canon-evolve sidecar incomplete: {completion.get('message')}"
            return result
        review_errors = semantic_artifact_errors(root, "canon-agent-task", scene_id)
        if review_errors:
            result["status"] = "semantic_incomplete"
            result["message"] = "canon semantic review incomplete: " + "; ".join(review_errors[:4])
            return result
        return canon_application_status(root, json_path, payload, result)
    result["status"] = "unknown"
    result["message"] = "unrecognized canon_change declaration"
    return result


def _canon_patch_paths(root: Path) -> list[Path]:
    folder = root / "canon" / "patches"
    if not folder.exists():
        return []
    return sorted(
        (
            path
            for path in folder.glob("*_canon_patch.json")
            if path.name not in {"canon_backlog.json"} and not path.name.endswith("_apply.json")
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _patch_backlog_item(root: Path, path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    errors = _canon_patch_payload_errors(root, path, payload, require_completion=False)
    approval_id = path.stem
    approval = approval_record_for_run(root, approval_id)
    change = _canon_change_value(payload.get("canon_change"))
    applied = payload.get("applied") is True or str(payload.get("status") or "").strip().lower() == "applied"
    candidate_sha256 = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
    approval_current = approval_matches_patch(approval, path)
    completion = agent_task_completion_status(path.with_suffix(".agent_tasks.md"), root=root)
    if applied:
        status = "applied"
    elif errors:
        status = "invalid"
    elif change is not True:
        status = "not_applicable"
    elif patch_requires_approval(payload) and (
        str(approval.get("decision") or "") != "approve" or not approval_current
    ):
        status = "needs_approval"
    else:
        status = "pending_apply" if completion.get("complete") is True else "task_incomplete"
    return {
        "patch": _rel(path, root),
        "scene_id": payload.get("scene_id", ""),
        "status": status,
        "canon_change": change,
        "applied": applied,
        "approval_run_id": approval_id,
        "approval_decision": approval.get("decision", ""),
        "approval_notes": approval.get("notes", ""),
        "approval_current": approval_current,
        "candidate_sha256": candidate_sha256,
        "completion_status": completion.get("status", ""),
        "completion_message": completion.get("message", ""),
        "requires_user_approval": patch_requires_approval(payload),
        "item_count": len(payload.get("items") if isinstance(payload.get("items"), list) else []),
        "errors": errors,
        "apply_manifest": str(payload.get("apply_manifest") or ""),
        "message": _patch_backlog_message(status, errors),
    }


def _patch_backlog_message(status: str, errors: list[str]) -> str:
    if errors:
        return "; ".join(errors[:4])
    return {
        "applied": "canon patch already applied to the canon ledger",
        "not_applicable": "patch does not declare canon_change=true",
        "needs_approval": "requires workflow approval before canon-apply",
        "task_incomplete": "canon-evolve sidecar must be completed before apply",
        "pending_apply": "ready for canon-apply",
    }.get(status, status)


def _resolve_patch_path(root: Path, patch: Path | None) -> Path:
    if patch is not None:
        path = patch if patch.is_absolute() else root / patch
        if not path.exists():
            raise FileNotFoundError(f"canon patch not found: {path}")
        return path
    for path in _canon_patch_paths(root):
        payload = _read_json(path)
        if _canon_change_value(payload.get("canon_change")) is True and payload.get("applied") is not True:
            return path
    raise FileNotFoundError("no unapplied canon patch found under canon/patches")


def _canon_patch_payload_errors(root: Path, patch_path: Path, payload: dict[str, Any], *, require_completion: bool = True) -> list[str]:
    errors: list[str] = []
    if not payload:
        return [f"canon patch JSON is missing or unreadable: {_rel(patch_path, root)}"]
    if payload.get("schema") != CANON_PATCH_SCHEMA:
        errors.append("canon patch has wrong or missing schema")
    if _canon_change_value(payload.get("canon_change")) is not True:
        errors.append("canon patch must declare canon_change=true before apply")
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    if not items:
        errors.append("canon patch has no items")
    errors.extend(_canon_patch_item_errors(items))
    if payload.get("applied") is True:
        errors.append("canon patch is already applied")
    if require_completion:
        completion = agent_task_completion_status(patch_path.with_suffix(".agent_tasks.md"), root=root)
        if completion.get("complete") is not True:
            errors.append(f"canon-evolve sidecar incomplete: {completion.get('message')}")
        if str(payload.get("formal_contract_revision") or "").strip() >= "2026-07-23.3":
            scene_id = str(payload.get("scene_id") or patch_path.stem.replace("_canon_patch", ""))
            errors.extend(semantic_artifact_errors(root, "canon-agent-task", scene_id))
    return errors


def _render_backlog(payload: dict[str, Any], root: Path) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# Canon Patch Backlog",
        "",
        f"- 项目：`{root}`",
        f"- Patch 数：{summary.get('patch_count', 0)}",
        f"- 待处理：{summary.get('pending_count', 0)}",
        f"- 已应用：{summary.get('applied_count', 0)}",
        "",
        "| Patch | Scene | Status | Approval | Items | Message |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        lines.append(
            "| `{patch}` | `{scene}` | `{status}` | `{approval}` | {items} | {message} |".format(
                patch=item.get("patch", ""),
                scene=item.get("scene_id", ""),
                status=item.get("status", ""),
                approval=item.get("approval_decision", "") or "missing",
                items=item.get("item_count", 0),
                message=str(item.get("message") or "").replace("|", "/"),
            )
        )
    return "\n".join(lines) + "\n"


def _render_apply_report(payload: dict[str, Any], root: Path) -> str:
    lines = [
        f"# Canon Apply：{payload.get('patch_id', '')}",
        "",
        f"- 项目：`{root}`",
        f"- Patch：`{payload.get('patch', '')}`",
        f"- 状态：`{payload.get('status', '')}`",
        f"- 审批：`{payload.get('approval_run_id', '')}`",
        f"- 应用数量：{payload.get('applied_count', 0)}",
        f"- 写入边界：`{payload.get('application_boundary', '')}`",
        f"- Canon 变更账本：`{payload.get('changelog', '')}`",
        "",
        "本操作把已审查/审批的 canon patch 写入持久 canon 变更账本；不会机械改写 world_rules 等目标文件。",
        "",
        "## 已登记条目",
        "",
    ]
    for index, item in enumerate(payload.get("items", []), start=1):
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"{index}. {item.get('summary', '')}",
                f"   - 类型：{item.get('type', '')}",
                f"   - 风险：{item.get('risk_level', '')}",
                f"   - 目标文件：{', '.join(str(path) for path in item.get('target_files', []))}",
                f"   - 证据：{item.get('source_evidence', '')}",
            ]
        )
    return "\n".join(lines) + "\n"


def _append_changelog(changelog: Path, patch_id: str, patch_payload: dict[str, Any], apply_payload: dict[str, Any]) -> None:
    previous = changelog.read_text(encoding="utf-8") if changelog.exists() else "# Canon Change Log\n\n"
    atomic_write_batch({changelog: previous.rstrip() + "\n\n" + _render_changelog_entry(patch_id, patch_payload, apply_payload)})


def _render_changelog_entry(patch_id: str, patch_payload: dict[str, Any], apply_payload: dict[str, Any]) -> str:
    lines = [
        f"## {patch_id}",
        "",
        f"- 应用时间：{apply_payload.get('applied_at', '')}",
        f"- 场景：{patch_payload.get('scene_id', '')}",
        f"- 审批：{apply_payload.get('approval_run_id', '')}",
        f"- Apply Manifest：`{apply_payload.get('patch_id', '')}_apply.json`",
        "",
    ]
    for item in patch_payload.get("items", []):
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"- {item.get('summary', '')}",
                f"  - 类型：{item.get('type', '')}",
                f"  - 证据：{item.get('source_evidence', '')}",
                f"  - 目标文件：{', '.join(str(path) for path in item.get('target_files', []))}",
            ]
        )
    return "\n".join(lines) + "\n"


def _initial_patch_payload(root: Path, scene_id: str, scene_path: Path, source_path: Path) -> dict[str, Any]:
    return {
        "schema": CANON_PATCH_SCHEMA,
        "formal_contract_revision": "2026-07-23.3",
        "scene_id": scene_id,
        "created_at": _now(),
        "scene": _rel(scene_path, root),
        "source": _rel(source_path, root),
        "canon_change": "unknown",
        "no_canon_change_reason": "",
        "items": [],
        "status": "candidate",
        "applied": False,
        "requires_user_approval": True,
        "source_paths": [_rel(scene_path, root), _rel(source_path, root)],
    }


def _initial_report(root: Path, scene_id: str, scene_path: Path, source_path: Path) -> str:
    return f"""# Canon 写回候选：{scene_id}

- 场景：`{_rel(scene_path, root)}`
- 正文来源：`{_rel(source_path, root)}`
- 状态：等待平台 Agent 判断

本文件不是正式 canon。平台 Agent 需要读取同名 `.agent_tasks.md`，判断本场是否产生持续世界事实；若没有，写明 no_canon_change_reason；若有，写入候选 patch 并等待审查/审批。
"""


def _resolve_scene(root: Path, scene: Path | None) -> Path:
    path = _resolve(root, scene, root / "scenes" / "scene_0001.yaml")
    if not path.exists():
        raise FileNotFoundError(f"scene file not found: {path}")
    return path


def _resolve_source(root: Path, scene_id: str, source: Path | None) -> Path:
    if source is not None:
        path = source if source.is_absolute() else root / source
        if not path.exists():
            raise FileNotFoundError(f"source file not found: {path}")
        return path
    for path in [
        root / "drafts" / "scenes" / f"{scene_id}.md",
        _candidate_path_from_promotion(root, scene_id),
        _latest_candidate(root, scene_id),
    ]:
        if path and path.exists():
            return path
    raise FileNotFoundError(f"no promoted draft or candidate found for scene: {scene_id}")


def _candidate_path_from_promotion(root: Path, scene_id: str) -> Path | None:
    payload = _read_json(root / "drafts" / "promotions" / f"{scene_id}_promotion.json")
    candidate = str(payload.get("candidate") or "").strip()
    if not candidate:
        return None
    path = Path(candidate)
    return path if path.is_absolute() else root / path


def _latest_candidate(root: Path, scene_id: str) -> Path | None:
    folder = root / "drafts" / "candidates"
    if not folder.exists():
        return None
    paths = sorted(folder.glob(f"{scene_id}-*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    return paths[0] if paths else None


def _candidate_manifest(root: Path, scene_id: str) -> dict[str, Any]:
    candidate = _candidate_path_from_promotion(root, scene_id) or _latest_candidate(root, scene_id)
    if candidate is None:
        return {}
    return _read_json(candidate.with_suffix(".json"))


def _review_canon_declaration(
    root: Path,
    scene_id: str,
    promotion_manifest: dict[str, Any],
) -> dict[str, Any]:
    review_path = root / "reviews" / "agent" / f"{scene_id}_scene_review.json"
    review = _read_json(review_path)
    if not review:
        return {}
    candidate_digest = str(promotion_manifest.get("candidate_sha256") or "").strip().lower()
    review_digest = str(review.get("candidate_sha256") or "").strip().lower()
    if not candidate_digest or review_digest != candidate_digest:
        return {}
    if str(review.get("conclusion") or "").strip().lower() not in {"pass", "pass_with_notes"}:
        return {}
    declaration = _canon_declaration(review)
    if declaration:
        declaration["source"] = _rel(review_path, root)
    return declaration


def _canon_declaration(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {}
    nested = payload.get("canon_writeback")
    if isinstance(nested, dict):
        change = _canon_change_value(nested.get("canon_change"))
        if change is not None:
            return {
                "canon_change": change,
                "no_canon_change_reason": str(nested.get("no_canon_change_reason") or payload.get("no_canon_change_reason") or "").strip(),
                "source": "canon_writeback",
            }
    change = _canon_change_value(payload.get("canon_change"))
    if change is None:
        return {}
    return {
        "canon_change": change,
        "no_canon_change_reason": str(payload.get("no_canon_change_reason") or "").strip(),
        "source": "top_level",
    }


def _canon_change_value(value: object) -> bool | str | None:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "yes", "1", "changed", "change"}:
        return True
    if text in {"false", "no", "0", "none", "no_change", "not_required"}:
        return False
    if text in {"unknown", "pending", "todo", "needs_review"}:
        return "unknown"
    return None


def _canon_patch_item_errors(items: list[Any]) -> list[str]:
    payload = {
        "schema": CANON_PATCH_SCHEMA,
        "canon_change": True,
        "items": items,
    }
    return [
        f"{issue.path} {issue.message}"
        for issue in canon_patch_candidate_issues(payload)
        if issue.path.startswith("items[")
    ]


def _scene_id(path: Path) -> str:
    return load_scene_facts(path).scene_id


def _resolve(root: Path, path: Path | None, default: Path) -> Path:
    if path is None:
        return default
    return path if path.is_absolute() else root / path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
