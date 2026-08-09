"""Exact semantic artifact projection for the Studio Worker program."""

from __future__ import annotations

import json
from typing import Any

from ..contracts import TaskPackage
from literary_engineering_studio_engine.prompting.agents.schema import load_schema_spec


def semantic_output_contract(task: TaskPackage) -> dict[str, Any]:
    """Project the exact semantic JSON contract into the sandbox task package."""

    current_state = str(task.current_state or task.payload.get("current_state") or "")
    scene_id = str(task.payload.get("scene_id") or "").strip()
    continuity = _continuity_ledger_output_contract(current_state, scene_id)
    if continuity:
        return continuity

    semantic = task.semantic_artifact
    schema_name = str(semantic.get("schema_name") or "").strip()
    if not schema_name:
        return {}
    schema = _load_schema(schema_name)
    if schema is None:
        return {"path": str(semantic.get("path") or ""), "schema_name": schema_name}
    locked = _locked_values(_load_template(task, semantic))
    contract: dict[str, Any] = {
        "path": str(semantic.get("path") or ""),
        "schema_name": schema_name,
        "required_fields": list(schema.get("required") or []),
        "field_types": dict(schema.get("types") or {}),
        "allowed_values": dict(schema.get("enums") or {}),
        "locked_values": locked,
        "current_state": current_state,
    }
    contract.update(_state_requirements(current_state, scene_id, locked))
    return contract


def _load_schema(schema_name: str) -> dict[str, Any] | None:
    try:
        return load_schema_spec(schema_name)
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError):
        return None


def _load_template(task: TaskPackage, semantic: dict[str, str]) -> dict[str, Any]:
    path = task.project_root / str(semantic.get("path") or "")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _locked_values(template: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "schema", "scene_id", "source_artifact", "composition_sha256",
        "state_patch_sha256", "canon_patch_sha256",
    )
    return {
        field: template[field]
        for field in fields
        if field in template and template[field] not in {"", None}
    }


def _state_requirements(
    current_state: str,
    scene_id: str,
    locked: dict[str, Any],
) -> dict[str, Any]:
    if current_state == "composition-agent-task":
        composition = f"drafts/compositions/{scene_id}_composition.json"
        return {"pass_requirements": {
            "status": "complete",
            "verdict": "pass",
            "ready_for_generation": True,
            "required_changes": [],
            "evidence_paths": [composition, f"drafts/compositions/{scene_id}_composition.md"],
            "findings": "A non-empty list of concrete checked conditions; record positive validation when no defect remains.",
        }, "revision_requirements": {
            "status": "needs_revision",
            "verdict": "revise_required",
            "ready_for_generation": False,
            "required_changes": "A non-empty list of concrete changes required before a new review.",
        }}
    if current_state in {"state-agent-task", "canon-agent-task"}:
        source_label = "state patch" if current_state == "state-agent-task" else "Canon patch"
        return {"pass_requirements": {
            "status": "complete",
            "verdict": "pass",
            "approval_recommendation": "approve",
            "required_changes": [],
            "evidence_paths": [str(locked.get("source_artifact") or "")],
            "findings": (
                f"A non-empty list of concrete evidence-backed checks showing why the {source_label} "
                "is safe to send to its separate approval boundary."
            ),
        }, "revision_requirements": {
            "status": "needs_revision",
            "verdict": "revise_required",
            "approval_recommendation": "hold",
            "required_changes": "A non-empty list of concrete changes required before a new review.",
        }}
    return {}


def _continuity_ledger_output_contract(current_state: str, scene_id: str) -> dict[str, Any]:
    if not scene_id:
        return {}
    if current_state == "continuity-ledger-agent-task":
        return {
            "path": f"plot/ledger_deltas/{scene_id}.json",
            "schema_name": "continuity-ledger-delta/v1",
            "required_fields": [
                "schema", "status", "scene_id", "source_draft", "source_draft_sha256",
                "writer_session_id", "evidence_paths", "reader_question_changes",
                "promise_changes", "no_change_reason",
            ],
            "field_types": {
                "evidence_paths": "list",
                "reader_question_changes": "list",
                "promise_changes": "list",
                "no_change_reason": "str",
            },
            "allowed_values": {"status": ["complete"]},
            "locked_values": {
                "schema": "literary-engineering-workbench/continuity-ledger-delta/v1",
                "scene_id": scene_id,
                "source_draft": f"drafts/scenes/{scene_id}.md",
            },
            "continuity_kind": "delta",
        }
    if current_state == "continuity-ledger-review":
        return {
            "path": f"reviews/continuity/{scene_id}_ledger_review.json",
            "schema_name": "continuity-ledger-review/v1",
            "required_fields": [
                "schema", "status", "scene_id", "delta_path", "delta_sha256",
                "writer_session_id", "reviewer_session_id", "verdict", "findings",
                "required_changes",
            ],
            "field_types": {"findings": "list", "required_changes": "list"},
            "allowed_values": {"status": ["complete"], "verdict": ["pass"]},
            "locked_values": {
                "schema": "literary-engineering-workbench/continuity-ledger-review/v1",
                "scene_id": scene_id,
                "delta_path": f"plot/ledger_deltas/{scene_id}.json",
            },
            "continuity_kind": "review",
        }
    return {}


def render_semantic_output_contract(contract: dict[str, Any]) -> str:
    if not contract:
        return "若声明语义成果，先完成真实判断；不得把 pending 模板或 completion receipt 当作正式结论。"
    base = _render_contract_base(contract)
    continuity = _continuity_guidance(str(contract.get("continuity_kind") or ""))
    if continuity:
        return base + continuity
    return base + _requirements_guidance(contract)


def _render_contract_base(contract: dict[str, Any]) -> str:
    path = str(contract.get("path") or "")
    required = ", ".join(f"`{item}`" for item in contract.get("required_fields") or []) or "无"
    allowed = contract.get("allowed_values") if isinstance(contract.get("allowed_values"), dict) else {}
    allowed_lines = "\n".join(
        f"- `{field}` 只能取：" + "、".join(f"`{value}`" for value in values)
        for field, values in allowed.items()
        if isinstance(values, list)
    ) or "- 无枚举字段"
    locked = contract.get("locked_values") if isinstance(contract.get("locked_values"), dict) else {}
    locked_lines = "\n".join(f"- `{field}`：`{value}`" for field, value in locked.items()) or "- 无预填机器值"
    return f"""该 JSON 当前是故意设置的 pending 初始模板，不能原样保留。必须使用 edit 工具完成 `{path}`，而不是只在聊天中说明审查结果。

必填字段：{required}

允许值：
{allowed_lines}

以下机器值必须保留，不得自行改写：
{locked_lines}"""


def _continuity_guidance(kind: str) -> str:
    if kind == "delta":
        return """

这不是可选记录，初始化的 `pending_agent_judgment` 不能原样提交。完成判断后必须设为 `status=complete`。

- 存在新建、更新、延期、兑现、反转或关闭的读者问题/承诺时：两个 changes 列表按实际填写，每条都必须来自已晋升正文，并在 `evidence_paths` 中引用正文路径。
- 确实没有任何账本变化时：两个 changes 列表保持空数组，并写出具体的 `no_change_reason`，说明正文为什么没有产生新的读者责任。
- `source_draft_sha256` 与 `writer_session_id` 由 Studio 绑定到本次任务；不要编造或以 completion receipt 代替正文判断。
- 只编辑 delta，不要编辑 `plot/reader_questions/ledger.json` 或 `plot/promises/ledger.json`。
"""
    if kind == "review":
        return """

这是一份独立复核，不是对模板的确认。核对 delta 的每一项是否有已晋升正文证据、是否重复旧问题、是否给出了合理的未来兑现窗口。

- 审查通过时：`status=complete`、`verdict=pass`、`findings` 非空、`required_changes=[]`。
- 发现问题时：不能伪造 pass；写出可执行的 `required_changes`，等待原作者重新提交 delta。
- `writer_session_id`、`reviewer_session_id` 和 delta 摘要由 Studio 绑定；不要自行创建 completion receipt，也不要编辑正式账本。
"""
    return ""


def _requirements_guidance(contract: dict[str, Any]) -> str:
    pass_requirements = contract.get("pass_requirements") if isinstance(contract.get("pass_requirements"), dict) else {}
    revision_requirements = contract.get("revision_requirements") if isinstance(contract.get("revision_requirements"), dict) else {}
    if not pass_requirements:
        return ""
    pass_lines = _pass_requirement_lines(pass_requirements)
    revision_lines = _revision_requirement_lines(revision_requirements)
    return f"""

若审查确认可进入下一步，必须同时写入：
{chr(10).join(pass_lines)}

若确有实质问题，不得伪造 pass；使用 {'、'.join(revision_lines)}，并写出可执行的 `required_changes`。"""


def _pass_requirement_lines(pass_requirements: dict[str, Any]) -> list[str]:
    pass_lines = [
        f"- `status`: `{pass_requirements['status']}`",
        f"- `verdict`: `{pass_requirements['verdict']}`",
    ]
    if "ready_for_generation" in pass_requirements:
        pass_lines.append("- `ready_for_generation`: `true`")
    if "approval_recommendation" in pass_requirements:
        pass_lines.append(f"- `approval_recommendation`: `{pass_requirements['approval_recommendation']}`")
    evidence_paths = pass_requirements.get("evidence_paths") or []
    if evidence_paths and evidence_paths[0]:
        pass_lines.append(f"- `evidence_paths`: 至少保留可读的证据路径，例如 `{evidence_paths[0]}`")
    pass_lines.extend(
        [
            f"- `findings`: {pass_requirements['findings']}",
            "- `required_changes`: `[]`",
        ]
    )
    return pass_lines


def _revision_requirement_lines(
    revision_requirements: dict[str, Any],
) -> list[str]:
    revision_lines = [
        f"`status={revision_requirements.get('status')}`",
        f"`verdict={revision_requirements.get('verdict')}`",
    ]
    if "ready_for_generation" in revision_requirements:
        revision_lines.append("`ready_for_generation=false`")
    if "approval_recommendation" in revision_requirements:
        revision_lines.append(f"`approval_recommendation={revision_requirements['approval_recommendation']}`")
    return revision_lines


__all__ = ["render_semantic_output_contract", "semantic_output_contract"]
