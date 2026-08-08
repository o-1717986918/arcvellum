"""Readable, security-bounded projection of executable task packages."""

from __future__ import annotations

from pathlib import Path

from ..prompt_registry import resolve_prompt_asset


OPERATING_REFERENCE_PATHS = {
    "SKILL.md",
    "AGENTS.md",
    "agentread.yaml",
    "references/agent-run-protocol.md",
    "references/cli-run-protocol.md",
    "references/artifact-contracts.md",
    "references/workflows.md",
}
AGENT_OUTPUT_CONTRACT = (
    "Only create the files listed under Allowed Outputs / Expected Outputs for this task. "
    "Studio owns CLI-protected prompt sidecars, lifecycle receipts, and other system-managed files; "
    "do not create, complete, or replace them."
)


def render_task_markdown(
    task: dict[str, object],
    root: Path,
    *,
    completion_path: Path,
) -> str:
    """Render an executable task without exposing unstaged project context."""

    human_required = str(task.get("execution_policy") or "") == "human-required"
    agent_sources = [str(item) for item in task.get("agent_source_paths") or []]
    sections = [
        _header(task, root, completion_path, human_required),
        _required_reading(task, agent_sources),
        _sources(task, agent_sources),
        _command(task, human_required),
        _constraints(task),
        _outputs(task, human_required),
        _validation(task),
        _execution(task, human_required),
    ]
    lines = [line for section in sections for line in section]
    return "\n".join(lines).rstrip() + "\n"


def _header(
    task: dict[str, object],
    root: Path,
    completion_path: Path,
    human_required: bool,
) -> list[str]:
    task_id = str(task.get("task_id") or "")
    lines = [
        f"# CLI 中介平台 Agent 任务：{task_id}",
        "",
        (
            "本文件由 `task-next` / `task-open` 生成，代表一个需要明确记录的用户决策边界。"
            if human_required
            else "本文件由 `task-next` / `task-open` 生成，代表一个正式项目操作任务。"
        ),
        (
            "请在 Studio 决策界面记录选择；此任务不要求 Agent 创建文件，也不允许 Agent 替用户做出选择。"
            if human_required
            else "用户可以继续与平台 Agent 自然对话；但本任务涉及的正式产物必须通过 CLI 提交和完成。"
        ),
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
    ]
    if not human_required:
        receipt = _relative_to_root(completion_path, root)
        lines.append(
            f"- lifecycle_receipt: `{receipt}` (由 Studio Worker 在预检通过后写入)"
        )
    lines.extend(["", *prompt_asset_lines(str(task.get("prompt_asset_id") or ""), studio_worker=True)])
    return lines


def _required_reading(
    task: dict[str, object],
    agent_sources: list[str],
) -> list[str]:
    reading = [str(item) for item in task.get("required_reading") or []]
    if agent_sources:
        reading = [item for item in reading if item not in OPERATING_REFERENCE_PATHS]
    return ["", "## Required Reading", "", *(f"- `{item}`" for item in reading)] if reading else []


def _sources(task: dict[str, object], agent_sources: list[str]) -> list[str]:
    source_paths = agent_sources or [str(item) for item in task.get("source_paths") or []]
    heading = "## Agent Source Artifacts" if agent_sources else "## Source Artifacts"
    lines = ["", heading, ""]
    lines.extend((f"- `{item}`" for item in source_paths) if source_paths else ["- 无。"])
    if agent_sources:
        lines.extend(
            [
                "",
                "## Source Boundary",
                "",
                "上列是平台 Agent 唯一需要阅读的项目资料。`source_paths` 中其余项目仅供 CLI/Studio Worker 复现确定性门禁；不得遍历目录、搜索项目或读取未列路径。",
            ]
        )
    return lines


def _command(task: dict[str, object], human_required: bool) -> list[str]:
    command = str(task.get("command") or "").strip()
    lines = ["", "## Command", ""]
    if human_required:
        lines.append("- No command. Record the offered decision through the Studio interface.")
    elif command:
        lines.extend(["```powershell", command, "```"])
    else:
        lines.append("- 本任务主要由平台 Agent 读取 source artifacts 后写出判断或创作产物。")
    return lines


def _constraints(task: dict[str, object]) -> list[str]:
    lines = ["", "## Hard Constraints", ""]
    lines.extend(f"- {item}" for item in task.get("hard_constraints") or [])
    style = list(task.get("style_constraints") or [])
    if style:
        lines.extend(["", "## Style Constraints", ""])
        lines.extend(f"- {item}" for item in style)
    return lines


def _outputs(task: dict[str, object], human_required: bool) -> list[str]:
    lifecycle, semantic = _system_metadata(task)
    receipts = lifecycle.get("completion_receipts") if isinstance(lifecycle.get("completion_receipts"), list) else []
    receipt_paths, agent_outputs = _output_facts(task, receipts)
    lines = _expected_output_section(agent_outputs, human_required)
    lines.extend(_receipt_section(receipt_paths))
    lines.extend(_protected_output_section(task))
    lines.extend(_system_metadata_section(lifecycle, semantic, receipts))
    return lines


def _output_facts(
    task: dict[str, object],
    receipts: list[object],
) -> tuple[set[str], list[str]]:
    receipt_paths = {
        str(item.get("path") or "")
        for item in receipts
        if isinstance(item, dict) and str(item.get("path") or "").strip()
    }
    core_managed = {str(item) for item in task.get("core_managed_outputs") or []}
    expected = [str(item) for item in task.get("expected_outputs") or []]
    agent_outputs = [item for item in expected if item not in receipt_paths and item not in core_managed]
    return receipt_paths, agent_outputs


def _expected_output_section(
    agent_outputs: list[str],
    human_required: bool,
) -> list[str]:
    lines = ["", "## Expected Outputs", ""]
    if agent_outputs:
        lines.extend(f"- 创建或覆盖 `{item}`" for item in agent_outputs)
    elif human_required:
        lines.append("- No file output. Studio records the decision as formal evidence.")
    else:
        lines.append("- 本任务没有固定文件输出；完成前仍需通过 `task-submit` 记录证据。")
    return lines


def _system_metadata(task: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    system_owned = task.get("system_owned_fields")
    if not isinstance(system_owned, dict):
        return {}, {}
    lifecycle = system_owned.get("lifecycle")
    semantic = system_owned.get("semantic")
    return (
        lifecycle if isinstance(lifecycle, dict) else {},
        semantic if isinstance(semantic, dict) else {},
    )


def _receipt_section(receipt_paths: set[str]) -> list[str]:
    if not receipt_paths:
        return []
    return [
        "",
        "## Studio Lifecycle Receipt",
        "",
        "下列回执由 Studio Worker 在 Agent 产物通过确定性预检后自动写入。它们不是 Agent 的创作或审查输出。",
        *(f"- 自动写入 `{item}`" for item in sorted(receipt_paths)),
    ]


def _protected_output_section(task: dict[str, object]) -> list[str]:
    outputs = [str(item) for item in task.get("core_managed_outputs") or []]
    if not outputs:
        return []
    return [
        "",
        "## CLI Protected Outputs",
        "",
        "以下文件由 Studio Worker 或本任务的 CLI Command 维护。平台 Agent 必须读取它们，但不得创建、覆盖、删除或用手写版本替代它们。",
        *(f"- 只读 `{item}`" for item in outputs),
    ]


def _system_metadata_section(
    lifecycle: dict[str, object],
    semantic: dict[str, object],
    receipts: list[object],
) -> list[str]:
    if not lifecycle and not semantic:
        return []
    lines = [
        "",
        "## System-Owned Metadata",
        "",
        "下列身份、路径、schema、摘要和完成状态由 Studio Worker 写入。Agent 只能提交创作判断与证据，不得自行发明或改写这些值。",
    ]
    lines.extend(
        f"- completion: `{item.get('path', '')}` -> `{item.get('status', '')}`"
        for item in receipts
        if isinstance(item, dict)
    )
    if semantic:
        lines.append(
            f"- semantic: `{semantic.get('path', '')}` / `{semantic.get('schema_name', '')}` / scene `{semantic.get('scene_id', '')}`"
        )
    return lines


def _validation(task: dict[str, object]) -> list[str]:
    lines = ["", "## Validation Gates", ""]
    lines.extend(f"- {item}" for item in task.get("validation_gates") or [])
    lines.extend(["", "## Forbidden Shortcuts", ""])
    lines.extend(f"- {item}" for item in task.get("forbidden_shortcuts") or [])
    return lines


def _execution(task: dict[str, object], human_required: bool) -> list[str]:
    if human_required:
        return [
            "",
            "## Human Decision Boundary",
            "",
            "This is a recorded human decision, not an Agent execution task. Do not create, revise, submit, or complete files from this task package.",
            "Record exactly one offered option through the Studio decision interface. The recorded choice must retain the task target and exact candidate SHA-256. Then request the next task again.",
            "",
        ]
    return [
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


def prompt_asset_lines(prompt_asset_id: str, *, studio_worker: bool = False) -> list[str]:
    """Return a readable prompt-asset projection for the task sidecar."""

    lines = ["## Prompt Asset", ""]
    if not prompt_asset_id:
        return [*lines, "- missing prompt_asset_id"]
    try:
        preview = resolve_prompt_asset(prompt_asset_id)
    except FileNotFoundError as exc:
        return [*lines, f"- registry_error: `{exc}`"]
    if preview.asset is None:
        return [
            *lines,
            f"- requested_id: `{prompt_asset_id}`",
            "- status: `missing`",
            "- action: run `prompt-registry-validate` before treating this task package as complete.",
        ]
    return [*lines, *_resolved_prompt_asset_lines(prompt_asset_id, preview.asset, studio_worker)]


def _resolved_prompt_asset_lines(prompt_id: str, asset, studio_worker: bool) -> list[str]:
    lines = [
        f"- requested_id: `{prompt_id}`",
        f"- resolved_id: `{asset.prompt_asset_id}`",
        f"- match: `{asset.match}`",
        f"- version: `{asset.version}`",
        f"- title: {asset.title}",
    ]
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
    return [*lines, "", "### Prompt Body", "", asset.body.strip()]


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
