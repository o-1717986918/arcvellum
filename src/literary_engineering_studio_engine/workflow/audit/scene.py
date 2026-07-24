"""Scene-development audit gates and downstream waiting projection."""
from __future__ import annotations

import re
from pathlib import Path

from ...agent_schema import validate_payload
from ...agent_tasks import agent_task_completion_status
from ...anti_ai_style import style_lint_gate_message
from ...canon_evolver import canon_writeback_status
from ...candidate_promotion import candidate_generation_gate, candidate_review_gate
from ...context_broker import context_trace_status
from ...flow_gates import branch_selection_status
from ...new_character_register import new_character_register_issues
from ...narrative_rhythm import narrative_rhythm_contract, rhythm_review_status
from ...reader_experience import reader_experience_contract
from ...word_budget import scene_word_budget_contract
from ...route_audit_common import _add_gate, _read_json, _read_text
from ...route_audit_evidence import (
    _agent_review_canon_writeback_ok,
    _mounted_style_exists,
    _review_needs_revision,
    _style_adherence_status,
    _word_budget_adherence_status,
)


_SCENE_GATE_PHASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("上下文", ("context-",)),
    ("角色推演", ("roleplay-",)),
    ("分支决策", ("branch-",)),
    ("编剧准备", ("scene-word-budget-", "reader-experience-", "narrative-rhythm-", "composition-")),
    ("候选生成", ("prose-candidate", "candidate-generation-", "generation-agent-task-", "style-lint-", "candidate-word-budget")),
    ("候选审查", ("agent-review-", "candidate-review-", "revision-evasion-", "style-adherence-review")),
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
