"""Exact semantic artifact projection for the Studio Worker program."""

from __future__ import annotations

import json
from typing import Any

from ..contracts import TaskPackage
from literary_engineering_studio_engine.prompting.agents.schema import load_schema_spec
from literary_engineering_studio_engine.literary.scene.branching.proposals import (
    branch_proposal_contract,
)


def semantic_output_contract(task: TaskPackage) -> dict[str, Any]:
    """Project the exact semantic JSON contract into the sandbox task package."""

    current_state = str(task.current_state or task.payload.get("current_state") or "")
    scene_id = str(task.payload.get("scene_id") or "").strip()
    revision = _scene_revision_output_contract(task, current_state, scene_id)
    if revision:
        return revision
    candidate = _scene_candidate_output_contract(task, current_state, scene_id)
    if candidate:
        return candidate
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
    template = _load_template(task, semantic)
    locked = _locked_values(template)
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
    if current_state == "branch-agent-task":
        proposals = template.get("proposals")
        proposal_count = len(proposals) if isinstance(proposals, list) else 0
        contract["branch_proposal_contract"] = branch_proposal_contract(proposal_count)
    return contract


def _scene_revision_output_contract(
    task: TaskPackage,
    current_state: str,
    scene_id: str,
) -> dict[str, Any]:
    """Separate revision judgments from exact-source transport metadata."""

    if current_state not in {"candidate-revision", "static-revision"}:
        return {}
    path = next(
        (
            item
            for item in task.expected_outputs
            if item.endswith("_revision.json")
        ),
        "",
    )
    if not path:
        return {}
    required_fields = [
        "revision_actions_applied",
        "warnings_addressed",
        "style_notes_addressed",
        "style_adherence_addressed",
        "anti_evasion_rows",
        "retained_transition_proofs",
        "evasion_risks_unresolved",
        "new_character_register",
        "waivers",
    ]
    model_fields = [*required_fields, "anti_evasion_not_applicable_reason"]
    return {
        "path": path,
        "schema_name": "scene-revision/v1",
        "revision_kind": "exact-source",
        "required_fields": required_fields,
        "field_types": {
            "revision_actions_applied": "list",
            "warnings_addressed": "list",
            "style_notes_addressed": "list",
            "style_adherence_addressed": "list",
            "anti_evasion_rows": "list",
            "anti_evasion_not_applicable_reason": "str",
            "retained_transition_proofs": "list",
            "evasion_risks_unresolved": "list",
            "new_character_register": "dict",
            "waivers": "list",
        },
        "object_shapes": {
            "anti_evasion_rows[]": {
                "source_excerpt": "exact excerpt present in revision_source",
                "issue": "specific review or lint defect",
                "revised_excerpt": "exact excerpt present in the revised candidate",
                "still_uses_explicit_transition": "bool",
                "suspected_rephrase": "bool",
                "critical_objection": "critical attempt to disprove the repair",
                "verdict": "resolved | retained_with_proof",
            },
            "new_character_register": {
                "schema": "literary-engineering-workbench/new-character-register/v0.1",
                "status": "none | existing_only | ephemeral_only | candidates_ready | resolved",
                "introduced": "list",
                "ephemeral_waivers": "list",
                "blocking_issues": "list; must be empty for a clean revision",
            },
        },
        "model_owned_fields": model_fields,
        "studio_owned_fields": [
            "schema",
            "scene_id",
            "source_candidate",
            "source_candidate_sha256",
            "candidate",
            "candidate_sha256",
            "report",
            "source_paths",
            "prompt_manifest",
            "style_mount_snapshot",
            "creative_quality_profile_digest",
            "reader_experience_contract",
            "narrative_rhythm_contract",
            "anti_evasion_protocol_applied",
            "ready_for_review",
            "generated_by",
            "provider",
            "formal_contract_revision",
            "writer_session_id",
        ],
        "locked_values": {"scene_id": scene_id},
    }


def _scene_candidate_output_contract(
    task: TaskPackage,
    current_state: str,
    scene_id: str,
) -> dict[str, Any]:
    """Expose only the literary judgments the prose Worker must author.

    Candidate identity, paths, profile digests and session provenance are
    deterministic Studio facts.  Keeping them out of the Agent-owned shape
    prevents the model from spending a prose turn guessing transport fields.
    """

    if current_state not in {"candidate-generation-provenance", "generation-agent-task"}:
        return {}
    path = next(
        (
            item
            for item in task.expected_outputs
            if item.endswith(".json")
            and not item.endswith(".prompt.json")
            and not item.endswith(".agent_completion.json")
        ),
        "",
    )
    if not path:
        return {}
    return {
        "path": path,
        "schema_name": "scene-candidate/v1",
        "required_fields": [
            "word_budget_standard_applied",
            "pass_with_notes_actions_applied",
            "canon_writeback",
            "new_character_register",
        ],
        "field_types": {
            "word_budget_standard_applied": "bool",
            "pass_with_notes_actions_applied": "bool",
            "canon_writeback": "dict",
            "new_character_register": "dict",
        },
        "object_shapes": {
            "canon_writeback": {
                "canon_change": "true | false | unknown",
                "no_canon_change_reason": "required non-empty str when canon_change=false",
                "candidate_patch": "optional project-relative str",
            },
            "new_character_register": {
                "schema": "literary-engineering-workbench/new-character-register/v0.1",
                "status": "none | existing_only | ephemeral_only | candidates_ready | resolved",
                "introduced": "list",
                "ephemeral_waivers": "list",
                "blocking_issues": "list; must be empty for a clean generation result",
            },
        },
        "model_owned_fields": [
            "word_budget_standard_applied",
            "pass_with_notes_actions_applied",
            "canon_writeback",
            "new_character_register",
        ],
        "studio_owned_fields": [
            "schema",
            "scene_id",
            "candidate",
            "prompt_manifest",
            "generated_by",
            "provider",
            "formal_contract_revision",
            "writer_session_id",
            "style_mount_snapshot",
            "creative_quality_profile_digest",
            "reader_experience_contract",
            "narrative_rhythm_contract",
            "style_generation_standard_applied",
            "hard_constraints_applied",
            "anti_evasion_protocol_applied",
            "narrative_rhythm_standard_applied",
        ],
        "locked_values": {"scene_id": scene_id},
    }


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
    return f"""

只填写修订中真实发生的文学判断，不得猜测 schema、路径、SHA-256、会话或受保护标准；这些字段由 Studio 在提交前绑定。

- `revision_actions_applied`、`warnings_addressed`、`style_notes_addressed`、`style_adherence_addressed` 分别记录已实际落实到正文的审查项；四组中至少一组非空。
- 不适用的组写空数组；无法落实的项目写入 `waivers`，不能谎报为已完成。
- `evasion_risks_unresolved` 必须为空才能进入复审；若仍有风险，保留具体条目并让任务继续阻塞。
- `anti_evasion_rows` 每项必须使用以下形状，两个 excerpt 都必须逐字存在于精确源正文或修订候选正文：

```json
{rendered}
```

- 源正文存在机械对照或换皮转折风险时，`anti_evasion_rows` 不得为空；确实不存在时才填写具体的 `anti_evasion_not_applicable_reason`。
- 保留显式转折时使用 `verdict=retained_with_proof`，并在 `retained_transition_proofs` 中给出经批判性反驳仍成立的场景功能证据。
- `new_character_register` 必须基于修订正文实际出现的人物填写；不得因 Studio 会补机器字段而省略文学判断。
"""


def _branch_proposal_guidance(contract: dict[str, Any]) -> str:
    count = int(contract.get("proposal_count") or 0)
    shape = contract.get("proposal_shape") if isinstance(contract.get("proposal_shape"), dict) else {}
    rendered = json.dumps(shape, ensure_ascii=False, indent=2)
    count_rule = f"恰好 {count} 条" if count else "`branch_manifest.json` 的 `branch_count` 所声明的精确数量"
    return f"""

`proposals` 必须保留并完成 {count_rule}场景特定提案。下面是唯一权威的单条机械形状；复制形状可以，复制占位内容不可以：

```json
{rendered}
```

- 不得把字段改名为 `id`、`rationale`、`irreversible_cost`、`next_scene_pressure` 或其他近义词。
- `state_writeback` 保留 `new_facts`、`character_changes`、`relationship_changes`、`foreshadowing_changes`、`next_scene_inputs` 五个字符串列表；至少一个列表必须有具体变化。
- 每条提案通常使用模板中的 2 个 beat；只有因果转向无法在两拍中清楚表达时才增加第 3 拍，不要为了显得完整而扩写。每拍填写全部字段，`serves` 必须是义务名称列表且可以同时承担多项义务。
- 每条提案的全部 beat 合计覆盖 `incoming_bridge`、`goal`、`turn`、`cost`、`reader_effect`、`outgoing_hook`。
- 顶层设置 `status=complete`，`evidence_paths` 与 `findings` 非空；所有 `<replace: ...>` 和 `agent_branch_replace_*` 占位值必须被替换。
- 同时完成任务声明的 `branch_selection.md`，其中 `selected_branch` 必须精确引用本文件的一条 `branch_id`；不要自行创建 completion receipt。
"""


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
