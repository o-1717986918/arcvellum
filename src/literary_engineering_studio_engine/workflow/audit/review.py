"""Project-level canon, longform, and committee audit gates."""
from __future__ import annotations

from pathlib import Path

from ...agent_schema import validate_payload
from ...agent_tasks import agent_task_completion_status
from ...literary.review.longform_contract import longform_audit_gate_errors
from ...route_audit_common import _add_gate, _read_json
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
    longform_errors = longform_audit_gate_errors(root, longform_payload, require_clean=True)
    _add_gate(
        gates,
        "review:longform-audit",
        _longform_artifacts_clean(root, longform, longform_errors),
        "blocking",
        "longform audit and graph exist",
        "长篇审计缺失、过期或仍有确定性阻塞：" + ("；".join(longform_errors[:4]) or "检查审计产物与图谱。"),
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


def _longform_artifacts_clean(root: Path, json_path: Path, errors: list[str]) -> bool:
    return (
        json_path.exists()
        and (root / "reviews" / "longform" / "longform_audit.md").exists()
        and (root / "plot" / "longform_graph.json").exists()
        and not errors
    )
