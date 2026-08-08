"""Planning and composition projections for scene-development audits."""
from __future__ import annotations

from pathlib import Path

from ...agent_tasks import agent_task_completion_status
from ...context_broker import context_trace_status
from ...flow_gates import branch_selection_status
from ...narrative_rhythm import narrative_rhythm_contract
from ...reader_experience import reader_experience_contract
from ...route_audit_common import _add_gate, _read_json, _read_text
from ...word_budget import scene_word_budget_contract


def add_scene_planning_gates(
    gates: list[dict[str, str]],
    root: Path,
    scene_path: Path,
    scene_id: str,
) -> None:
    """Project context, simulation, selection, and composition evidence."""

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
    provenance_value = composition_payload.get("formal_cli_provenance")
    composition_provenance = provenance_value if isinstance(provenance_value, dict) else {}
    flow_gate_value = composition_payload.get("flow_gate")
    flow_gate = flow_gate_value if isinstance(flow_gate_value, dict) else {}
    composition_ready = (
        composition_json.exists()
        and composition_payload.get("selection_source") == "selection"
        and flow_gate.get("ready_for_generation") is True
    )

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
    _add_roleplay_gates(gates, root, scene_id, roleplay, roleplay_task, roleplay_text)
    _add_branch_gates(
        gates,
        root,
        scene_id,
        branch_manifest,
        branch_task,
        branch_payload,
        branches,
        selection_gate,
    )
    _add_composition_gates(
        gates,
        root,
        scene_id,
        composition_json,
        composition_task,
        composition_provenance,
        composition_ready,
    )
    _add_literary_contract_gates(gates, root, scene_path, scene_id, composition_json)


def _add_roleplay_gates(
    gates: list[dict[str, str]],
    root: Path,
    scene_id: str,
    roleplay: Path,
    roleplay_task: Path,
    roleplay_text: str,
) -> None:
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
    completion = agent_task_completion_status(roleplay_task, root=root)
    _add_gate(
        gates,
        f"{scene_id}:roleplay-agent-task-complete",
        completion.get("complete") is True,
        "blocking",
        f"{scene_id} roleplay platform-agent task completed",
        f"{scene_id} 的 RP sidecar 未完成：{completion.get('message')}",
    )


def _add_branch_gates(
    gates: list[dict[str, str]],
    root: Path,
    scene_id: str,
    branch_manifest: Path,
    branch_task: Path,
    branch_payload: dict,
    branches: object,
    selection_gate: dict,
) -> None:
    _add_gate(
        gates,
        f"{scene_id}:branch-manifest",
        branch_manifest.exists() and isinstance(branches, list) and bool(branches),
        "blocking",
        f"{scene_id} branch manifest exists",
        f"{scene_id} 缺少有效 branches/{scene_id}/branch_manifest.json；正式场景开发必须运行 branch-simulate --agent。",
    )
    provenance = branch_payload.get("formal_cli_provenance")
    _add_gate(
        gates,
        f"{scene_id}:branch-cli-provenance",
        provenance.get("created_by") == "branch-simulate" if isinstance(provenance, dict) else False,
        "blocking",
        f"{scene_id} branch manifest has branch-simulate CLI provenance",
        f"{scene_id} 的 branch_manifest.json 缺少 formal_cli_provenance.created_by=branch-simulate；手写 manifest 只能作为 exploratory/debug。",
    )
    completion = agent_task_completion_status(branch_task, root=root)
    _add_gate(
        gates,
        f"{scene_id}:branch-agent-task-complete",
        completion.get("complete") is True,
        "blocking",
        f"{scene_id} branch platform-agent task completed",
        f"{scene_id} 的 branch sidecar 未完成：{completion.get('message')}",
    )
    _add_gate(
        gates,
        f"{scene_id}:branch-selection",
        selection_gate["status"] == "selected",
        "blocking",
        f"{scene_id} formal branch selection exists",
        f"{scene_id} 的 branch_selection.md 未记录 decision: selected 与 selected_branch；当前状态：{selection_gate['message']}。",
    )


def _add_composition_gates(
    gates: list[dict[str, str]],
    root: Path,
    scene_id: str,
    composition_json: Path,
    composition_task: Path,
    composition_provenance: dict,
    composition_ready: bool,
) -> None:
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
    completion = agent_task_completion_status(composition_task, root=root)
    _add_gate(
        gates,
        f"{scene_id}:composition-agent-task-complete",
        completion.get("complete") is True,
        "blocking",
        f"{scene_id} composition platform-agent task completed",
        f"{scene_id} 的 composition sidecar 未完成：{completion.get('message')}",
    )


def _add_literary_contract_gates(
    gates: list[dict[str, str]],
    root: Path,
    scene_path: Path,
    scene_id: str,
    composition_json: Path,
) -> None:
    budget_contract = scene_word_budget_contract(root, scene_path)
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
    reader_contract = reader_experience_contract(root, scene_path)
    reader_status = str(reader_contract.get("status") or "").strip().lower()
    _add_gate(
        gates,
        f"{scene_id}:reader-experience-contract",
        reader_status in {"pass", "not_required"},
        "blocking",
        f"{scene_id} reader-experience contract is ready",
        f"{scene_id} 缺少可用读者体验/章节义务硬属性：{reader_contract.get('message')}",
    )
    rhythm_contract = narrative_rhythm_contract(root, scene_path, composition_json)
    rhythm_status = str(rhythm_contract.get("status") or "")
    _add_gate(
        gates,
        f"{scene_id}:narrative-rhythm-contract",
        rhythm_status in {"pass", "defaulted"},
        "blocking",
        f"{scene_id} narrative rhythm and bridge contract is available",
        f"{scene_id} 缺少叙事节奏/场景桥接硬属性：{rhythm_contract.get('message')}",
    )
    _add_gate(
        gates,
        f"{scene_id}:narrative-rhythm-explicit",
        rhythm_status == "pass",
        "warning",
        f"{scene_id} narrative rhythm/bridge is explicit",
        f"{scene_id} 使用默认叙事节奏/场景桥接契约；建议在 scene.yaml 或 composition 中显式填写，避免场景节奏扁平化。",
    )
