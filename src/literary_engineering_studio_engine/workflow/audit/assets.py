"""Character-and-world asset route audit gates."""
from __future__ import annotations

from pathlib import Path

from ...agent_tasks import agent_task_completion_status
from ...asset_workshop import ASSET_CANDIDATE_DIRS
from ...route_audit_common import _add_gate, _approval_record, _path_exists, _read_json, _rel
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
