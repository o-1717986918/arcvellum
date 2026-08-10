"""Explicit, content-safe live Runtime benchmark execution."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ..application.config import load_config
from ..runtime.worker import AgentWorker
from ..runtime.run_manifest import load_run
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
    prompt_version: str = "configured",
) -> dict[str, object]:
    """Run one benchmark task and return a sanitized evidence projection."""

    runtime_config = deepcopy(config or load_config())
    _configure_prompt_version(runtime_config, prompt_version, runtime_id)
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
        return _unavailable(
            case,
            runtime_id,
            capabilities.detail,
            prompt_version=prompt_version,
        )

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
    preflight = _safe_preflight_projection(result.run_root)
    return {
        "schema": LIVE_REPORT_SCHEMA,
        "case_id": case.case_id,
        "benchmark_class": case.benchmark_class,
        "runtime": runtime_id,
        "selected_model": capabilities.selected_model or "unavailable",
        "runner_readiness": capabilities.readiness_state,
        "requested_prompt_version": prompt_version,
        "status": result.status,
        "failure_kind": result.failure_kind,
        "retryable": result.retryable,
        "preflight": preflight,
        "sample": sample if isinstance(sample, dict) else {},
        "content_policy": "no prompts, prose, reasoning text, paths, credentials, or tool payloads",
    }


def _safe_preflight_projection(run_root: Path | None) -> dict[str, object]:
    if run_root is None:
        return {"issue_count": 0, "issue_codes": []}
    try:
        manifest = load_run(run_root)
    except (OSError, ValueError):
        return {"issue_count": 0, "issue_codes": []}
    preflight = manifest.get("preflight")
    payload = preflight if isinstance(preflight, dict) else {}
    issues = payload.get("issues")
    rows = issues if isinstance(issues, list) else []
    codes = sorted(
        {
            str(item.get("code") or "").strip()
            for item in rows
            if isinstance(item, dict) and str(item.get("code") or "").strip()
        }
    )
    return {"issue_count": len(rows), "issue_codes": codes}


def _configure_prompt_version(
    config: dict[str, Any],
    prompt_version: str,
    runtime_id: str,
) -> None:
    if prompt_version == "configured":
        return
    if prompt_version not in {"v2", "v3"}:
        raise ValueError(f"unsupported live prompt version: {prompt_version}")
    worker = config.setdefault("worker", {})
    prompt = worker.setdefault("prompt_program", {})
    prompt.update(
        {
            "mode": "off" if prompt_version == "v2" else "enforced",
            "version": "v3",
            "fallback": "v2",
            "enforcement": {
                "enabled": prompt_version == "v3",
                "runtimes": [runtime_id],
                "routes": [],
                "states": [],
                "task_kinds": [],
            },
        }
    )


def _unavailable(
    case: BenchmarkCase,
    runtime_id: str,
    detail: str,
    *,
    prompt_version: str = "configured",
) -> dict[str, object]:
    return {
        "schema": LIVE_REPORT_SCHEMA,
        "case_id": case.case_id,
        "benchmark_class": case.benchmark_class,
        "runtime": runtime_id,
        "selected_model": "unavailable",
        "runner_readiness": "unavailable",
        "requested_prompt_version": prompt_version,
        "status": "evidence-insufficient",
        "failure_kind": "runner-unavailable",
        "retryable": None,
        "preflight": {"issue_count": 0, "issue_codes": []},
        "diagnostic": detail,
        "sample": {},
        "content_policy": "no prompts, prose, reasoning text, paths, credentials, or tool payloads",
    }
