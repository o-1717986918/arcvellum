"""Reproducible compile-only Prompt v2/v3 canary evidence."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..application.config import default_config
from ..runtime.worker import AgentWorker
from .runtime_benchmark import BenchmarkCase, reconstruct_benchmark_case


PROMPT_CANARY_SCHEMA = "arcvellum/prompt-compile-canary/v1"
_REDUCTION_GATES = {
    "structured": 0.30,
    "analysis": 0.60,
    "prose": 0.80,
    "review": 0.40,
    "planning": 0.40,
}


def run_prompt_compile_canary(
    cases: Iterable[BenchmarkCase],
    destination: Path,
    *,
    runtime_id: str = "pi-worker",
    config: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    root = destination.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=False)
    samples = [
        _compile_case(case, root / case.case_id, runtime_id, config)
        for case in cases
    ]
    report: dict[str, object] = {
        "schema": PROMPT_CANARY_SCHEMA,
        "mode": "compile-only",
        "runtime_renderer": runtime_id,
        "sample_count": len(samples),
        "status": "pass" if samples and all(row["status"] == "pass" for row in samples) else "fail",
        "samples": samples,
        "limitations": [
            "No model was invoked; quality, preflight pass rate, latency, and provider token usage remain unproven.",
            "A live interleaved A/B gate is still required before Prompt v3 enforcement is enabled.",
        ],
        "live_quality_gate": {
            "status": "pending-current-live-ab",
            "historical_baseline": "docs/benchmarks/prompt-v3-final-ab-gate-2026-08-11.json",
            "historical_coverage": ["structured", "review"],
            "required_dimensions": [
                "closure_rate",
                "time_to_first_artifact",
                "total_cost",
                "repair_count",
                "blind_literary_quality",
            ],
        },
        "content_policy": "no prompt bodies, prose, reasoning, credentials, or absolute paths",
    }
    report["revision"] = _digest(report)[:20]
    return report


def render_prompt_canary_markdown(report: Mapping[str, object]) -> str:
    lines = [
        "# ArcVellum Prompt v3 Compile Canary",
        "",
        f"- revision: `{report.get('revision')}`",
        f"- status: `{report.get('status')}`",
        "- mode: compile-only; no model was invoked.",
        "",
        "| case | class/runtime kind | v2 chars | v3 chars | reduction | gate | duplicate | lint | status |",
        "|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for value in report.get("samples") or []:
        if not isinstance(value, Mapping):
            continue
        lines.append(_markdown_canary_row(value))
    lines.extend(
        (
            "",
            "## Live Quality Gate",
            "",
            f"- current: `{_mapping(report.get('live_quality_gate')).get('status', 'pending')}`",
            "- historical baseline: `docs/benchmarks/prompt-v3-final-ab-gate-2026-08-11.json`",
            "- compile pass does not authorize broad Prompt v3 enforcement.",
            "",
            "## Limitations",
            "",
            *[f"- {item}" for item in report.get("limitations") or []],
        )
    )
    return "\n".join(lines) + "\n"


def _markdown_canary_row(value: Mapping[str, object]) -> str:
    v2, v3 = _mapping(value.get("v2")), _mapping(value.get("v3"))
    fields = {
        "case": value.get("case_id") or "",
        "klass": value.get("benchmark_class") or "",
        "kind": value.get("runtime_task_kind") or "",
        "v2": v2.get("total_characters") or 0,
        "v3": v3.get("total_characters") or 0,
        "reduction": float(value.get("actual_character_reduction") or 0.0),
        "gate": float(value.get("required_character_reduction") or 0.0),
        "duplicate": float(v3.get("duplicate_character_ratio") or 0.0),
        "lint": value.get("v3_lint_status") or "",
        "status": value.get("status") or "",
    }
    return (
        "| {case} | {klass}/{kind} | {v2} | {v3} | {reduction:.1%} | "
        "{gate:.0%} | {duplicate:.1%} | {lint} | {status} |"
    ).format(**fields)


def _compile_case(
    case: BenchmarkCase,
    root: Path,
    runtime_id: str,
    config: Mapping[str, Any] | None,
) -> dict[str, object]:
    runtime_config = deepcopy(dict(config or default_config()))
    worker = dict(runtime_config.get("worker") or {})
    worker["runs_root"] = str(root / "runs")
    prompt = dict(worker.get("prompt_program") or {})
    prompt.update({"mode": "shadow", "fallback": "v2"})
    worker["prompt_program"] = prompt
    runtime_config["worker"] = worker
    reconstructed = reconstruct_benchmark_case(
        case, root / "project", config=runtime_config
    )
    _task, sandbox, terminal = AgentWorker(runtime_config).prepare(
        reconstructed.project_root,
        route=reconstructed.route,
        runtime_id=runtime_id,
        task_id=reconstructed.task_id,
    )
    if terminal is not None or sandbox is None:
        return {
            "case_id": case.case_id,
            "benchmark_class": case.benchmark_class,
            "status": "fail",
            "failure_kind": "preparation-failed",
            "task_contract_sha256": reconstructed.task_contract_sha256,
        }
    manifest = json.loads(sandbox.manifest_path.read_text(encoding="utf-8"))
    materialization = _mapping(manifest.get("prompt_program"))
    formal = _mapping(_mapping(materialization.get("formal")).get("metrics"))
    shadow_record = _mapping(materialization.get("shadow"))
    shadow = _mapping(shadow_record.get("metrics"))
    program = _mapping(shadow_record.get("program"))
    lint = _mapping(shadow_record.get("lint"))
    reduction = _reduction(formal, shadow)
    required = _REDUCTION_GATES.get(case.benchmark_class, 0.0)
    passed = (
        lint.get("status") == "pass"
        and float(shadow.get("duplicate_character_ratio") or 0.0) < 0.10
        and reduction >= required
    )
    identity = _mapping(program.get("task_identity"))
    return {
        "case_id": case.case_id,
        "benchmark_class": case.benchmark_class,
        "runtime_task_kind": str(identity.get("task_kind") or ""),
        "task_contract_sha256": reconstructed.task_contract_sha256,
        "status": "pass" if passed else "fail",
        "required_character_reduction": required,
        "actual_character_reduction": reduction,
        "v2": _safe_metrics(formal),
        "v3": _safe_metrics(shadow),
        "v3_lint_status": str(lint.get("status") or "missing"),
        "prompt_program_digest": str(program.get("digest") or ""),
        "compile_metrics": dict(_mapping(program.get("compile_metrics"))),
    }


def _safe_metrics(value: Mapping[str, object]) -> dict[str, object]:
    return {
        key: value.get(key)
        for key in (
            "total_characters",
            "estimated_input_tokens",
            "instruction_characters",
            "evidence_characters",
            "unique_source_count",
            "duplicate_character_ratio",
            "constraint_count",
            "constraint_repetition_ratio",
            "exact_on_demand_count",
            "prompt_sha256",
        )
    }


def _reduction(formal: Mapping[str, object], shadow: Mapping[str, object]) -> float:
    baseline = int(formal.get("total_characters") or 0)
    candidate = int(shadow.get("total_characters") or 0)
    return round(1 - (candidate / baseline), 6) if baseline > 0 else 0.0


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = [
    "PROMPT_CANARY_SCHEMA",
    "render_prompt_canary_markdown",
    "run_prompt_compile_canary",
]
