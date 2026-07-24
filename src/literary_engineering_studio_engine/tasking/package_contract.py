"""Executable task-package contract shared by every formal route.

Route blueprints live in :mod:`task_registry`; this module deliberately owns
only the cross-route envelope, prompt projection, output policy, and readable
task rendering.  That separation lets routes evolve independently without
duplicating the formal Agent/Worker contract.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..prompt_registry import resolve_prompt_asset


TASK_CONTRACT_REVISION = "2026-07-25.24"
COMPLETION_SCHEMA = "literary-engineering-workbench/agent-task-completion/v1"
_OPERATING_REFERENCE_PATHS = {
    "SKILL.md",
    "AGENTS.md",
    "agentread.yaml",
    "references/agent-run-protocol.md",
    "references/cli-run-protocol.md",
    "references/artifact-contracts.md",
    "references/workflows.md",
}
RECHECK_REQUIRED_STATES = {
    "asset-review-pass",
    "asset-approval-revision",
    "canon-review-pass",
    "committee-pass",
}
TASK_TYPE_EXECUTION = {
    "deterministic-cli": ("deterministic", "deterministic-engine"),
    "deterministic-review": ("deterministic", "deterministic-engine"),
    "deterministic-cli-plus-platform-review": ("agent-required", "main-agent"),
    "deterministic-cli-or-repair": ("agent-required", "main-agent"),
    "manual-route-repair": ("agent-required", "main-agent"),
    "human-approval-boundary": ("human-required", "human-decision"),
    "main-platform-agent-prose": ("agent-required", "main-creative-agent"),
    "main-platform-agent-prose-revision": ("agent-required", "main-creative-agent"),
    "platform-agent-asset-creation": ("agent-required", "main-creative-agent"),
    "platform-agent-extraction": ("agent-required", "main-creative-agent"),
    "platform-agent-revision": ("agent-required", "main-creative-agent"),
    "platform-agent-style-prompt": ("agent-required", "main-creative-agent"),
    "platform-agent-asset-review": ("agent-required", "main-review-agent"),
    "platform-agent-evaluation": ("agent-required", "main-review-agent"),
    "platform-agent-judgment": ("agent-required", "main-review-agent"),
    "platform-agent-review": ("agent-required", "main-review-agent"),
    # Historical task packages can be reopened and upgraded in place.
    "deterministic-command": ("deterministic", "deterministic-engine"),
    "human-choice": ("human-required", "human-decision"),
    "platform-agent": ("agent-required", "main-agent"),
    "platform-agent-creative": ("agent-required", "main-creative-agent"),
    "platform-agent-prose": ("agent-required", "main-creative-agent"),
}

HIGH_IMPACT_OUTPUT_PREFIXES = (
    "canon/",
    "characters/",
    "drafts/scenes/",
    "manuscript/",
    "releases/",
    "state/",
)
PROMPT_METADATA_LIST_FIELDS = (
    "required_inputs",
    "optional_inputs",
    "context_groups",
    "hard_constraints",
    "style_constraints",
    "output_contract",
    "review_requirements",
    "forbidden_shortcuts",
)
AGENT_OUTPUT_CONTRACT = (
    "Only create the files listed under Allowed Outputs / Expected Outputs for this task. "
    "Studio owns CLI-protected prompt sidecars, lifecycle receipts, and other system-managed files; "
    "do not create, complete, or replace them."
)
EXPLICIT_TASK_CONTRACT_FIELDS = {
    "execution_policy",
    "agent_role",
    "human_gate",
    "runtime_capabilities_required",
    "output_contracts",
}


def task_contract_fingerprint(task: dict[str, object]) -> str:
    """Hash the executable task contract, excluding lifecycle metadata."""

    fields = {
        key: task.get(key)
        for key in (
            "schema",
            "task_contract_revision",
            "task_id",
            "route",
            "scene_id",
            "current_state",
            "task_type",
            "prompt_asset_id",
            "command",
            "required_reading",
            "source_paths",
            "agent_source_paths",
            "expected_outputs",
            "repair_targets",
            "repair_target_sha256",
            "hard_constraints",
            "style_constraints",
            "validation_gates",
            "forbidden_shortcuts",
            "execution_policy",
            "agent_role",
            "human_gate",
            "runtime_capabilities_required",
            "output_contracts",
            "semantic_artifact",
            "system_owned_fields",
            "core_managed_outputs",
            "scene_character_assets",
        )
    }
    encoded = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def enrich_task_payload(task: dict[str, object]) -> dict[str, object]:
    """Add the authoritative execution and prompt contracts to a task."""

    enriched = dict(task)
    enriched["task_contract_revision"] = TASK_CONTRACT_REVISION
    prompt_id = str(enriched.get("prompt_asset_id") or "").strip()
    if not prompt_id:
        raise ValueError("formal task is missing prompt_asset_id")
    preview = resolve_prompt_asset(prompt_id)
    if preview.asset is None:
        raise ValueError(f"formal task prompt asset is not registered: {prompt_id}")

    asset = preview.asset
    prompt_asset: dict[str, object] = {
        "requested_id": prompt_id,
        "resolved_id": asset.prompt_asset_id,
        "exact": preview.exact,
        "match": asset.match,
        "version": asset.version,
        "route": asset.route,
        "task_type": str(asset.metadata.get("task_type") or ""),
        "title": asset.title,
        "body": asset.body.strip(),
    }
    for field in PROMPT_METADATA_LIST_FIELDS:
        prompt_asset[field] = [str(item) for item in asset.metadata.get(field) or []]
    # Prompt assets are shared with the standalone Skill, where a platform
    # Agent may own a completion marker.  Inside Studio, lifecycle evidence
    # and CLI scaffolds are Worker-owned.  Project the Studio-specific output
    # boundary into every sandboxed task so the model never receives two
    # contradictory write instructions.
    prompt_asset["output_contract"] = [AGENT_OUTPUT_CONTRACT]
    enriched["prompt_asset"] = prompt_asset

    expected_outputs = [str(item) for item in enriched.get("expected_outputs") or []]
    core_managed_outputs = {str(item) for item in enriched.get("core_managed_outputs") or []}
    semantic = enriched.get("semantic_artifact") if isinstance(enriched.get("semantic_artifact"), dict) else None
    if semantic is not None:
        semantic_path = normalize_relative(str(semantic.get("path") or ""))
        if semantic_path not in expected_outputs:
            raise ValueError("semantic artifact must be declared in expected_outputs")
        if not str(semantic.get("schema_name") or "").strip() or not str(semantic.get("consumed_by") or "").strip():
            raise ValueError("semantic artifact requires schema_name and consumed_by")
        enriched["semantic_artifact"] = {
            "path": semantic_path,
            "kind": str(semantic.get("kind") or "semantic-artifact"),
            "schema_name": str(semantic["schema_name"]),
            "consumed_by": str(semantic["consumed_by"]),
            "writeback_policy": str(semantic.get("writeback_policy") or "preview-required"),
        }

    # Agents author creative reasoning, not lifecycle bookkeeping.  Keep every
    # deterministic identity/path/enum contract in the task package so the
    # Worker can materialize it after the substantive outputs exist.
    enriched["system_owned_fields"] = _merge_system_owned_fields(
        enriched.get("system_owned_fields"),
        _system_owned_fields(enriched, expected_outputs, semantic),
    )

    present_contract_fields = EXPLICIT_TASK_CONTRACT_FIELDS & set(enriched)
    if present_contract_fields == EXPLICIT_TASK_CONTRACT_FIELDS:
        if str(enriched.get("execution_policy") or "") == "human-required":
            enriched["submission_command"] = ""
            enriched["completion_command"] = ""
        return enriched
    if present_contract_fields:
        missing = ", ".join(sorted(EXPLICIT_TASK_CONTRACT_FIELDS - present_contract_fields))
        raise ValueError(f"formal task has a partial explicit execution contract; missing: {missing}")

    task_type = str(enriched.get("task_type") or "").strip()
    try:
        execution_policy, agent_role = TASK_TYPE_EXECUTION[task_type]
    except KeyError as exc:
        raise ValueError(f"formal task has no explicit execution contract for task_type: {task_type}") from exc
    human_required = execution_policy == "human-required"
    human_reasons = [str(enriched.get("current_state") or "human-decision")] if human_required else []
    if execution_policy == "deterministic":
        capabilities = ["deterministic-command"]
    elif human_required:
        capabilities = []
    else:
        capabilities = ["read-task-sources"]
        if expected_outputs:
            capabilities.append("write-expected-outputs")

    enriched.update(
        {
            "execution_policy": execution_policy,
            "agent_role": agent_role,
            "human_gate": {
                "required": human_required,
                "reasons": human_reasons,
                "source": "task-registry",
            },
            "runtime_capabilities_required": capabilities,
            "output_contracts": [
                output_contract(
                    item,
                    execution_policy,
                    core_managed=item in core_managed_outputs,
                    semantic=semantic if semantic and item == semantic["path"] else None,
                )
                for item in expected_outputs
            ],
        }
    )
    if human_required:
        enriched["submission_command"] = ""
        enriched["completion_command"] = ""
        enriched["forbidden_shortcuts"] = [
            item
            for item in enriched.get("forbidden_shortcuts") or []
            if "task-submit and task-complete" not in str(item)
        ]
        enriched["forbidden_shortcuts"].extend(
            [
                "Do not treat the Agent or a delegated runtime as the decision maker for this boundary.",
                "Do not create an agent completion marker or a substitute approval file; use the Studio decision interface.",
            ]
        )
    return enriched


def _system_owned_fields(
    task: dict[str, object],
    expected_outputs: list[str],
    semantic: dict[str, object] | None,
) -> dict[str, object]:
    """Build the cross-route machine-owned part of an Agent task contract."""

    task_id = str(task.get("task_id") or "")
    route = str(task.get("route") or "")
    state = str(task.get("current_state") or "")
    policy = TASK_TYPE_EXECUTION.get(str(task.get("task_type") or ""), ("", ""))[0]
    receipts: list[dict[str, object]] = []
    if policy == "agent-required":
        status = "recheck_required" if state in RECHECK_REQUIRED_STATES else "complete"
        checked = status == "complete"
        for item in expected_outputs:
            normalized = normalize_relative(item)
            if not normalized.endswith(".agent_completion.json"):
                continue
            base = normalized[: -len(".agent_completion.json")]
            source_task = base + (".md" if base.endswith(".agent_tasks") else ".agent_tasks.md")
            receipts.append(
                {
                    "path": normalized,
                    "schema": COMPLETION_SCHEMA,
                    "source_task": source_task,
                    "status": status,
                    "expected_artifacts_checked": checked,
                }
            )
    lifecycle: dict[str, object] = {
        "task_identity": {"task_id": task_id, "route": route, "current_state": state},
        "completion_receipts": receipts,
        "allowed_status_values": ["complete", "recheck_required"],
    }
    result: dict[str, object] = {"lifecycle": lifecycle}
    if semantic is not None:
        result["semantic"] = {
            "path": str(semantic.get("path") or ""),
            "kind": str(semantic.get("kind") or ""),
            "schema_name": str(semantic.get("schema_name") or ""),
            "scene_id": str(task.get("scene_id") or ""),
            "consumed_by": str(semantic.get("consumed_by") or ""),
            "status_values": ["complete"],
        }
    return result


def _merge_system_owned_fields(existing: object, generated: dict[str, object]) -> dict[str, object]:
    """Merge route-specific ownership with the required cross-route envelope."""

    merged = dict(existing) if isinstance(existing, dict) else {}
    for key, value in generated.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


def output_contract(
    path: str,
    execution_policy: str,
    *,
    core_managed: bool = False,
    semantic: dict[str, object] | None = None,
) -> dict[str, str]:
    """Describe ownership and writeback policy for a declared output."""

    normalized = normalize_relative(path)
    lower = normalized.lower()
    if core_managed:
        kind = "deterministic"
        policy = "automatic"
    elif lower.endswith("agent_completion.json") or ".agent_completion." in lower:
        kind = "completion-evidence"
        policy = "automatic"
    elif "approval" in lower or lower.startswith("decisions/"):
        kind = "human-approval"
        policy = "approval-required"
    elif execution_policy == "deterministic":
        kind = "deterministic"
        policy = "automatic"
    else:
        kind = "agent-authored"
        policy = "approval-required" if lower.startswith(HIGH_IMPACT_OUTPUT_PREFIXES) else "preview-required"
    result = {"path": normalized, "kind": kind, "writeback_policy": policy}
    if semantic is not None:
        result.update(
            {
                "kind": str(semantic.get("kind") or "semantic-artifact"),
                "schema_name": str(semantic.get("schema_name") or ""),
                "consumed_by": str(semantic.get("consumed_by") or ""),
            }
        )
    return result


def render_task_markdown(task: dict[str, object], root: Path, *, completion_path: Path) -> str:
    """Render the human-readable projection of an executable task contract."""

    task_id = str(task.get("task_id") or "")
    human_required = str(task.get("execution_policy") or "") == "human-required"
    agent_source_paths = list(task.get("agent_source_paths") or [])
    required_reading = [str(item) for item in task.get("required_reading") or []]
    if agent_source_paths:
        required_reading = [item for item in required_reading if item not in _OPERATING_REFERENCE_PATHS]
    lines = [
        f"# CLI 中介平台 Agent 任务：{task_id}",
        "",
        "本文件由 `task-next` / `task-open` 生成，代表一个正式项目操作任务。"
        if not human_required
        else "本文件由 `task-next` / `task-open` 生成，代表一个需要明确记录的用户决策边界。",
        "用户可以继续与平台 Agent 自然对话；但本任务涉及的正式产物必须通过 CLI 提交和完成。"
        if not human_required
        else "请在 Studio 决策界面记录选择；此任务不要求 Agent 创建文件，也不允许 Agent 替用户做出选择。",
        "",
        "## Task Metadata",
        "",
        f"- task_id: `{task_id}`",
        f"- route: `{task.get('route', '')}`",
        f"- scene_id: `{task.get('scene_id', '')}`",
        f"- current_state: `{task.get('current_state', '')}`",
        f"- task_type: `{task.get('task_type', '')}`",
        f"- prompt_asset_id: `{task.get('prompt_asset_id', '')}`",
        f"- execution_policy: `{task.get('execution_policy', '')}`",
        f"- agent_role: `{task.get('agent_role', '')}`",
        f"- context_trace: `{task.get('context_trace', '') or 'n/a'}`",
        f"- status: `{task.get('status', '')}`",
        *([] if human_required else [f"- lifecycle_receipt: `{relative_to_root(completion_path, root)}` (由 Studio Worker 在预检通过后写入)"]),
        "",
        *prompt_asset_lines(str(task.get("prompt_asset_id") or ""), studio_worker=True),
    ]
    if required_reading:
        lines.extend(["", "## Required Reading", ""])
        lines.extend(f"- `{item}`" for item in required_reading)
    source_paths = agent_source_paths or list(task.get("source_paths") or [])
    source_heading = "## Agent Source Artifacts" if agent_source_paths else "## Source Artifacts"
    lines.extend(["", source_heading, ""])
    if source_paths:
        lines.extend(f"- `{item}`" for item in source_paths)
    else:
        lines.append("- 无。")
    if agent_source_paths:
        lines.extend(
            [
                "",
                "## Source Boundary",
                "",
                "上列是平台 Agent 唯一需要阅读的项目资料。`source_paths` 中其余项目仅供 CLI/Studio Worker 复现确定性门禁；不得遍历目录、搜索项目或读取未列路径。",
            ]
        )
    lines.extend(["", "## Command", ""])
    command = str(task.get("command") or "").strip()
    if human_required:
        lines.append("- No command. Record the offered decision through the Studio interface.")
    elif command:
        lines.extend(["```powershell", command, "```"])
    else:
        lines.append("- 本任务主要由平台 Agent 读取 source artifacts 后写出判断或创作产物。")
    lines.extend(["", "## Hard Constraints", ""])
    lines.extend(f"- {item}" for item in task.get("hard_constraints") or [])
    style_constraints = list(task.get("style_constraints") or [])
    if style_constraints:
        lines.extend(["", "## Style Constraints", ""])
        lines.extend(f"- {item}" for item in style_constraints)
    system_owned = task.get("system_owned_fields")
    lifecycle = system_owned.get("lifecycle") if isinstance(system_owned, dict) and isinstance(system_owned.get("lifecycle"), dict) else {}
    receipts = lifecycle.get("completion_receipts") if isinstance(lifecycle.get("completion_receipts"), list) else []
    receipt_paths = {
        str(item.get("path") or "")
        for item in receipts
        if isinstance(item, dict) and str(item.get("path") or "").strip()
    }

    lines.extend(["", "## Expected Outputs", ""])
    expected_outputs = list(task.get("expected_outputs") or [])
    core_managed = {str(item) for item in task.get("core_managed_outputs") or []}
    agent_outputs = [
        item
        for item in expected_outputs
        if str(item) not in receipt_paths and str(item) not in core_managed
    ]
    if agent_outputs:
        lines.extend(f"- 创建或覆盖 `{item}`" for item in agent_outputs)
    elif human_required:
        lines.append("- No file output. Studio records the decision as formal evidence.")
    else:
        lines.append("- 本任务没有固定文件输出；完成前仍需通过 `task-submit` 记录证据。")
    if receipt_paths:
        lines.extend(["", "## Studio Lifecycle Receipt", ""])
        lines.append("下列回执由 Studio Worker 在 Agent 产物通过确定性预检后自动写入。它们不是 Agent 的创作或审查输出。")
        lines.extend(f"- 自动写入 `{item}`" for item in sorted(receipt_paths))
    core_managed_outputs = list(task.get("core_managed_outputs") or [])
    if core_managed_outputs:
        lines.extend(["", "## CLI Protected Outputs", ""])
        lines.append("以下文件由 Studio Worker 或本任务的 CLI Command 维护。平台 Agent 必须读取它们，但不得创建、覆盖、删除或用手写版本替代它们。")
        lines.extend(f"- 只读 `{item}`" for item in core_managed_outputs)
    if isinstance(system_owned, dict):
        semantic = system_owned.get("semantic") if isinstance(system_owned.get("semantic"), dict) else {}
        if lifecycle or semantic:
            lines.extend(["", "## System-Owned Metadata", ""])
            lines.append("下列身份、路径、schema、摘要和完成状态由 Studio Worker 写入。Agent 只能提交创作判断与证据，不得自行发明或改写这些值。")
            if receipts:
                lines.extend(
                    f"- completion: `{item.get('path', '')}` -> `{item.get('status', '')}`"
                    for item in receipts
                    if isinstance(item, dict)
                )
            if semantic:
                lines.append(
                    f"- semantic: `{semantic.get('path', '')}` / `{semantic.get('schema_name', '')}` / scene `{semantic.get('scene_id', '')}`"
                )
    lines.extend(["", "## Validation Gates", ""])
    lines.extend(f"- {item}" for item in task.get("validation_gates") or [])
    lines.extend(["", "## Forbidden Shortcuts", ""])
    lines.extend(f"- {item}" for item in task.get("forbidden_shortcuts") or [])
    if human_required:
        lines.extend(
            [
                "",
                "## Human Decision Boundary",
                "",
                "This is a recorded human decision, not an Agent execution task. Do not create, revise, submit, or complete files from this task package.",
                "Record exactly one offered option through the Studio decision interface. The recorded choice must retain the task target and exact candidate SHA-256. Then request the next task again.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Agent Execution",
                "",
                "[AGENT_TASK: 只读取本任务列出的 Required Reading（如有）和 Agent Source Artifacts（没有该节时才读取 Source Artifacts）。完成必要阅读后立即创建或覆盖 Expected Outputs；不要枚举目录、反复读取资料或等待 Studio 生命周期回执。Studio Worker 会完成预检、提交、回执与状态推进。]",
                "",
                "推荐提交命令：",
                "",
                "```powershell",
                str(task.get("submission_command") or ""),
                "```",
                "",
                "推荐完成命令：",
                "",
                "```powershell",
                str(task.get("completion_command") or ""),
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def prompt_asset_lines(prompt_asset_id: str, *, studio_worker: bool = False) -> list[str]:
    """Return a readable prompt-asset projection for the task sidecar."""

    lines = ["## Prompt Asset", ""]
    if not prompt_asset_id:
        lines.append("- missing prompt_asset_id")
        return lines
    try:
        preview = resolve_prompt_asset(prompt_asset_id)
    except FileNotFoundError as exc:
        lines.append(f"- registry_error: `{exc}`")
        return lines
    if preview.asset is None:
        lines.extend(
            [
                f"- requested_id: `{prompt_asset_id}`",
                "- status: `missing`",
                "- action: run `prompt-registry-validate` before treating this task package as complete.",
            ]
        )
        return lines
    asset = preview.asset
    lines.extend(
        [
            f"- requested_id: `{prompt_asset_id}`",
            f"- resolved_id: `{asset.prompt_asset_id}`",
            f"- match: `{asset.match}`",
            f"- version: `{asset.version}`",
            f"- title: {asset.title}",
        ]
    )
    for field, title in (
        ("required_inputs", "Required Inputs"),
        ("optional_inputs", "Optional Inputs"),
        ("context_groups", "Context Groups"),
        ("hard_constraints", "Hard Constraints"),
        ("style_constraints", "Style Constraints"),
        ("output_contract", "Output Contract"),
        ("review_requirements", "Review Requirements"),
        ("forbidden_shortcuts", "Forbidden Shortcuts"),
    ):
        values = [str(item) for item in asset.metadata.get(field) or []]
        if field == "output_contract" and studio_worker:
            values = [AGENT_OUTPUT_CONTRACT]
        if not values and field in {"optional_inputs", "style_constraints"}:
            continue
        lines.extend(["", f"### Prompt {title}", ""])
        lines.extend(f"- {item}" for item in values)
    lines.extend(["", "### Prompt Body", "", asset.body.strip()])
    return lines


def normalize_relative(value: str | Path) -> str:
    return Path(str(value)).as_posix()


def relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
