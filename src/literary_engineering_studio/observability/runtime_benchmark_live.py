"""Explicit, content-safe live Runtime benchmark execution."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ..application.config import load_config
from ..runtime.worker import AgentWorker
from ..runtimes import build_runtime
from .runtime_benchmark import (
    BenchmarkCase,
    build_historical_runtime_report,
    reconstruct_benchmark_case,
)


LIVE_REPORT_SCHEMA = "arcvellum/runtime-benchmark-live-smoke/v1"


def run_live_benchmark(
    case: BenchmarkCase,
    destination: Path,
    *,
    runtime_id: str = "opencode",
    timeout_seconds: int = 300,
    config: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Run one benchmark task and return a sanitized evidence projection."""

    runtime_config = deepcopy(config or load_config())
    worker_config = dict(runtime_config.get("worker") or {})
    runs_root = destination.parent / ".runtime-benchmark-live-runs"
    worker_config.update(
        {
            "runs_root": str(runs_root),
            "timeout_seconds": max(30, int(timeout_seconds)),
        }
    )
    runtime_config["worker"] = worker_config
    capabilities = build_runtime(runtime_id, runtime_config).capabilities()
    if not capabilities.available:
        return _unavailable(case, runtime_id, capabilities.detail)

    reconstructed = reconstruct_benchmark_case(case, destination, config=runtime_config)
    result = AgentWorker(runtime_config).run_once(
        reconstructed.project_root,
        route=reconstructed.route,
        runtime_id=runtime_id,
        task_id=reconstructed.task_id,
    )
    historical = build_historical_runtime_report(result.run_root or runs_root, limit=1)
    samples = historical.get("samples")
    sample = samples[-1] if isinstance(samples, list) and samples else {}
    return {
        "schema": LIVE_REPORT_SCHEMA,
        "case_id": case.case_id,
        "benchmark_class": case.benchmark_class,
        "runtime": runtime_id,
        "selected_model": capabilities.selected_model or "unavailable",
        "runner_readiness": capabilities.readiness_state,
        "status": result.status,
        "failure_kind": result.failure_kind,
        "retryable": result.retryable,
        "sample": sample if isinstance(sample, dict) else {},
        "content_policy": "no prompts, prose, reasoning text, paths, credentials, or tool payloads",
    }


def _unavailable(case: BenchmarkCase, runtime_id: str, detail: str) -> dict[str, object]:
    return {
        "schema": LIVE_REPORT_SCHEMA,
        "case_id": case.case_id,
        "benchmark_class": case.benchmark_class,
        "runtime": runtime_id,
        "selected_model": "unavailable",
        "runner_readiness": "unavailable",
        "status": "evidence-insufficient",
        "failure_kind": "runner-unavailable",
        "retryable": None,
        "diagnostic": detail,
        "sample": {},
        "content_policy": "no prompts, prose, reasoning text, paths, credentials, or tool payloads",
    }
