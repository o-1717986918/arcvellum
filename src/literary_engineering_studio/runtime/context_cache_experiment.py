"""Isolated micro-benchmark for rebuildable prepared-context reuse."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
from statistics import median
import tempfile
import time
from typing import Any, Mapping

from ..contracts import TaskPackage, load_task_package
from .context_ab import project_content_digest
from .context_budget import resolve_task_context_budget
from .engine_bridge import CoreBridge
from .prepared_context_cache import PreparedContextCache
from .sandbox import stage_task


CONTEXT_CACHE_EXPERIMENT_SCHEMA = "arcvellum/prepared-context-cache-experiment/v1"


def run_prepared_context_cache_experiment(
    project_root: Path,
    *,
    task_id: str,
    config: dict[str, Any],
    output_path: Path | None = None,
    repetitions: int = 5,
) -> dict[str, object]:
    """Measure cache reuse in an isolated project copy without invoking a model."""

    project = project_root.resolve()
    if output_path is not None and output_path.resolve().is_relative_to(project):
        raise ValueError("context cache report must be written outside the source project")
    count = max(2, min(20, int(repetitions)))
    original_digest = project_content_digest(project)
    with tempfile.TemporaryDirectory(prefix="arcvellum-context-cache-") as temporary:
        root = Path(temporary)
        isolated_project = root / "project"
        shutil.copytree(project, isolated_project)
        bridge = CoreBridge(config)
        bridge.task_contract_replay(isolated_project, task_id)
        task = load_task_package(isolated_project, _task_path(isolated_project, task_id))
        if task.command:
            bridge.execute_task_command(task.command, isolated_project)
            task = load_task_package(isolated_project, _task_path(isolated_project, task_id))
        report = measure_prepared_context_cache_reuse(
            task,
            runs_root=root / "runs",
            worker_config=_bounded_worker_config(config),
            repetitions=count,
        )
    final_digest = project_content_digest(project)
    report["source_project_unchanged"] = original_digest == final_digest
    report["criteria"]["source_project_unchanged"] = original_digest == final_digest
    report["cache_canary_candidate"] = all(report["criteria"].values())
    if output_path is not None:
        target = output_path.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return report


def measure_prepared_context_cache_reuse(
    task: TaskPackage,
    *,
    runs_root: Path,
    worker_config: Mapping[str, Any],
    repetitions: int = 5,
) -> dict[str, object]:
    """Stage equivalent Agent views through one shared cache lifecycle."""

    count = max(2, min(20, int(repetitions)))
    cache = PreparedContextCache(enabled=True, max_entries=2)
    budget = resolve_task_context_budget(task, worker_config)
    samples: list[dict[str, object]] = []
    for index in range(count):
        started = time.perf_counter_ns()
        sandbox = stage_task(
            task,
            runs_root,
            runtime="context-cache-experiment",
            run_id=f"prepared-context-{index + 1:02d}",
            context_budget=budget,
            prepared_context_cache=cache,
        )
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        manifest = _read_json(sandbox.manifest_path)
        cache_state = _mapping(manifest.get("prepared_context_cache"))
        context_state = _mapping(manifest.get("context_budget"))
        samples.append(
            {
                "sequence": index + 1,
                "cache_status": str(cache_state.get("status") or ""),
                "cache_key": str(cache_state.get("key") or ""),
                "elapsed_ms": round(elapsed_ms, 3),
                "prepared_context_sha256": str(manifest.get("prepared_context_sha256") or ""),
                "prepared_context_characters": int(manifest.get("prepared_context_characters") or 0),
                "context_budget_digest": str(context_state.get("digest") or ""),
            }
        )
    first_ms = float(samples[0]["elapsed_ms"])
    hit_times = [float(item["elapsed_ms"]) for item in samples[1:]]
    median_hit_ms = median(hit_times)
    speedup = (first_ms - median_hit_ms) / first_ms if first_ms > 0 else 0.0
    criteria = _cache_reuse_criteria(samples, speedup)
    return {
        "schema": CONTEXT_CACHE_EXPERIMENT_SCHEMA,
        "task_id": task.task_id,
        "route": task.route,
        "current_state": task.current_state,
        "repetitions": count,
        "samples": samples,
        "cache_status": cache.status(),
        "comparison": {
            "first_miss_ms": round(first_ms, 3),
            "median_hit_ms": round(median_hit_ms, 3),
            "preparation_speedup_ratio": round(speedup, 6),
        },
        "claims": {
            "model_invoked": False,
            "model_token_reduction": False,
            "measured_scope": "context preparation CPU and local file IO only",
        },
        "criteria": criteria,
        "cache_canary_candidate": all(criteria.values()),
    }


def _cache_reuse_criteria(
    samples: list[dict[str, object]],
    speedup: float,
) -> dict[str, bool]:
    statuses = [str(item["cache_status"]) for item in samples]
    keys = {str(item["cache_key"]) for item in samples}
    content_digests = {str(item["prepared_context_sha256"]) for item in samples}
    budget_digests = {str(item["context_budget_digest"]) for item in samples}
    return {
        "first_preparation_is_miss": statuses[0] == "miss",
        "all_repeated_preparations_are_hits": all(value == "hit" for value in statuses[1:]),
        "cache_key_is_stable": len(keys) == 1 and "" not in keys,
        "prepared_content_is_identical": len(content_digests) == 1 and "" not in content_digests,
        "context_budget_is_identical": len(budget_digests) == 1 and "" not in budget_digests,
        "median_hit_is_at_least_five_percent_faster": speedup >= 0.05,
    }


def _bounded_worker_config(config: Mapping[str, Any]) -> dict[str, Any]:
    worker = deepcopy(_mapping(config.get("worker")))
    context = worker.setdefault("context_budget", {})
    context["mode"] = "bounded"
    context.setdefault("bounded_rollout", {})["enabled"] = False
    return worker


def _task_path(project: Path, task_id: str) -> Path:
    path = project / "workflow" / "tasks" / f"{task_id}.task.json"
    if not path.is_file():
        raise FileNotFoundError(f"formal task package not found: {task_id}")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return payload


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = [
    "CONTEXT_CACHE_EXPERIMENT_SCHEMA",
    "measure_prepared_context_cache_reuse",
    "run_prepared_context_cache_experiment",
]
