"""Human-readable rendering for semantic output contracts."""

from __future__ import annotations

import json
from typing import Any

from literary_engineering_studio_engine.public.prompting import render_prompt_template


def render_semantic_output_contract(contract: dict[str, Any]) -> str:
    if not contract:
        return render_prompt_template("formal.semantic.default.protocol", ())
    base = _render_contract_base(contract)
    continuity = _continuity_guidance(str(contract.get("continuity_kind") or ""))
    if continuity:
        return base + continuity
    if contract.get("revision_kind") == "exact-source":
        return base + _revision_guidance(contract)
    branch = contract.get("branch_proposal_contract")
    if isinstance(branch, dict):
        return base + _branch_proposal_guidance(branch)
    return base + _requirements_guidance(contract)


def _revision_guidance(contract: dict[str, Any]) -> str:
    shapes = contract.get("object_shapes") if isinstance(contract.get("object_shapes"), dict) else {}
    row_shape = shapes.get("anti_evasion_rows[]") if isinstance(shapes.get("anti_evasion_rows[]"), dict) else {}
    rendered = json.dumps(row_shape, ensure_ascii=False, indent=2)
    return render_prompt_template("formal.semantic.revision.protocol", (
        rendered,
    ))


def _branch_proposal_guidance(contract: dict[str, Any]) -> str:
    count = int(contract.get("proposal_count") or 0)
    shape = contract.get("proposal_shape") if isinstance(contract.get("proposal_shape"), dict) else {}
    rendered = json.dumps(shape, ensure_ascii=False, indent=2)
    count_rule = f"恰好 {count} 条" if count else "`branch_manifest.json` 的 `branch_count` 所声明的精确数量"
    return render_prompt_template("formal.semantic.branch.protocol", (
        count_rule,
        rendered,
    ))


def _render_contract_base(contract: dict[str, Any]) -> str:
    path = str(contract.get("path") or "")
    required = ", ".join(f"`{item}`" for item in contract.get("required_fields") or []) or "无"
    allowed = contract.get("allowed_values") if isinstance(contract.get("allowed_values"), dict) else {}
    allowed_lines = "\n".join(
        f"- `{field}` 只能取：" + "、".join(f"`{value}`" for value in values)
        for field, values in allowed.items() if isinstance(values, list)
    ) or "- 无枚举字段"
    locked = contract.get("locked_values") if isinstance(contract.get("locked_values"), dict) else {}
    locked_lines = "\n".join(
        f"- `{field}`：`{value}`" for field, value in locked.items()
    ) or "- 无预填机器值"
    return render_prompt_template("formal.semantic.base.protocol", (
        path,
        required,
        allowed_lines,
        locked_lines,
    ))


def _continuity_guidance(kind: str) -> str:
    if kind == "delta":
        return render_prompt_template("formal.semantic.continuity-delta.protocol", ())
    if kind == "review":
        return render_prompt_template("formal.semantic.continuity-review.protocol", ())
    return ""


def _requirements_guidance(contract: dict[str, Any]) -> str:
    passed = contract.get("pass_requirements") if isinstance(contract.get("pass_requirements"), dict) else {}
    revision = contract.get("revision_requirements") if isinstance(contract.get("revision_requirements"), dict) else {}
    if not passed:
        return ""
    return render_prompt_template("formal.semantic.requirements.protocol", (
        chr(10).join(_pass_requirement_lines(passed)),
        '、'.join(_revision_requirement_lines(revision)),
    ))


def _pass_requirement_lines(requirements: dict[str, Any]) -> list[str]:
    lines = [f"- `status`: `{requirements['status']}`", f"- `verdict`: `{requirements['verdict']}`"]
    if "ready_for_generation" in requirements:
        lines.append("- `ready_for_generation`: `true`")
    if "approval_recommendation" in requirements:
        lines.append(f"- `approval_recommendation`: `{requirements['approval_recommendation']}`")
    evidence_paths = requirements.get("evidence_paths") or []
    if evidence_paths and evidence_paths[0]:
        lines.append(f"- `evidence_paths`: 至少保留可读的证据路径，例如 `{evidence_paths[0]}`")
    return [*lines, f"- `findings`: {requirements['findings']}", "- `required_changes`: `[]`"]


def _revision_requirement_lines(requirements: dict[str, Any]) -> list[str]:
    lines = [f"`status={requirements.get('status')}`", f"`verdict={requirements.get('verdict')}`"]
    if "ready_for_generation" in requirements:
        lines.append("`ready_for_generation=false`")
    if "approval_recommendation" in requirements:
        lines.append(f"`approval_recommendation={requirements['approval_recommendation']}`")
    return lines


__all__ = ["render_semantic_output_contract"]
