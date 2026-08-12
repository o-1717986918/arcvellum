"""Export the exact Pi Worker system and task messages for local prompt audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from literary_engineering_studio.contracts import load_task_package
from literary_engineering_studio.runtime.context_budget import resolve_task_context_budget
from literary_engineering_studio.runtime.prompt_metrics import measure_prompt
from literary_engineering_studio.runtime.sandbox import stage_task


HOST_RESIDUES = (
    "SKILL.md",
    "AGENTS.md",
    "agentread.yaml",
    "平台 Agent",
    "[AGENT_TASK",
    "task-submit",
    "task-complete",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    project = args.project.resolve()
    task_path = args.task if args.task.is_absolute() else project / args.task
    task = load_task_package(project, task_path)
    budget = resolve_task_context_budget(task, {"context_budget": {"mode": "enforced"}})
    sandbox = stage_task(
        task,
        args.runs_root,
        runtime="pi-worker",
        run_id=args.run_id,
        context_budget=budget,
        execution_profile={"runtime_id": "pi-worker"},
        prompt_program_config={
            "mode": "enforced",
            "fallback": "error",
            "enforcement": {"enabled": True, "runtimes": ["pi-worker"]},
        },
    )
    repository = Path(__file__).resolve().parents[1]
    system_source = repository / "workers/pi-worker/profiles/main-creative-agent.md"
    system_message = system_source.read_text(encoding="utf-8").strip()
    task_message = sandbox.prompt_path.read_text(encoding="utf-8").strip()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    system_path = output / "pi-worker-main-creative-system-prompt.md"
    task_output = output / "scene-prose-fixed-full-prompt.md"
    effective_path = output / "scene-prose-fixed-effective-messages.md"
    system_path.write_text(system_message + "\n", encoding="utf-8")
    task_output.write_text(task_message + "\n", encoding="utf-8")
    effective_path.write_text(
        "# ArcVellum Pi Worker 有效消息审计\n\n"
        "以下两段分别作为 System message 与 User message 发送；本文件仅用于本地审计。\n\n"
        "## System message\n\n"
        + system_message
        + "\n\n## User message\n\n"
        + task_message
        + "\n",
        encoding="utf-8",
    )
    metrics = measure_prompt(task_message)
    report = {
        "schema": "arcvellum/pi-prompt-audit/v1",
        "task_id": task.task_id,
        "system_prompt": system_path.as_posix(),
        "task_prompt": task_output.as_posix(),
        "effective_messages": effective_path.as_posix(),
        "task_characters": len(task_message),
        "task_utf8_bytes": len(task_message.encode("utf-8")),
        "task_lines": len(task_message.splitlines()),
        "estimated_tokens": metrics.estimated_input_tokens,
        "inline_evidence_count": metrics.unique_source_count,
        "exact_on_demand_count": metrics.exact_on_demand_count,
        "host_residue_counts": {
            token: task_message.count(token) for token in HOST_RESIDUES
        },
        "semantic_anchor_counts": {
            token: len(re.findall(re.escape(token), task_message, re.IGNORECASE))
            for token in (
                "background_story",
                "narrative_rhythm",
                "scene_bridge",
                "target_chinese_chars",
                "must_not_resolve",
                "reader_question",
                "canon_writeback",
                "new_character_register",
            )
        },
    }
    report_path = output / "scene-prose-fixed-prompt-audit.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
