"""Scan platform-agent task sidecars and route completion gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .agent_tasks import agent_task_completion_status, default_agent_completion_path
from .asset_workshop import ASSET_CANDIDATE_DIRS
from .canon_evolver import canon_writeback_status
from .candidate_promotion import candidate_generation_gate, candidate_review_gate
from .context_broker import context_trace_status
from .flow_gates import branch_selection_status
from .anti_ai_style import style_lint_gate_message
from .agent_schema import validate_payload
from .new_character_register import new_character_register_issues
from .narrative_rhythm import narrative_rhythm_contract, rhythm_review_status
from .reader_experience import reader_experience_contract
from .word_budget import scene_word_budget_contract


BACKTICK_RE = re.compile(r"`([^`]+)`")
EXPECTED_HINT_RE = re.compile(r"(完成后写入|创建或覆盖|expected_|写入候选|写入正式|输出到|输出至)")
IGNORED_PARTS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv"}
DEBUG_WAIVER_KEYS = {
    "allow_unreviewed",
    "allow_review_notes",
    "allow_unapproved",
    "allow_unresolved",
    "allow_missing_composition",
    "allow_unselected_composition",
    "allow_missing_branch",
    "allow_recommended_branch",
    "include_blocked",
}
DEBUG_WAIVER_DECISIONS = {
    "allow_unreviewed",
    "allow_review_notes",
    "allow_unapproved",
    "allow_unresolved",
    "include_blocked",
}


@dataclass(frozen=True)
class AgentTaskRecord:
    path: str
    route: str
    status: str
    expected_paths: tuple[str, ...]
    existing_expected_paths: tuple[str, ...]
    missing_expected_paths: tuple[str, ...]
    source_paths: tuple[str, ...]
    missing_source_paths: tuple[str, ...]


@dataclass(frozen=True)
class AgentTaskStatusResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    task_count: int
    pending_count: int
    partial_count: int
    complete_count: int
    missing_expected_count: int


@dataclass(frozen=True)
class RouteAuditResult:
    project_root: Path
    markdown_path: Path
    json_path: Path
    route: str
    gate_count: int
    blocking_count: int
    warning_count: int
    pending_task_count: int


def build_agent_task_status(
    project_root: Path,
    *,
    output: Path | None = None,
    json_output: Path | None = None,
) -> AgentTaskStatusResult:
    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    records = _scan_agent_tasks(root)
    summary = _summary(records)
    markdown_path = _resolve_output(root, output, "workflow", "agent_task_status.md")
    json_path = _resolve_output(root, json_output, "workflow", "agent_task_status.json")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "literary-engineering-workbench/agent-task-status/v0.1",
        "generated_at": _now(),
        "project_root": str(root),
        "summary": summary,
        "tasks": [asdict(record) for record in records],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_status_markdown(payload), encoding="utf-8")
    return AgentTaskStatusResult(
        project_root=root,
        markdown_path=markdown_path,
        json_path=json_path,
        task_count=summary["task_count"],
        pending_count=summary["pending_count"],
        partial_count=summary["partial_count"],
        complete_count=summary["complete_count"],
        missing_expected_count=summary["missing_expected_count"],
    )


def build_route_audit(
    project_root: Path,
    *,
    route: str = "",
    output: Path | None = None,
    json_output: Path | None = None,
) -> RouteAuditResult:
    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root not found: {root}")
    records = _scan_agent_tasks(root)
    normalized_route = _normalize_route(route)
    gates = _route_gates(root, normalized_route, records)
    scene_scope = _scene_audit_scope(root) if normalized_route == "scene-development" else {}
    summary = {
        "route": normalized_route or "overall",
        "gate_count": len(gates),
        "blocking_count": sum(1 for gate in gates if gate["severity"] == "blocking"),
        "warning_count": sum(1 for gate in gates if gate["severity"] == "warning"),
        "waiting_count": sum(1 for gate in gates if gate["status"] == "waiting"),
        "pass_count": sum(1 for gate in gates if gate["status"] == "pass"),
        "pending_task_count": sum(1 for record in records if record.status in {"pending", "partial", "unknown"}),
        "missing_expected_count": sum(len(record.missing_expected_paths) for record in records),
    }
    if scene_scope:
        summary["scene_scope"] = scene_scope
    markdown_path = _resolve_output(root, output, "workflow", "route_audit.md")
    json_path = _resolve_output(root, json_output, "workflow", "route_audit.json")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "literary-engineering-workbench/route-audit/v0.1",
        "generated_at": _now(),
        "project_root": str(root),
        "summary": summary,
        "gates": gates,
        "tasks": [asdict(record) for record in records],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_route_audit_markdown(payload), encoding="utf-8")
    return RouteAuditResult(
        project_root=root,
        markdown_path=markdown_path,
        json_path=json_path,
        route=summary["route"],
        gate_count=summary["gate_count"],
        blocking_count=summary["blocking_count"],
        warning_count=summary["warning_count"],
        pending_task_count=summary["pending_task_count"],
    )


def _scan_agent_tasks(root: Path) -> list[AgentTaskRecord]:
    records = []
    for path in sorted(root.rglob("*.agent_tasks.md")):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if _is_human_decision_task(path, text):
            # Human boundaries are surfaced through workflow state/current choices,
            # not as unfinished Agent sidecars with completion markers.
            continue
        expected = _unique(_extract_expected_paths(root, text))
        completion = _normalize_path(root, default_agent_completion_path(path))
        if completion not in expected:
            expected.append(completion)
        sources = _unique(_extract_source_paths(root, text))
        existing = tuple(item for item in expected if _path_exists(root, item))
        missing = tuple(item for item in expected if not _path_exists(root, item))
        missing_sources = tuple(item for item in sources if not _path_exists(root, item))
        completion_state = agent_task_completion_status(path, root=root)
        if expected and not missing and completion_state.get("complete") is True:
            status = "complete"
        elif expected and existing:
            status = "partial"
        elif expected:
            status = "pending"
        else:
            status = "unknown"
        records.append(
            AgentTaskRecord(
                path=_rel(path, root),
                route=_infer_route(path, text),
                status=status,
                expected_paths=tuple(expected),
                existing_expected_paths=existing,
                missing_expected_paths=missing,
                source_paths=tuple(sources),
                missing_source_paths=missing_sources,
            )
        )
    return records


def _is_human_decision_task(path: Path, text: str) -> bool:
    """Recognize registry-backed human boundaries before sidecar accounting."""

    if "execution_policy: `human-required`" in text:
        return True
    payload = _registered_task_payload(path)
    return str(payload.get("execution_policy") or "") == "human-required"


def _registered_task_payload(path: Path) -> dict[str, object]:
    task_json = path.with_name(path.name.removesuffix(".agent_tasks.md") + ".task.json")
    if not task_json.is_file():
        return {}
    try:
        payload = json.loads(task_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_expected_paths(root: Path, text: str) -> list[str]:
    results: list[str] = []
    for line in text.splitlines():
        if not EXPECTED_HINT_RE.search(line):
            continue
        for item in BACKTICK_RE.findall(line):
            if _looks_like_project_path(item):
                results.append(_normalize_path(root, item))
    return results


def _extract_source_paths(root: Path, text: str) -> list[str]:
    results: list[str] = []
    in_sources = False
    for line in text.splitlines():
        if line.strip() == "## Source Artifacts":
            in_sources = True
            continue
        if in_sources and line.startswith("## "):
            break
        if not in_sources:
            continue
        for item in BACKTICK_RE.findall(line):
            if _looks_like_project_path(item):
                results.append(_normalize_path(root, item))
    return results


def _looks_like_project_path(value: str) -> bool:
    text = value.strip()
    if not text or text.startswith("literary-engineering-workbench/"):
        return False
    if re.search(r"\s", text):
        return False
    suffixes = (".md", ".json", ".yaml", ".yml", ".csv", ".txt", ".docx")
    return "/" in text or "\\" in text or text.lower().endswith(suffixes)


def _normalize_path(root: Path, value: str | Path) -> str:
    if isinstance(value, Path):
        path = value
    else:
        path = Path(value.strip())
    if path.is_absolute():
        return _rel(path, root)
    return path.as_posix()


def _path_exists(root: Path, value: str) -> bool:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    # Historical task packages may contain paths from a packaged runtime whose
    # temporary extraction directory has already disappeared or is unreadable.
    # They are missing inputs, not a reason to make the whole dashboard fail.
    try:
        return path.exists()
    except OSError:
        return False


def _infer_route(path: Path, text: str) -> str:
    registered_route = str(_registered_task_payload(path).get("route") or "").strip()
    if registered_route:
        return registered_route
    route_line = re.search(r"(?m)^- route: `([^`]+)`\s*$", text)
    if route_line:
        return route_line.group(1).strip()
    joined = (path.as_posix() + "\n" + text[:1000]).lower()
    if "word_budget" in joined or "longform word budget" in joined:
        return "longform-planning"
    if "source_ingest" in joined or "extract_project_files" in joined or "sources/imports" in joined:
        return "source-ingest"
    if "style" in joined:
        return "style-engineering"
    if "asset" in joined or "candidate asset" in joined or "platform asset" in joined:
        return "character-and-world-assets"
    if "scene_review" in joined or "canon_review" in joined or "committee" in joined:
        return "review-and-audit"
    if "branch" in joined or "composition" in joined or "candidate" in joined or "state_patch" in joined or "revision" in joined:
        return "scene-development"
    if "export" in joined or "publish" in joined or "release" in joined:
        return "export-and-release"
    return "optional-cli"


def _route_gates(root: Path, route: str, records: list[AgentTaskRecord]) -> list[dict[str, str]]:
    gates: list[dict[str, str]] = []
    pending = [record for record in records if record.status in {"pending", "partial", "unknown"}]
    missing_expected = sum(len(record.missing_expected_paths) for record in records)
    debug_waivers = _debug_waiver_hits(root)
    _add_gate(gates, "project-root", (root / "project.yaml").exists(), "blocking", "project.yaml exists", "不是标准 work project；若扫描 skill root，可忽略本项。")
    _add_gate(gates, "agent-sidecars-handled", not pending, "blocking", "all .agent_tasks.md sidecars handled", f"仍有 {len(pending)} 个 sidecar 未完整处理。")
    _add_gate(gates, "expected-artifacts-exist", missing_expected == 0, "blocking", "all expected artifacts exist", f"仍缺 {missing_expected} 个预期产物。")
    _add_gate(
        gates,
        "debug-waiver-flags",
        not debug_waivers,
        "blocking",
        "no debug waiver flags found",
        f"检测到正式 Skill 宿主禁用的调试/跳审字段：{'; '.join(debug_waivers[:8])}。不要用 allow/unreview/include-blocked 类参数跳过 review；补齐正式门禁。",
    )
    if route == "longform-planning":
        _add_longform_budget_gates(gates, root, force=True)
    if route == "character-and-world-assets":
        _add_asset_route_gates(gates, root)
    if route == "review-and-audit":
        _add_review_audit_route_gates(gates, root)
    if route == "scene-development":
        _add_longform_budget_gates(gates, root, force=False)
        scene_files = _scene_files(root)
        _add_gate(gates, "scene-files", bool(scene_files), "blocking", "scene yaml exists", "先创建 scenes/{scene_id}.yaml。")
        started_ids = _started_scene_ids(root)
        started_scenes = [scene_path for scene_path in scene_files if _scene_id(scene_path) in started_ids]
        _add_gate(
            gates,
            "scene-audit-scope",
            True,
            "info",
            f"auditing {len(started_scenes)} started scene(s); {len(scene_files) - len(started_scenes)} planned scene(s) remain future work",
            "",
        )
        for scene_path in started_scenes:
            _add_scene_development_gates(gates, root, scene_path)
        scene_pending = [record for record in pending if record.route == "scene-development"]
        _add_gate(gates, "scene-sidecars-handled", not scene_pending, "blocking", "scene-development sidecars handled", f"仍有 {len(scene_pending)} 个 scene-development sidecar 未完成。")
        unresolved_reviews = _unresolved_scene_review_count(root)
        _add_gate(gates, "scene-review-notes-resolved", unresolved_reviews == 0, "blocking", "scene review notes resolved", f"仍有 {unresolved_reviews} 个场景 review notes 未进入 revise-scene 修订闭环或缺修订报告。")
    if route == "export-and-release":
        chapter_jsons = list((root / "plot" / "chapters").glob("*.json")) if (root / "plot" / "chapters").exists() else []
        _add_gate(gates, "chapter-workspace-json", bool(chapter_jsons), "blocking", "chapter workspace JSON exists", "先运行 chapter-workspace。")
        non_ready = _non_ready_scene_count(chapter_jsons)
        _add_gate(gates, "chapter-scenes-ready", non_ready == 0 and bool(chapter_jsons), "blocking", "chapter scenes ready", f"章节中仍有 {non_ready} 个非 ready 场景。")
        stale_or_weak = _stale_or_weak_chapter_gate_count(chapter_jsons)
        _add_gate(
            gates,
            "chapter-clean-review-gates",
            stale_or_weak == 0 and bool(chapter_jsons),
            "blocking",
            "chapter scenes have clean formal review gates",
            f"章节工作台中仍有 {stale_or_weak} 个场景缺少新式 clean review/flow gate 字段或存在未解决 notes；重新运行 chapter-workspace 并修订。",
        )
        _add_longform_budget_gates(gates, root, force=False)
        unapplied = _unapplied_state_patch_count(root)
        _add_gate(
            gates,
            "state-patches-applied-or-waived",
            unapplied == 0,
            "warning",
            "character state patches have apply reports or no pending patches",
            f"仍有 {unapplied} 个人物状态 patch 未生成 state-apply 报告；最终发布前需审批写回或记录内部预览 waiver。",
        )
        unapplied_canon = _unapplied_canon_patch_count(root)
        _add_gate(
            gates,
            "canon-patches-applied",
            unapplied_canon == 0,
            "blocking",
            "canon patches have been applied to the canon ledger",
            f"仍有 {unapplied_canon} 个 canon patch 未进入 canon-apply 账本；最终发布前需审批并运行 canon-apply，或明确改回 no_canon_change_reason。",
        )
        _add_export_release_route_gates(gates, root, chapter_jsons)
    return gates


def _add_longform_budget_gates(gates: list[dict[str, str]], root: Path, *, force: bool) -> None:
    target_words = _project_target_words(root)
    if not force and target_words < 100000:
        return
    budget_json = root / "plot" / "word_budget" / "word_budget.json"
    budget_task = root / "plot" / "word_budget" / "word_budget.agent_tasks.md"
    scene_task = root / "plot" / "word_budget" / "scene_inventory_expansion.agent_tasks.md"
    obligation_task = root / "plot" / "chapter_obligations" / "chapter_obligations.agent_tasks.md"
    review = root / "reviews" / "word_budget" / "word_budget_review.md"
    obligation_review = root / "reviews" / "word_budget" / "chapter_obligation_review.md"
    candidate = root / "plot" / "candidates" / "outlines" / "word_budget_expansion.md"
    scene_plan = root / "plot" / "candidates" / "scenes" / "word_budget_scene_inventory.md"
    scene_review = root / "reviews" / "word_budget" / "scene_inventory_review.md"

    prefix = "longform" if force else "longform-required"
    _add_gate(
        gates,
        f"{prefix}:word-budget-json",
        budget_json.exists(),
        "blocking",
        "word budget JSON exists",
        "目标达到中长篇规模或正在执行 longform-planning；先运行 word-budget / longform-budget，不能直接批量写正文。",
    )
    if not budget_json.exists():
        return

    payload = _read_json(budget_json)
    status = str(payload.get("status") or "").strip().lower()
    _add_gate(
        gates,
        f"{prefix}:word-budget-review",
        review.exists(),
        "blocking",
        "word-budget platform review exists",
        "平台 Agent 必须写 reviews/word_budget/word_budget_review.md，确认字数-剧情库存映射后才能进入批量场景开发。",
    )
    budget_completion = agent_task_completion_status(budget_task, root=root)
    _add_gate(
        gates,
        f"{prefix}:word-budget-task-complete",
        budget_completion.get("complete") is True,
        "blocking",
        "word-budget platform-agent task completed",
        f"word_budget.agent_tasks.md 未完成：{budget_completion.get('message')}",
    )
    _add_gate(
        gates,
        f"{prefix}:chapter-obligation-task",
        obligation_task.exists(),
        "blocking",
        "chapter obligation planning task exists",
        "word-budget 后必须生成 plot/chapter_obligations/chapter_obligations.agent_tasks.md，用于把数字预算转成章节承诺和读者体验契约。",
    )
    obligation_completion = agent_task_completion_status(obligation_task, root=root)
    _add_gate(
        gates,
        f"{prefix}:chapter-obligation-task-complete",
        obligation_completion.get("complete") is True,
        "blocking",
        "chapter obligation planning task completed",
        f"chapter_obligations.agent_tasks.md 未完成：{obligation_completion.get('message')}",
    )
    _add_gate(
        gates,
        f"{prefix}:chapter-obligation-review",
        obligation_review.exists(),
        "blocking",
        "chapter obligation review exists",
        "平台 Agent 必须写 reviews/word_budget/chapter_obligation_review.md，确认每章承诺、兑现/延迟和读者问题后才能批量生成。",
    )
    if status == "needs_expansion":
        _add_gate(gates, f"{prefix}:budgeted-outline-candidate", candidate.exists(), "blocking", "budgeted outline candidate exists", "预算显示剧情库存不足；平台 Agent 需处理 word_budget.agent_tasks.md。")
        _add_gate(gates, f"{prefix}:scene-inventory-expansion", scene_plan.exists(), "blocking", "scene inventory expansion candidate exists", "预算显示场景库存不足；平台 Agent 需处理 scene_inventory_expansion.agent_tasks.md。")
        _add_gate(gates, f"{prefix}:scene-inventory-review", scene_review.exists(), "blocking", "scene inventory review exists", "扩展场景库存后，平台 Agent 需写 reviews/word_budget/scene_inventory_review.md。")
        scene_completion = agent_task_completion_status(scene_task, root=root)
        _add_gate(
            gates,
            f"{prefix}:scene-inventory-task-complete",
            scene_completion.get("complete") is True,
            "blocking",
            "scene inventory platform-agent task completed",
            f"scene_inventory_expansion.agent_tasks.md 未完成：{scene_completion.get('message')}",
        )


def _add_review_audit_route_gates(gates: list[dict[str, str]], root: Path) -> None:
    canon_lint = root / "reviews" / "canon_lint.json"
    canon_lint_payload = _read_json(canon_lint)
    canon_summary = canon_lint_payload.get("summary") if isinstance(canon_lint_payload.get("summary"), dict) else {}
    canon_lint_blocking = int(canon_summary.get("blocking_count", 0) or 0)
    _add_gate(
        gates,
        "review:canon-lint",
        canon_lint.exists() and canon_lint_payload.get("schema") == "literary-engineering-workbench/canon-lint/v0.1" and canon_lint_blocking == 0,
        "blocking",
        "canon-lint exists with no blocking issues",
        f"canon-lint 缺失、schema 无效或仍有 blocking={canon_lint_blocking}；先运行 canon-lint 并修复阻塞。",
    )

    canon_task = root / "reviews" / "agent" / "canon_review.agent_tasks.md"
    canon_completion = agent_task_completion_status(canon_task, root=root)
    canon_review = root / "reviews" / "agent" / "canon_review.json"
    canon_payload = _read_json(canon_review)
    canon_schema_errors, _canon_warnings = validate_payload(canon_payload, "canon_review.v1") if canon_payload else ([{"path": "$", "message": "missing"}], [])
    canon_blocking = canon_payload.get("blocking_issues") if isinstance(canon_payload.get("blocking_issues"), list) else []
    canon_warnings = canon_payload.get("warnings") if isinstance(canon_payload.get("warnings"), list) else []
    unresolved = canon_payload.get("unresolved_facts") if isinstance(canon_payload.get("unresolved_facts"), list) else []
    timeline = canon_payload.get("timeline_risks") if isinstance(canon_payload.get("timeline_risks"), list) else []
    canon_clean = (
        canon_review.exists()
        and (root / "reviews" / "agent" / "canon_review.md").exists()
        and canon_completion.get("complete") is True
        and not canon_schema_errors
        and canon_payload.get("conclusion") == "pass"
        and not canon_blocking
        and not canon_warnings
        and not unresolved
        and not timeline
    )
    _add_gate(
        gates,
        "review:canon-review-clean-pass",
        canon_clean,
        "blocking",
        "platform-agent canon review clean pass",
        "canon_review.v1 未 clean pass：需要 sidecar completion、schema pass、conclusion=pass，且 blocking/warnings/unresolved_facts/timeline_risks 全空。",
    )

    longform = root / "reviews" / "longform" / "longform_audit.json"
    longform_payload = _read_json(longform)
    _add_gate(
        gates,
        "review:longform-audit",
        longform.exists()
        and (root / "reviews" / "longform" / "longform_audit.md").exists()
        and (root / "plot" / "longform_graph.json").exists()
        and longform_payload.get("schema") == "literary-engineering-workbench/longform-audit/v0.1",
        "blocking",
        "longform audit and graph exist",
        "缺少 reviews/longform/longform_audit.* 或 plot/longform_graph.json，或 longform audit schema 无效。",
    )

    committee_task = root / "reviews" / "agent" / "committee_project-final-audit.agent_tasks.md"
    committee_completion = agent_task_completion_status(committee_task, root=root)
    committee = root / "reviews" / "agent" / "committee_project-final-audit.json"
    committee_payload = _read_json(committee)
    committee_schema_errors, _committee_warnings = validate_payload(committee_payload, "committee_review.v1") if committee_payload else ([{"path": "$", "message": "missing"}], [])
    action_items = committee_payload.get("action_items") if isinstance(committee_payload.get("action_items"), list) else []
    disagreements = committee_payload.get("disagreements") if isinstance(committee_payload.get("disagreements"), list) else []
    committee_clean = (
        committee.exists()
        and committee.with_suffix(".md").exists()
        and committee_completion.get("complete") is True
        and not committee_schema_errors
        and committee_payload.get("final_recommendation") == "approve"
        and not action_items
        and not disagreements
    )
    _add_gate(
        gates,
        "review:committee-approve",
        committee_clean,
        "blocking",
        "committee approved with no open action items",
        "committee_project-final-audit 未通过：需要 sidecar completion、schema pass、final_recommendation=approve，且 action_items/disagreements 全空。",
    )


def _add_asset_route_gates(gates: list[dict[str, str]], root: Path) -> None:
    candidates = _asset_candidate_files(root)
    sidecars = _asset_creation_sidecars(root)
    _add_gate(
        gates,
        "asset-candidates-or-sidecars",
        bool(candidates or sidecars),
        "blocking",
        "candidate asset or asset creation sidecar exists",
        "没有候选资产或资产创建 sidecar；先运行 asset-create / agent-create-*，再由平台 Agent 完成候选 JSON/报告。",
    )
    seen = {path.stem for path in candidates}
    for task in sidecars:
        candidate_path = _agent_task_base(task).with_suffix(".json")
        if candidate_path.stem in seen:
            continue
        _add_asset_candidate_gates(gates, root, candidate_path, from_sidecar=task)
    for candidate in candidates:
        _add_asset_candidate_gates(gates, root, candidate)


def _add_asset_candidate_gates(gates: list[dict[str, str]], root: Path, candidate: Path, from_sidecar: Path | None = None) -> None:
    payload = _read_json(candidate)
    candidate_id = str(payload.get("candidate_id") or candidate.stem)
    creation_task = from_sidecar or candidate.with_suffix(".agent_tasks.md")
    creation_completion = agent_task_completion_status(creation_task, root=root)
    report = candidate.with_suffix(".md")
    review_json = root / "reviews" / "assets" / f"{candidate_id}_review.json"
    review_md = review_json.with_suffix(".md")
    review_task = review_json.with_suffix(".agent_tasks.md")
    review_completion = agent_task_completion_status(review_task, root=root)
    review_payload = _read_json(review_json)
    review_status = str(review_payload.get("status") or "").strip().lower()
    blocking = review_payload.get("blocking_issues") if isinstance(review_payload.get("blocking_issues"), list) else []
    revisions = review_payload.get("revision_actions") if isinstance(review_payload.get("revision_actions"), list) else []
    approval = _approval_record(root, candidate_id)
    promotion = root / "workflow" / "asset_promotions" / f"{candidate_id}_promotion.json"
    promotion_payload = _read_json(promotion)
    outputs = promotion_payload.get("outputs") if isinstance(promotion_payload.get("outputs"), list) else []
    missing_outputs = [str(item) for item in outputs if not _path_exists(root, str(item))]

    _add_gate(
        gates,
        f"{candidate_id}:asset-creation-sidecar-complete",
        creation_completion.get("complete") is True,
        "blocking",
        f"{candidate_id} asset creation sidecar completed",
        f"{candidate_id} 创建 sidecar 未完成：{creation_completion.get('message')}",
    )
    _add_gate(
        gates,
        f"{candidate_id}:asset-candidate-json",
        candidate.exists(),
        "blocking",
        f"{candidate_id} candidate JSON exists",
        f"{candidate_id} 缺少候选 JSON：{_rel(candidate, root)}。",
    )
    _add_gate(
        gates,
        f"{candidate_id}:asset-candidate-report",
        report.exists(),
        "blocking",
        f"{candidate_id} candidate report exists",
        f"{candidate_id} 缺少候选说明：{_rel(report, root)}。",
    )
    _add_gate(
        gates,
        f"{candidate_id}:asset-review-sidecar-complete",
        review_completion.get("complete") is True,
        "blocking",
        f"{candidate_id} asset review sidecar completed",
        f"{candidate_id} 审查 sidecar 未完成：{review_completion.get('message')}",
    )
    _add_gate(
        gates,
        f"{candidate_id}:asset-review-clean-pass",
        review_json.exists() and review_md.exists() and review_status == "pass" and not blocking and not revisions,
        "blocking",
        f"{candidate_id} asset review clean pass",
        f"{candidate_id} 资产审查未 clean pass；status={review_status or 'missing'}，blocking={len(blocking)}，revision_actions={len(revisions)}。",
    )
    _add_gate(
        gates,
        f"{candidate_id}:asset-approval",
        str(approval.get("decision") or "") == "approve",
        "blocking",
        f"{candidate_id} approve record exists",
        f"{candidate_id} 缺少用户 approve 记录；review 不能替代 approval。",
    )
    _add_gate(
        gates,
        f"{candidate_id}:asset-promotion",
        promotion.exists() and promotion_payload.get("status") == "promoted" and not promotion_payload.get("allow_unapproved") and not missing_outputs,
        "blocking",
        f"{candidate_id} promoted without approval bypass",
        f"{candidate_id} 尚未正式晋升，或使用了 allow_unapproved，或晋升输出缺失：{', '.join(missing_outputs) or 'n/a'}。",
    )


def _asset_candidate_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for folder in ASSET_CANDIDATE_DIRS.values():
        base = root / folder
        if not base.exists():
            continue
        candidates.extend(
            path
            for path in sorted(base.glob("*.json"))
            if not path.name.endswith(".agent_completion.json") and not path.name.endswith(".submission.json")
        )
    return candidates


def _asset_creation_sidecars(root: Path) -> list[Path]:
    sidecars: list[Path] = []
    for folder in ASSET_CANDIDATE_DIRS.values():
        base = root / folder
        if base.exists():
            sidecars.extend(sorted(base.glob("*.agent_tasks.md")))
    return sidecars


def _agent_task_base(task_path: Path) -> Path:
    name = task_path.name
    suffix = ".agent_tasks.md"
    if name.endswith(suffix):
        return task_path.with_name(name[: -len(suffix)])
    return task_path.with_suffix("")


def _approval_record(root: Path, run_id: str) -> dict[str, object]:
    index = root / "workflow" / "approvals" / "index.jsonl"
    if not index.exists():
        return {}
    latest: dict[str, object] = {}
    for line in index.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("run_id") == run_id:
            latest = payload
    return latest


def _project_target_words(root: Path) -> int:
    text = _read_text(root / "project.yaml")
    values: list[int] = []
    for key in ("target_length", "target_words"):
        for match in re.finditer(rf"(?m)^\s*{re.escape(key)}:\s*([0-9][0-9_,]*)\s*$", text):
            raw = match.group(1).replace("_", "").replace(",", "")
            try:
                values.append(int(raw))
            except ValueError:
                continue
    return max(values) if values else 0


def _debug_waiver_hits(root: Path) -> list[str]:
    hits: list[str] = []
    for path in sorted(root.rglob("*.json")):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        payload = _read_json(path)
        if not payload:
            continue
        hits.extend(_scan_debug_waivers(payload, _rel(path, root), ()))
    return _unique(hits)


def _scan_debug_waivers(value: object, source: str, trail: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            next_trail = trail + (key_text,)
            if key_text in DEBUG_WAIVER_KEYS and _truthy_debug_flag(item):
                hits.append(f"{source}:{'.'.join(next_trail)}={item}")
            if key_text == "decision" and str(item).strip().lower() in DEBUG_WAIVER_DECISIONS:
                hits.append(f"{source}:{'.'.join(next_trail)}={item}")
            hits.extend(_scan_debug_waivers(item, source, next_trail))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_scan_debug_waivers(item, source, trail + (str(index),)))
    return hits


def _truthy_debug_flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"true", "yes", "1", "allow", "allowed", "enabled"}


def _add_gate(gates: list[dict[str, str]], key: str, passed: bool, severity: str, passed_message: str, failed_message: str) -> None:
    gates.append(
        {
            "key": key,
            "status": "pass" if passed else "fail",
            "severity": "info" if passed else severity,
            "message": passed_message if passed else failed_message,
        }
    )


_SCENE_GATE_PHASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("上下文", ("context-",)),
    ("角色推演", ("roleplay-",)),
    ("分支决策", ("branch-",)),
    (
        "编剧准备",
        (
            "scene-word-budget-",
            "reader-experience-",
            "narrative-rhythm-",
            "composition-",
        ),
    ),
    (
        "候选生成",
        (
            "prose-candidate",
            "candidate-generation-",
            "generation-agent-task-",
            "style-lint-",
            "candidate-word-budget",
        ),
    ),
    (
        "候选审查",
        (
            "agent-review-",
            "candidate-review-",
            "revision-evasion-",
            "style-adherence-review",
        ),
    ),
    ("晋升", ("promotion-", "promoted-draft")),
    ("静态审查", ("static-review-",)),
    ("状态写回", ("state-", "canon-writeback")),
)


def _scene_gate_phase(key: str) -> tuple[int, str]:
    """Return the formal scene stage for one route-audit gate.

    A route audit is an observability surface, not a second workflow engine.  The
    mapping deliberately follows the formal scene pipeline so later, unreachable
    gates can be shown as waiting without weakening their eventual enforcement.
    """

    label = key.split(":", 1)[-1]
    for index, (name, prefixes) in enumerate(_SCENE_GATE_PHASES):
        if label.startswith(prefixes):
            return index, name
    return len(_SCENE_GATE_PHASES), "后续步骤"


def _mark_waiting_scene_gates(gates: list[dict[str, str]]) -> None:
    """Demote only unreachable downstream failures to an informational wait.

    All failing gates in the earliest incomplete formal phase remain blocking.
    This preserves parallel checks such as exact-candidate review and new-character
    registration, while avoiding a misleading wall of failures for promotion and
    state evolution that cannot run yet.
    """

    failed_phases = [
        _scene_gate_phase(str(gate["key"]))[0]
        for gate in gates
        if gate.get("status") == "fail" and gate.get("severity") == "blocking"
    ]
    if not failed_phases:
        return
    active_phase = min(failed_phases)
    active_phase_name = (
        _SCENE_GATE_PHASES[active_phase][0]
        if active_phase < len(_SCENE_GATE_PHASES)
        else "后续步骤"
    )
    for gate in gates:
        phase, _ = _scene_gate_phase(str(gate["key"]))
        if phase <= active_phase or gate.get("status") != "fail" or gate.get("severity") != "blocking":
            continue
        original_message = str(gate.get("message") or "")
        gate["status"] = "waiting"
        gate["severity"] = "info"
        gate["message"] = f"等待“{active_phase_name}”阶段的阻塞门禁先解决，尚未到达本步骤。原检查：{original_message}"


def _scene_files(root: Path) -> list[Path]:
    scenes = root / "scenes"
    if not scenes.exists():
        return []
    return sorted(path for path in scenes.glob("*.yaml") if not path.name.startswith("_"))


def _scene_audit_scope(root: Path) -> dict[str, int]:
    scene_files = _scene_files(root)
    started_ids = _started_scene_ids(root)
    started = sum(1 for scene_path in scene_files if _scene_id(scene_path) in started_ids)
    return {
        "total_scene_count": len(scene_files),
        "started_scene_count": started,
        "planned_scene_count": len(scene_files) - started,
    }


def _started_scene_ids(root: Path) -> set[str]:
    """Build one filesystem index instead of probing every planned scene repeatedly."""

    started: set[str] = set()
    context_dir = root / "memory" / "context_packets"
    if context_dir.is_dir():
        started.update(path.stem for path in context_dir.glob("scene_*.md"))
    branch_dir = root / "branches"
    if branch_dir.is_dir():
        started.update(path.name for path in branch_dir.iterdir() if path.is_dir() and path.name.startswith("scene_"))
    composition_dir = root / "drafts" / "compositions"
    if composition_dir.is_dir():
        started.update(path.stem.removesuffix("_composition") for path in composition_dir.glob("scene_*_composition.json"))
    candidate_dir = root / "drafts" / "candidates"
    if candidate_dir.is_dir():
        for path in candidate_dir.glob("scene_*.md"):
            scene_id = path.name.split("-", 1)[0]
            if scene_id.startswith("scene_"):
                started.add(scene_id)
    review_dir = root / "reviews" / "agent"
    if review_dir.is_dir():
        started.update(path.stem.removesuffix("_scene_review") for path in review_dir.glob("scene_*_scene_review.json"))
    promotion_dir = root / "drafts" / "promotions"
    if promotion_dir.is_dir():
        started.update(path.stem.removesuffix("_promotion") for path in promotion_dir.glob("scene_*_promotion.json"))
    draft_dir = root / "drafts" / "scenes"
    if draft_dir.is_dir():
        started.update(path.stem for path in draft_dir.glob("scene_*.md"))
    state_dir = root / "characters" / "state_patches"
    if state_dir.is_dir():
        started.update(path.stem.removesuffix("_state_patch") for path in state_dir.glob("scene_*_state_patch.json"))
    task_dir = root / "workflow" / "tasks"
    if task_dir.is_dir():
        for path in task_dir.glob("scene-development-scene_*-*.task.json"):
            match = re.match(r"scene-development-(scene_[^-]+)-", path.name)
            if match:
                started.add(match.group(1))
    return {scene_id for scene_id in started if scene_id.startswith("scene_")}


def _add_scene_development_gates(gates: list[dict[str, str]], root: Path, scene_path: Path) -> None:
    first_scene_gate = len(gates)
    scene_id = _scene_id(scene_path)
    context = root / "memory" / "context_packets" / f"{scene_id}.md"
    context_trace = context_trace_status(root, scene_id, context)
    roleplay = root / "branches" / scene_id / "roleplay_simulation.md"
    roleplay_task = root / "branches" / scene_id / "roleplay_simulation.agent_tasks.md"
    roleplay_text = _read_text(roleplay)
    branch_manifest = root / "branches" / scene_id / "branch_manifest.json"
    branch_task = root / "branches" / scene_id / "branch_manifest.agent_tasks.md"
    branch_payload = _read_json(branch_manifest)
    branches = branch_payload.get("branches")
    selection = root / "branches" / scene_id / "branch_selection.md"
    selection_gate = branch_selection_status(selection)
    composition_json = root / "drafts" / "compositions" / f"{scene_id}_composition.json"
    composition_task = root / "drafts" / "compositions" / f"{scene_id}_composition.agent_tasks.md"
    composition_payload = _read_json(composition_json)
    composition_provenance = composition_payload.get("formal_cli_provenance", {}) if isinstance(composition_payload.get("formal_cli_provenance"), dict) else {}
    flow_gate = composition_payload.get("flow_gate", {}) if isinstance(composition_payload.get("flow_gate"), dict) else {}
    composition_ready = (
        composition_json.exists()
        and composition_payload.get("selection_source") == "selection"
        and flow_gate.get("ready_for_generation") is True
    )
    candidate_path = _promotion_candidate_path(root, scene_id) or _latest_scene_candidate(root, scene_id)
    generation_task = candidate_path.with_suffix(".agent_tasks.md") if candidate_path is not None else None
    review_json = root / "reviews" / "agent" / f"{scene_id}_scene_review.json"
    review_task = review_json.with_suffix(".agent_tasks.md")
    candidate_gate = (
        candidate_review_gate(root, scene_id, candidate_path)
        if candidate_path is not None
        else {"status": "missing", "message": "no prose candidate found for exact-candidate review"}
    )
    generation_gate = (
        candidate_generation_gate(root, scene_id, candidate_path)
        if candidate_path is not None
        else {"status": "missing", "message": "no prose candidate found for generation provenance"}
    )
    promotion_json = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    promotion_payload = _read_json(promotion_json)
    promoted_draft = root / "drafts" / "scenes" / f"{scene_id}.md"
    static_review = root / "reviews" / f"{scene_id}-review.md"
    static_review_conclusion = _static_review_conclusion(static_review)
    state_patch_json = root / "characters" / "state_patches" / f"{scene_id}_state_patch.json"
    state_patch_report = root / "characters" / "state_patches" / f"{scene_id}_state_patch.md"
    state_task = state_patch_json.with_suffix(".agent_tasks.md")
    budget_contract = scene_word_budget_contract(root, scene_path)
    reader_contract = reader_experience_contract(root, scene_path)
    rhythm_contract = narrative_rhythm_contract(root, scene_path, composition_json)

    _add_gate(
        gates,
        f"{scene_id}:context-packet",
        context.exists(),
        "blocking",
        f"{scene_id} context packet exists",
        f"{scene_id} 缺少 memory/context_packets/{scene_id}.md；先运行 context 或 rebuild-context。",
    )
    _add_gate(
        gates,
        f"{scene_id}:context-trace",
        context_trace.passed,
        "blocking",
        f"{scene_id} context trace validates loaded source groups",
        f"{scene_id} 上下文来源证明无效：{context_trace.message}。先重跑 context，并检查 trace 是否列出 scene/project/canon/character/style/word-budget 来源。",
    )
    _add_gate(
        gates,
        f"{scene_id}:roleplay-simulation",
        roleplay.exists(),
        "blocking",
        f"{scene_id} roleplay simulation exists",
        f"{scene_id} 缺少 branches/{scene_id}/roleplay_simulation.md；正式场景开发必须先运行 simulate-scene --agent。",
    )
    _add_gate(
        gates,
        f"{scene_id}:roleplay-cli-provenance",
        roleplay.exists() and "正式 CLI 来源：`simulate-scene`" in roleplay_text,
        "blocking",
        f"{scene_id} roleplay has simulate-scene CLI provenance",
        f"{scene_id} 的 RP 文件缺少 simulate-scene 正式来源标记；手写 RP 只能作为 exploratory/debug，不满足正式路线。",
    )
    _add_gate(
        gates,
        f"{scene_id}:roleplay-reading-receipt",
        roleplay.exists() and "读取回执" in roleplay_text,
        "blocking",
        f"{scene_id} roleplay reading receipt exists",
        f"{scene_id} 的 RP 文件缺少平台 Agent 读取回执；用 simulate-scene --agent 或补正式读取回执。",
    )
    _add_gate(
        gates,
        f"{scene_id}:roleplay-agent-tasks-resolved",
        roleplay.exists() and "[AGENT_TASK:" not in roleplay_text,
        "blocking",
        f"{scene_id} roleplay AGENT_TASK directives resolved",
        f"{scene_id} 的 roleplay_simulation.md 仍含 [AGENT_TASK: ...]；平台 Agent 需补全/替换后再继续。",
    )
    roleplay_completion = agent_task_completion_status(roleplay_task, root=root)
    _add_gate(
        gates,
        f"{scene_id}:roleplay-agent-task-complete",
        roleplay_completion.get("complete") is True,
        "blocking",
        f"{scene_id} roleplay platform-agent task completed",
        f"{scene_id} 的 RP sidecar 未完成：{roleplay_completion.get('message')}",
    )
    _add_gate(
        gates,
        f"{scene_id}:branch-manifest",
        branch_manifest.exists() and isinstance(branches, list) and bool(branches),
        "blocking",
        f"{scene_id} branch manifest exists",
        f"{scene_id} 缺少有效 branches/{scene_id}/branch_manifest.json；正式场景开发必须运行 branch-simulate --agent。",
    )
    _add_gate(
        gates,
        f"{scene_id}:branch-cli-provenance",
        branch_payload.get("formal_cli_provenance", {}).get("created_by") == "branch-simulate" if isinstance(branch_payload.get("formal_cli_provenance"), dict) else False,
        "blocking",
        f"{scene_id} branch manifest has branch-simulate CLI provenance",
        f"{scene_id} 的 branch_manifest.json 缺少 formal_cli_provenance.created_by=branch-simulate；手写 manifest 只能作为 exploratory/debug。",
    )
    branch_completion = agent_task_completion_status(branch_task, root=root)
    _add_gate(
        gates,
        f"{scene_id}:branch-agent-task-complete",
        branch_completion.get("complete") is True,
        "blocking",
        f"{scene_id} branch platform-agent task completed",
        f"{scene_id} 的 branch sidecar 未完成：{branch_completion.get('message')}",
    )
    _add_gate(
        gates,
        f"{scene_id}:branch-selection",
        selection_gate["status"] == "selected",
        "blocking",
        f"{scene_id} formal branch selection exists",
        f"{scene_id} 的 branch_selection.md 未记录 decision: selected 与 selected_branch；当前状态：{selection_gate['message']}。",
    )
    _add_gate(
        gates,
        f"{scene_id}:composition-json",
        composition_json.exists(),
        "blocking",
        f"{scene_id} composition JSON exists",
        f"{scene_id} 缺少 drafts/compositions/{scene_id}_composition.json；先基于正式分支运行 compose-scene。",
    )
    _add_gate(
        gates,
        f"{scene_id}:composition-ready",
        composition_ready,
        "blocking",
        f"{scene_id} composition is ready for generation",
        f"{scene_id} 的 composition 未达到 selection_source=selection 且 ready_for_generation=true；重建 compose-scene。",
    )
    _add_gate(
        gates,
        f"{scene_id}:composition-cli-provenance",
        composition_provenance.get("created_by") == "compose-scene",
        "blocking",
        f"{scene_id} composition has compose-scene CLI provenance",
        f"{scene_id} 的 composition 缺少 formal_cli_provenance.created_by=compose-scene；手写 composition 不能满足正式 generate-scene 门禁。",
    )
    composition_completion = agent_task_completion_status(composition_task, root=root)
    _add_gate(
        gates,
        f"{scene_id}:composition-agent-task-complete",
        composition_completion.get("complete") is True,
        "blocking",
        f"{scene_id} composition platform-agent task completed",
        f"{scene_id} 的 composition sidecar 未完成：{composition_completion.get('message')}",
    )
    budget_status = str(budget_contract.get("status") or "").strip().lower()
    _add_gate(
        gates,
        f"{scene_id}:scene-word-budget-contract",
        budget_status in {"pass", "not_required"},
        "blocking",
        f"{scene_id} scene word-budget contract is ready",
        f"{scene_id} 缺少可用场景字数预算硬属性：{budget_contract.get('message')}",
    )
    _add_gate(
        gates,
        f"{scene_id}:scene-word-budget-alignment",
        budget_contract.get("alignment_status") != "manual_override_needs_review",
        "warning",
        f"{scene_id} scene word-count target aligns with budget source",
        f"{scene_id} 的 scene.yaml 字数目标与 word_budget 推导值差异过大：{'; '.join(str(item) for item in budget_contract.get('warnings', []))}",
    )
    reader_status = str(reader_contract.get("status") or "").strip().lower()
    _add_gate(
        gates,
        f"{scene_id}:reader-experience-contract",
        reader_status in {"pass", "not_required"},
        "blocking",
        f"{scene_id} reader-experience contract is ready",
        f"{scene_id} 缺少可用读者体验/章节义务硬属性：{reader_contract.get('message')}",
    )
    _add_gate(
        gates,
        f"{scene_id}:narrative-rhythm-contract",
        str(rhythm_contract.get("status") or "") in {"pass", "defaulted"},
        "blocking",
        f"{scene_id} narrative rhythm and bridge contract is available",
        f"{scene_id} 缺少叙事节奏/场景桥接硬属性：{rhythm_contract.get('message')}",
    )
    _add_gate(
        gates,
        f"{scene_id}:narrative-rhythm-explicit",
        str(rhythm_contract.get("status") or "") == "pass",
        "warning",
        f"{scene_id} narrative rhythm/bridge is explicit",
        f"{scene_id} 使用默认叙事节奏/场景桥接契约；建议在 scene.yaml 或 composition 中显式填写，避免场景节奏扁平化。",
    )
    _add_gate(
        gates,
        f"{scene_id}:prose-candidate",
        candidate_path is not None and candidate_path.exists(),
        "blocking",
        f"{scene_id} prose candidate exists",
        f"{scene_id} 缺少 drafts/candidates/{scene_id}-*.md；不能直接写 drafts/scenes 正式草稿。",
    )
    _add_gate(
        gates,
        f"{scene_id}:candidate-generation-provenance",
        generation_gate.get("status") == "pass",
        "blocking",
        f"{scene_id} candidate has formal CLI/platform-agent generation provenance",
        f"{scene_id} 候选稿缺少正式 generate-scene provenance：{generation_gate.get('message') or generation_gate.get('status') or 'missing'}。正式候选必须有 prompt manifest、.agent_tasks.md 和平台 Agent manifest 约束字段。",
    )
    if generation_task is not None:
        generation_completion = agent_task_completion_status(generation_task, root=root)
        _add_gate(
            gates,
            f"{scene_id}:generation-agent-task-complete",
            generation_completion.get("complete") is True,
            "blocking",
            f"{scene_id} generation platform-agent task completed",
            f"{scene_id} 的 generation sidecar 未完成：{generation_completion.get('message')}",
        )
    lint_gate = candidate_gate.get("style_lint") if isinstance(candidate_gate, dict) else {}
    if candidate_path is not None:
        _add_gate(
            gates,
            f"{scene_id}:style-lint-clean",
            isinstance(lint_gate, dict) and lint_gate.get("status") != "blocking",
            "blocking",
            f"{scene_id} Style Lint Gate clean or notes-only",
            f"{scene_id} 候选稿未通过 Style Lint Gate：{style_lint_gate_message(lint_gate if isinstance(lint_gate, dict) else {})}。机械对照句式和 medium+ AI 腔风险必须先修订。",
        )
        budget_gate = candidate_gate.get("word_budget_adherence") if isinstance(candidate_gate, dict) else {}
        budget_status = str(budget_gate.get("status") or "").strip().lower() if isinstance(budget_gate, dict) else ""
        _add_gate(
            gates,
            f"{scene_id}:candidate-word-budget",
            budget_status in {"pass", "not_required"},
            "blocking",
            f"{scene_id} candidate cleaned body satisfies scene word budget",
            f"{scene_id} 候选稿未通过场景字数预算门禁：{budget_gate.get('message') if isinstance(budget_gate, dict) else 'missing'}。不要用非正文信息或灌水内容补字数。",
        )
    _add_gate(
        gates,
        f"{scene_id}:agent-review-json",
        review_json.exists(),
        "blocking",
        f"{scene_id} platform Agent review JSON exists",
        f"{scene_id} 缺少 reviews/agent/{scene_id}_scene_review.json；运行 agent-review-scene --draft <candidate> 并由平台 Agent 填写 scene_review.v1。",
    )
    review_completion = agent_task_completion_status(review_task, root=root)
    _add_gate(
        gates,
        f"{scene_id}:agent-review-task-complete",
        review_completion.get("complete") is True,
        "blocking",
        f"{scene_id} platform Agent review task completed",
        f"{scene_id} 的 AgentReview sidecar 未完成：{review_completion.get('message')}",
    )
    _add_gate(
        gates,
        f"{scene_id}:candidate-review-pass",
        candidate_gate.get("status") == "pass",
        "blocking",
        f"{scene_id} exact prose candidate review passed",
        f"{scene_id} 候选稿未通过 exact-candidate AgentReview：{candidate_gate.get('message') or candidate_gate.get('status') or 'missing'}。",
    )
    review_payload = _read_json(review_json)
    review_budget_status = _word_budget_adherence_status(review_payload)
    new_character_issues = new_character_register_issues(review_payload, root, mode="review") if review_payload else ["new_character_register is missing"]
    _add_gate(
        gates,
        f"{scene_id}:agent-review-word-budget",
        review_budget_status in {"pass", "not_required"},
        "blocking",
        f"{scene_id} AgentReview word budget gate passed",
        f"{scene_id} 的 AgentReview 缺少 clean pass 的 word_budget_adherence；当前状态：{review_budget_status or 'missing'}。",
    )
    _add_gate(
        gates,
        f"{scene_id}:agent-review-new-character-register",
        not new_character_issues,
        "blocking",
        f"{scene_id} AgentReview new-character register is resolved",
        f"{scene_id} 的 AgentReview 新角色登记未解决：{'; '.join(new_character_issues)}。",
    )
    review_rhythm_status = rhythm_review_status(review_payload)
    review_rhythm = review_payload.get("narrative_rhythm_adherence") if isinstance(review_payload.get("narrative_rhythm_adherence"), dict) else {}
    _add_gate(
        gates,
        f"{scene_id}:agent-review-narrative-rhythm",
        review_rhythm_status in {"pass", "not_applicable"}
        and review_rhythm.get("rhythm_executed") is not False
        and review_rhythm.get("bridge_executed") is not False,
        "blocking",
        f"{scene_id} AgentReview narrative rhythm gate passed",
        f"{scene_id} 的 AgentReview 叙事节奏/场景桥接未 clean pass：{review_rhythm_status or 'missing'}。",
    )
    canon_review_ok, canon_review_message = _agent_review_canon_writeback_ok(review_payload)
    _add_gate(
        gates,
        f"{scene_id}:agent-review-canon-writeback",
        canon_review_ok,
        "blocking",
        f"{scene_id} AgentReview canon writeback declaration exists",
        f"{scene_id} 的 AgentReview 缺少可执行 canon 写回判断：{canon_review_message}。",
    )
    revision_manifest = _revision_manifest_path(root, scene_id, candidate_path)
    if candidate_path is not None and _is_revision_candidate(root, candidate_path):
        revision_payload = _read_json(revision_manifest)
        _add_gate(
            gates,
            f"{scene_id}:revision-evasion-clean",
            _revision_evasion_clean(revision_payload),
            "blocking",
            f"{scene_id} revision anti-evasion manifest is clean",
            f"{scene_id} 使用修订候选但缺少干净的反规避修订记录；需要 revise-scene manifest 写入 anti_evasion_protocol_applied=true，且 evasion_risks_unresolved 为空或 false。",
        )
    _add_gate(
        gates,
        f"{scene_id}:promotion-manifest",
        promotion_json.exists(),
        "blocking",
        f"{scene_id} promotion manifest exists",
        f"{scene_id} 缺少 drafts/promotions/{scene_id}_promotion.json；通过候选专属审查后运行 promote-candidate。",
    )
    _add_gate(
        gates,
        f"{scene_id}:promoted-draft",
        promoted_draft.exists(),
        "blocking",
        f"{scene_id} promoted draft exists",
        f"{scene_id} 缺少 drafts/scenes/{scene_id}.md；不能跳过 promote-candidate 直接进入章节装配。",
    )
    _add_gate(
        gates,
        f"{scene_id}:static-review-pass",
        static_review.exists() and static_review_conclusion == "pass",
        "blocking",
        f"{scene_id} local static review-scene passed",
        f"{scene_id} 缺少 clean 本地 review-scene；当前结论：{static_review_conclusion or 'missing'}。promote 后必须运行 review-scene 并处理 notes。",
    )
    if promotion_json.exists():
        promoted_candidate = str(promotion_payload.get("candidate") or "").strip()
        gate = candidate_review_gate(root, scene_id, root / promoted_candidate) if promoted_candidate else {"status": "missing", "message": "promotion manifest has no candidate"}
        _add_gate(
            gates,
            f"{scene_id}:promotion-candidate-review",
            gate.get("status") == "pass",
            "blocking",
            f"{scene_id} promoted candidate had a formal pre-promotion review",
            f"{scene_id} promotion 缺少正式候选审查门禁：{gate.get('message') or gate.get('status') or 'missing'}。",
        )
    _add_gate(
        gates,
        f"{scene_id}:state-patch-json",
        state_patch_json.exists(),
        "blocking",
        f"{scene_id} state evolution JSON exists",
        f"{scene_id} 缺少 characters/state_patches/{scene_id}_state_patch.json；promote 后运行 state-evolve --agent-tasks。",
    )
    _add_gate(
        gates,
        f"{scene_id}:state-patch-report",
        state_patch_report.exists(),
        "blocking",
        f"{scene_id} state evolution report exists",
        f"{scene_id} 缺少 characters/state_patches/{scene_id}_state_patch.md；平台 Agent 需审查人物状态演化候选。",
    )
    state_completion = agent_task_completion_status(state_task, root=root)
    _add_gate(
        gates,
        f"{scene_id}:state-agent-task-complete",
        state_completion.get("complete") is True,
        "blocking",
        f"{scene_id} state-evolve platform-agent task completed",
        f"{scene_id} 的 state-evolve sidecar 未完成：{state_completion.get('message')}",
    )
    canon_status = canon_writeback_status(root, scene_id)
    _add_gate(
        gates,
        f"{scene_id}:canon-writeback",
        str(canon_status.get("status") or "") in {"pass", "not_required"},
        "blocking",
        f"{scene_id} canon writeback candidate/no-change gate passed",
        f"{scene_id} 的 canon 写回候选门禁未完成：{canon_status.get('message')}",
    )
    if _mounted_style_exists(root):
        style_status = _style_adherence_status(review_payload)
        _add_gate(
            gates,
            f"{scene_id}:style-adherence-review",
            style_status == "pass",
            "blocking",
            f"{scene_id} mounted style adherence reviewed",
            f"{scene_id} 已挂载文风，但 scene_review.v1 缺少 clean pass 的 style_adherence；当前状态：{style_status or 'missing'}。",
        )
    _mark_waiting_scene_gates(gates[first_scene_gate:])


def _promotion_candidate_path(root: Path, scene_id: str) -> Path | None:
    promotion_json = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    payload = _read_json(promotion_json)
    candidate = str(payload.get("candidate") or "").strip()
    if not candidate:
        return None
    path = Path(candidate)
    return path if path.is_absolute() else root / path


def _latest_scene_candidate(root: Path, scene_id: str) -> Path | None:
    candidate_dir = root / "drafts" / "candidates"
    revision_dir = root / "drafts" / "revisions"
    candidates: list[Path] = []
    if candidate_dir.exists():
        candidates.extend(
            path
            for path in candidate_dir.glob(f"{scene_id}-*.md")
            if not path.name.endswith(".agent_tasks.md") and not path.name.endswith(".prompt.md")
        )
    if revision_dir.exists():
        candidates.extend(
            path
            for path in revision_dir.glob(f"{scene_id}_revision.md")
            if not path.name.endswith(".agent_tasks.md") and not path.name.endswith(".prompt.md")
        )
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def _revision_manifest_path(root: Path, scene_id: str, candidate_path: Path | None) -> Path:
    if candidate_path is not None and candidate_path.name.endswith("_revision.md"):
        return candidate_path.with_suffix(".json")
    return root / "drafts" / "revisions" / f"{scene_id}_revision.json"


def _is_revision_candidate(root: Path, candidate_path: Path) -> bool:
    try:
        rel = candidate_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = str(candidate_path)
    return rel.startswith("drafts/revisions/") or candidate_path.name.endswith("_revision.md")


def _revision_evasion_clean(payload: dict[str, object]) -> bool:
    if not payload:
        return False
    if payload.get("anti_evasion_protocol_applied") is not True:
        return False
    unresolved = payload.get("evasion_risks_unresolved")
    if isinstance(unresolved, bool):
        return not unresolved
    if isinstance(unresolved, list):
        return len(unresolved) == 0
    if isinstance(unresolved, str):
        return unresolved.strip().lower() in {"", "false", "none", "no", "[]", "无"}
    return unresolved in (None, 0)


def _static_review_conclusion(path: Path) -> str:
    text = _read_text(path)
    match = re.search(r"(?m)^-\s*(?:审查)?结论：\s*(?:\*\*)?`?([a-z_]+)`?(?:\*\*)?\s*$", text, re.IGNORECASE)
    return match.group(1).strip().lower() if match else ""


def _scene_id(scene_path: Path) -> str:
    text = _read_text(scene_path)
    match = re.search(r"(?m)^\s*scene_id:\s*['\"]?([^'\"\n#]+)", text)
    scene_id = match.group(1).strip() if match else ""
    return scene_id or scene_path.stem


def _non_ready_scene_count(chapter_jsons: list[Path]) -> int:
    total = 0
    for path in chapter_jsons:
        payload = _read_json(path)
        for scene in payload.get("scenes", []) if isinstance(payload.get("scenes"), list) else []:
            if isinstance(scene, dict) and scene.get("status") != "ready":
                total += 1
    return total


def _stale_or_weak_chapter_gate_count(chapter_jsons: list[Path]) -> int:
    total = 0
    required_keys = {
        "agent_review_source_match",
        "agent_review_unresolved_notes",
        "style_adherence_status",
        "word_budget_adherence_status",
        "reader_experience_adherence_status",
        "reader_promise_satisfied",
        "flow_gate_issues",
        "readiness_issues",
    }
    for path in chapter_jsons:
        payload = _read_json(path)
        for scene in payload.get("scenes", []) if isinstance(payload.get("scenes"), list) else []:
            if not isinstance(scene, dict):
                continue
            if not required_keys.issubset(scene):
                total += 1
                continue
            reader_status = scene.get("reader_experience_adherence_status")
            weak = (
                scene.get("review_conclusion") != "pass"
                or scene.get("agent_review_conclusion") != "pass"
                or scene.get("agent_review_schema_status") != "pass"
                or scene.get("agent_review_source_match") is not True
                or bool(scene.get("agent_review_unresolved_notes"))
                or scene.get("word_budget_adherence_status") not in {"pass", "not_required"}
                or reader_status not in {"", "pass", "not_required"}
                or (reader_status in {"pass", "not_required"} and scene.get("reader_promise_satisfied") is False)
                or bool(scene.get("flow_gate_issues"))
                or bool(scene.get("readiness_issues"))
            )
            if weak:
                total += 1
    return total


def _unresolved_scene_review_count(root: Path) -> int:
    review_dir = root / "reviews" / "agent"
    if not review_dir.exists():
        return 0
    unresolved = 0
    for path in sorted(review_dir.glob("*_scene_review.json")):
        payload = _read_json(path)
        scene_id = path.name[: -len("_scene_review.json")]
        if not _review_needs_revision(payload):
            continue
        report = root / "drafts" / "revisions" / f"{scene_id}_revision_report.md"
        manifest = root / "drafts" / "revisions" / f"{scene_id}_revision.json"
        if not (report.exists() and manifest.exists()):
            unresolved += 1
    return unresolved


def _unapplied_state_patch_count(root: Path) -> int:
    patch_dir = root / "characters" / "state_patches"
    if not patch_dir.exists():
        return 0
    count = 0
    for path in sorted(patch_dir.glob("*_state_patch.json")):
        scene_id = path.name[: -len("_state_patch.json")]
        apply_json = patch_dir / f"{scene_id}_state_apply.json"
        apply_report = patch_dir / f"{scene_id}_state_apply.md"
        if not (apply_json.exists() and apply_report.exists()):
            count += 1
    return count


def _unapplied_canon_patch_count(root: Path) -> int:
    patch_dir = root / "canon" / "patches"
    if not patch_dir.exists():
        return 0
    count = 0
    for path in sorted(patch_dir.glob("*_canon_patch.json")):
        payload = _read_json(path)
        if payload.get("applied") is True or str(payload.get("status") or "").strip().lower() == "applied":
            continue
        change = payload.get("canon_change")
        if change is True or str(change).strip().lower() in {"true", "yes", "1", "changed", "change"}:
            count += 1
    return count


def _add_export_release_route_gates(gates: list[dict[str, str]], root: Path, chapter_jsons: list[Path]) -> None:
    chapter_ids = [path.stem for path in chapter_jsons] or ["chapter_0001"]
    for chapter_id in chapter_ids:
        manifest = root / "exports" / chapter_id / "export_manifest.json"
        payload = _read_json(manifest)
        skipped = payload.get("skipped_scenes") if isinstance(payload.get("skipped_scenes"), list) else []
        outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
        output_missing: list[str] = []
        trace_hits: list[str] = []
        for key in ("novel", "screenplay", "video_prompt_pack"):
            rel = str(outputs.get(key) or "")
            if not rel:
                output_missing.append(key)
                continue
            path = root / rel
            if not path.exists():
                output_missing.append(rel)
                continue
            hits = _delivery_trace_hits(path)
            if hits:
                trace_hits.append(f"{rel}:{','.join(hits[:3])}")
        _add_gate(
            gates,
            f"{chapter_id}:export-package-clean",
            manifest.exists()
            and payload.get("schema") == "literary-engineering-workbench/export-package/v0.1"
            and payload.get("include_blocked") is not True
            and not skipped
            and not output_missing
            and not trace_hits,
            "blocking",
            f"{chapter_id} export package is clean",
            f"{chapter_id} 导出包未通过：manifest/schema/include_blocked/skipped/output/trace 有问题；skipped={len(skipped)}，missing={', '.join(output_missing) or 'none'}，trace={'; '.join(trace_hits[:4]) or 'none'}。",
        )

        docx = outputs.get("docx") if isinstance(outputs.get("docx"), dict) else {}
        inspections = outputs.get("docx_inspections") if isinstance(outputs.get("docx_inspections"), dict) else {}
        missing_docx = [str(rel) for rel in docx.values() if not (root / str(rel)).exists()]
        missing_inspections = [str(rel) for rel in inspections.values() if not (root / str(rel)).exists()]
        _add_gate(
            gates,
            f"{chapter_id}:docx-inspection",
            not docx or (not missing_docx and not missing_inspections and set(docx) <= set(inspections)),
            "blocking",
            f"{chapter_id} DOCX outputs have inspection reports or DOCX was not requested",
            f"{chapter_id} DOCX 导出缺少文件或 inspection：docx_missing={', '.join(missing_docx) or 'none'}，inspection_missing={', '.join(missing_inspections) or 'none'}。",
        )

        run_id = f"release-{chapter_id}"
        approval = _approval_record(root, run_id)
        _add_gate(
            gates,
            f"{chapter_id}:release-approval",
            str(approval.get("decision") or "") == "approve",
            "blocking",
            f"{chapter_id} release approve record exists",
            f"{chapter_id} 缺少 run_id={run_id} 的用户 approve 记录；平台 Agent 不能自批发布。",
        )

        publish_manifest = root / "releases" / chapter_id / "formal-release" / "publish_manifest.json"
        latest = root / "releases" / chapter_id / "latest.json"
        publish_payload = _read_json(publish_manifest)
        latest_payload = _read_json(latest)
        published_outputs = publish_payload.get("published_outputs") if isinstance(publish_payload.get("published_outputs"), dict) else {}
        missing_published = [str(rel) for rel in published_outputs.values() if not (root / str(rel)).exists()]
        _add_gate(
            gates,
            f"{chapter_id}:publish-release",
            publish_manifest.exists()
            and latest.exists()
            and publish_payload.get("schema") == "literary-engineering-workbench/publish-chapter/v0.1"
            and publish_payload.get("status") == "published"
            and (publish_payload.get("approval") if isinstance(publish_payload.get("approval"), dict) else {}).get("decision") == "approve"
            and latest_payload.get("manifest") == _rel(publish_manifest, root)
            and published_outputs
            and not missing_published,
            "blocking",
            f"{chapter_id} published release exists and latest points to it",
            f"{chapter_id} 发布未闭合：formal-release/latest/approval/status/outputs 有问题；missing_published={', '.join(missing_published) or 'none'}。",
        )


def _delivery_trace_hits(path: Path) -> list[str]:
    text = _read_text(path)
    patterns = {
        "scene-id": r"\bscene_\d{4}\b",
        "agent-task": r"\[AGENT_TASK:",
        "canon-note-heading": r"(?m)^#{1,4}\s*(新增事实候选|人物状态变化|关系变化|伏笔变化|需要人工确认|世界状态变化|状态变化候选)\s*$",
        "review-heading": r"(?m)^#{1,4}\s*(审查|AgentReview|Route Audit|平台 Agent 任务|门禁问题汇总)\b",
        "workflow-path": r"\b(workflow/tasks|reviews/agent|characters/state_patches|drafts/promotions|branch_manifest|roleplay_simulation)\b",
    }
    hits = []
    for label, pattern in patterns.items():
        if re.search(pattern, text):
            hits.append(label)
    return hits


def _review_needs_revision(payload: dict) -> bool:
    conclusion = str(payload.get("conclusion") or "").strip().lower()
    if conclusion in {"pass_with_notes", "revise_required", "reject"}:
        return True
    for key in ("revision_actions", "warnings", "style_notes", "blocking_issues"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            return True
    budget_status = _word_budget_adherence_status(payload)
    if budget_status not in {"", "pass", "not_required"}:
        return True
    budget = payload.get("word_budget_adherence")
    if isinstance(budget, dict) and budget_status in {"pass", "not_required"} and budget.get("narrative_load_satisfied") is False:
        return True
    return False


def _mounted_style_exists(root: Path) -> bool:
    active = root / "style" / "active_style_skill.json"
    if active.exists():
        return True
    return bool(list((root / "style" / "mounted").glob("*"))) if (root / "style" / "mounted").exists() else False


def _style_adherence_status(payload: dict) -> str:
    adherence = payload.get("style_adherence")
    if not isinstance(adherence, dict):
        return ""
    return str(adherence.get("status") or "").strip().lower()


def _word_budget_adherence_status(payload: dict) -> str:
    adherence = payload.get("word_budget_adherence")
    if not isinstance(adherence, dict):
        return ""
    return str(adherence.get("status") or "").strip().lower()


def _agent_review_canon_writeback_ok(payload: dict) -> tuple[bool, str]:
    value = payload.get("canon_writeback") if isinstance(payload, dict) else None
    if not isinstance(value, dict):
        return False, "canon_writeback object missing"
    status = str(value.get("status") or "").strip().lower()
    change = _canon_change_value(value.get("canon_change"))
    if status not in {"pass", "not_required", "pending_canon_evolve", "unknown"}:
        return False, f"status={status or 'missing'}"
    if change is False:
        reason = str(value.get("no_canon_change_reason") or "").strip()
        if not reason:
            return False, "canon_change=false requires no_canon_change_reason"
        return True, "no canon change"
    if change in {True, "unknown"}:
        return True, "canon-evolve required or pending"
    return False, "canon_change must be true, false, or unknown"


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


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _summary(records: list[AgentTaskRecord]) -> dict[str, int]:
    return {
        "task_count": len(records),
        "pending_count": sum(1 for record in records if record.status == "pending"),
        "partial_count": sum(1 for record in records if record.status == "partial"),
        "complete_count": sum(1 for record in records if record.status == "complete"),
        "unknown_count": sum(1 for record in records if record.status == "unknown"),
        "missing_expected_count": sum(len(record.missing_expected_paths) for record in records),
        "missing_source_count": sum(len(record.missing_source_paths) for record in records),
    }


def _render_status_markdown(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        "# 平台 Agent 任务总控面板",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 任务数：{summary['task_count']}",
        f"- Pending：{summary['pending_count']}",
        f"- Partial：{summary['partial_count']}",
        f"- Complete：{summary['complete_count']}",
        f"- Unknown：{summary['unknown_count']}",
        f"- 缺失预期产物：{summary['missing_expected_count']}",
        "",
        "## Sidecars",
        "",
        "| 状态 | Route | Task | 缺失预期产物 | 缺失 Source |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for record in payload["tasks"]:
        lines.append(
            f"| {record['status']} | {record['route']} | `{record['path']}` | {len(record['missing_expected_paths'])} | {len(record['missing_source_paths'])} |"
        )
    lines.extend(["", "## 下一步", "", "- 先处理 pending / partial sidecar，再进入生成、审查、装配或发布。"])
    return "\n".join(lines).rstrip() + "\n"


def _render_route_audit_markdown(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        f"# Route Audit：{summary['route']}",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- Gate 数：{summary['gate_count']}",
        f"- Blocking：{summary['blocking_count']}",
        f"- Warning：{summary['warning_count']}",
        f"- 等待前序门禁：{summary.get('waiting_count', 0)}",
        f"- 未完成 sidecar：{summary['pending_task_count']}",
        "",
        "## Gates",
        "",
        "| 状态 | 级别 | Gate | 说明 |",
        "| --- | --- | --- | --- |",
    ]
    scene_scope = summary.get("scene_scope") if isinstance(summary.get("scene_scope"), dict) else {}
    if scene_scope:
        lines[7:7] = [
            f"- 场景审计范围：已开始 {scene_scope.get('started_scene_count', 0)} / 总数 {scene_scope.get('total_scene_count', 0)}；未开始计划场景 {scene_scope.get('planned_scene_count', 0)} 不计为失败。",
        ]
    for gate in payload["gates"]:
        lines.append(f"| {gate['status']} | {gate['severity']} | {gate['key']} | {gate['message']} |")
    lines.extend(["", "## Sidecar Summary", "", "| 状态 | Route | Task |", "| --- | --- | --- |"])
    for record in payload["tasks"]:
        lines.append(f"| {record['status']} | {record['route']} | `{record['path']}` |")
    return "\n".join(lines).rstrip() + "\n"


def _normalize_route(route: str) -> str:
    return route.strip().lower().replace("_", "-")


def _resolve_output(root: Path, output: Path | None, *default_parts: str) -> Path:
    if output is None:
        return root.joinpath(*default_parts)
    return output if output.is_absolute() else root / output


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _unique(items: list[str]) -> list[str]:
    seen = set()
    results = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        results.append(item)
    return results


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
