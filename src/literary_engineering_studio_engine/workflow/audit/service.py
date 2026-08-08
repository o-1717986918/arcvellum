"""Evidence-only route audit coordinator.

This module aggregates Gate reports.  It deliberately cannot issue, submit, or
complete tasks, so observability never becomes an alternate workflow path.
"""

from __future__ import annotations

from pathlib import Path

from ...agent_task_inventory import AgentTaskRecord
from ...route_audit_assets import _add_asset_route_gates
from ...route_audit_common import _add_gate, _debug_waiver_hits
from ...route_audit_export import (
    _add_export_release_route_gates,
    _non_ready_scene_count,
    _stale_or_weak_chapter_gate_count,
    _unapplied_canon_patch_count,
    _unapplied_state_patch_count,
)
from ...route_audit_longform import _add_longform_budget_gates
from ...route_audit_review import _add_review_audit_route_gates
from ...route_audit_scene import (
    _add_scene_development_gates,
    _scene_audit_scope,
    _scene_files,
    _scene_id,
    _started_scene_ids,
    _unresolved_scene_review_count,
)


def build_route_gates(root: Path, route: str, records: list[AgentTaskRecord]) -> list[dict[str, str]]:
    gates: list[dict[str, str]] = []
    pending = _add_common_route_gates(gates, root, records)
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
        _add_gate(gates, "scene-audit-scope", True, "info", f"auditing {len(started_scenes)} started scene(s); {len(scene_files) - len(started_scenes)} planned scene(s) remain future work", "")
        for scene_path in started_scenes:
            _add_scene_development_gates(gates, root, scene_path)
        scene_pending = [record for record in pending if record.route == "scene-development"]
        _add_gate(gates, "scene-sidecars-handled", not scene_pending, "blocking", "scene-development sidecars handled", f"仍有 {len(scene_pending)} 个 scene-development sidecar 未完成。")
        unresolved_reviews = _unresolved_scene_review_count(root)
        _add_gate(gates, "scene-review-notes-resolved", unresolved_reviews == 0, "blocking", "scene review notes resolved", f"仍有 {unresolved_reviews} 个场景 review notes 未进入 revise-scene 修订闭环或缺修订报告。")
    if route == "export-and-release":
        _add_review_audit_route_gates(gates, root)
        chapter_jsons = list((root / "plot" / "chapters").glob("*.json")) if (root / "plot" / "chapters").exists() else []
        _add_gate(gates, "chapter-workspace-json", bool(chapter_jsons), "blocking", "chapter workspace JSON exists", "先运行 chapter-workspace。")
        non_ready = _non_ready_scene_count(chapter_jsons)
        _add_gate(gates, "chapter-scenes-ready", non_ready == 0 and bool(chapter_jsons), "blocking", "chapter scenes ready", f"章节中仍有 {non_ready} 个非 ready 场景。")
        stale_or_weak = _stale_or_weak_chapter_gate_count(chapter_jsons)
        _add_gate(gates, "chapter-clean-review-gates", stale_or_weak == 0 and bool(chapter_jsons), "blocking", "chapter scenes have clean formal review gates", f"章节工作台中仍有 {stale_or_weak} 个场景缺少新式 clean review/flow gate 字段或存在未解决 notes；重新运行 chapter-workspace 并修订。")
        _add_longform_budget_gates(gates, root, force=False)
        unapplied = _unapplied_state_patch_count(root)
        _add_gate(gates, "state-patches-applied-or-waived", unapplied == 0, "warning", "character state patches have apply reports or no pending patches", f"仍有 {unapplied} 个人物状态 patch 未生成 state-apply 报告；最终发布前需审批写回或记录内部预览 waiver。")
        unapplied_canon = _unapplied_canon_patch_count(root)
        _add_gate(gates, "canon-patches-applied", unapplied_canon == 0, "blocking", "canon patches have been applied to the canon ledger", f"仍有 {unapplied_canon} 个 canon patch 未进入 canon-apply 账本；最终发布前需审批并运行 canon-apply，或明确改回 no_canon_change_reason。")
        _add_export_release_route_gates(gates, root, chapter_jsons)
    return gates


def _add_common_route_gates(
    gates: list[dict[str, str]],
    root: Path,
    records: list[AgentTaskRecord],
) -> list[AgentTaskRecord]:
    pending = [record for record in records if record.status in {"pending", "partial", "unknown"}]
    missing_expected = sum(len(record.missing_expected_paths) for record in records)
    debug_waivers = _debug_waiver_hits(root)
    _add_gate(gates, "project-root", (root / "project.yaml").exists(), "blocking", "project.yaml exists", "不是标准 work project；若扫描 skill root，可忽略本项。")
    _add_gate(gates, "agent-sidecars-handled", not pending, "blocking", "all .agent_tasks.md sidecars handled", f"仍有 {len(pending)} 个 sidecar 未完整处理。")
    _add_gate(gates, "expected-artifacts-exist", missing_expected == 0, "blocking", "all expected artifacts exist", f"仍缺 {missing_expected} 个预期产物。")
    _add_gate(
        gates, "debug-waiver-flags", not debug_waivers, "blocking", "no debug waiver flags found",
        f"检测到正式 Skill 宿主禁用的调试/跳审字段：{'; '.join(debug_waivers[:8])}。不要用 allow/unreview/include-blocked 类参数跳过 review；补齐正式门禁。",
    )
    return pending


def scene_audit_scope(root: Path) -> dict[str, int]:
    return _scene_audit_scope(root)
