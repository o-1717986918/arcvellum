"""Human-readable rendering for semantic output contracts."""

from __future__ import annotations

import json
from typing import Any


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
        for field, values in allowed.items() if isinstance(values, list)
    ) or "- 无枚举字段"
    locked = contract.get("locked_values") if isinstance(contract.get("locked_values"), dict) else {}
    locked_lines = "\n".join(
        f"- `{field}`：`{value}`" for field, value in locked.items()
    ) or "- 无预填机器值"
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

- 顶层 `evidence_paths` 是证据文件路径列表；存在变化时必须包含已晋升正文路径。
- `reader_question_changes` 和 `promise_changes` 的每一条变化都必须另写非空字符串字段 `evidence`，填写来自本场正文的具体事实、原句或可核验概述。条目内部的 `evidence_paths` 不能替代 `evidence`。
- 每条开放中的读者问题必须有 `target_window`、`target_scene` 或 `responsibility`；每条开放中的承诺必须有 `due_window`、`due_scene`、`target_scene` 或 `responsibility`。
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
    passed = contract.get("pass_requirements") if isinstance(contract.get("pass_requirements"), dict) else {}
    revision = contract.get("revision_requirements") if isinstance(contract.get("revision_requirements"), dict) else {}
    if not passed:
        return ""
    return f"""

若审查确认可进入下一步，必须同时写入：
{chr(10).join(_pass_requirement_lines(passed))}

若确有实质问题，不得伪造 pass；使用 {'、'.join(_revision_requirement_lines(revision))}，并写出可执行的 `required_changes`。"""


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
