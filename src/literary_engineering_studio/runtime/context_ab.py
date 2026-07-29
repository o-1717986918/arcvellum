"""Isolated same-task A/B measurement for context-budget rollout."""

from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Callable, Iterator, Mapping

from ..contracts import load_task_package
from ..integrations.opencode.opencode_runtime_pool import (
    OpenCodeRuntimePool,
)
from ..observability.throughput_metrics import (
    build_throughput_projection,
)
from ..process_manager import ProcessManager
from .engine_bridge import CoreBridge
from .context_ab_reporting import (
    CONTEXT_AB_SCHEMA,
    build_arm_report,
    build_experiment_report,
)
from .worker import AgentWorker
from .worker_results import WorkerRunResult


_ARMS = ("shadow", "bounded")
_MAX_TRANSIENT_ARM_RETRIES = 1


def run_context_ab_experiment(
    project_root: Path,
    *,
    task_id: str,
    runtime_id: str,
    config: dict[str, Any],
    output_path: Path | None = None,
    worker_factory: Callable[..., AgentWorker] = AgentWorker,
) -> dict[str, object]:
    """Execute one formal task in isolated shadow/bounded project copies."""

    project = project_root.resolve()
    if output_path is not None and output_path.resolve().is_relative_to(
        project
    ):
        raise ValueError(
            "context A/B report must be written outside the source project"
        )
    task_path = _task_path(project, task_id)
    original_task = load_task_package(project, task_path)
    original_digest = project_content_digest(project)
    with tempfile.TemporaryDirectory(
        prefix="arcvellum-context-ab-",
    ) as temporary:
        experiment_root = Path(temporary)
        arms = {
            mode: _run_arm_with_transient_retry(
                project,
                original_task.route,
                task_id,
                runtime_id,
                config,
                mode,
                experiment_root / mode,
                worker_factory,
            )
            for mode in _ARMS
        }
    final_digest = project_content_digest(project)
    report = build_experiment_report(
        task_id,
        original_task.route,
        runtime_id,
        original_digest,
        final_digest,
        arms,
    )
    if output_path is not None:
        target = output_path.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return report


def _run_arm_with_transient_retry(
    source_project: Path,
    route: str,
    task_id: str,
    runtime_id: str,
    config: dict[str, Any],
    mode: str,
    arm_root: Path,
    worker_factory: Callable[..., AgentWorker],
) -> dict[str, object]:
    elapsed = 0.0
    transient_retries = 0
    report: dict[str, object] = {}
    for attempt in range(_MAX_TRANSIENT_ARM_RETRIES + 1):
        report = _run_arm(
            source_project,
            route,
            task_id,
            runtime_id,
            config,
            mode,
            arm_root / f"attempt-{attempt + 1}",
            worker_factory,
        )
        elapsed += float(report.get("elapsed_seconds") or 0)
        failure = _mapping(report.get("failure"))
        if failure.get("retryable") is not True:
            break
        transient_retries += 1
    result = dict(report)
    result["elapsed_seconds"] = round(elapsed, 3)
    result["experiment_attempts"] = transient_retries + 1
    result["experiment_transient_retries"] = transient_retries
    return result


def project_content_digest(root: Path) -> str:
    identities: list[tuple[str, str]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        identities.append(
            (
                relative,
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    encoded = json.dumps(
        identities,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _run_arm(
    source_project: Path,
    route: str,
    task_id: str,
    runtime_id: str,
    config: dict[str, Any],
    mode: str,
    arm_root: Path,
    worker_factory: Callable[..., AgentWorker],
) -> dict[str, object]:
    project = arm_root / "project"
    runs = arm_root / "runs"
    shutil.copytree(source_project, project)
    task_path = _task_path(project, task_id)
    _remove_prior_outputs(project, task_path)
    _refresh_task_contract(
        project,
        route,
        task_id,
        config,
    )
    events: list[dict[str, Any]] = []
    sequence = 0

    def emit(event: str, data: dict[str, Any]) -> None:
        nonlocal sequence
        sequence += 1
        events.append(
            {
                "sequence": sequence,
                "event": (
                    event if event.startswith("worker.") else f"worker.{event}"
                ),
                "at": datetime.now(timezone.utc).isoformat(),
                "data": dict(data),
            }
        )

    arm_config = _arm_config(config, mode, runs)
    started = time.monotonic()
    with _owned_runtime_pool(
        runtime_id,
        arm_config,
        arm_root,
    ) as runtime_pool:
        worker_kwargs: dict[str, object] = {"event_sink": emit}
        if runtime_pool is not None:
            worker_kwargs["runtime_pool"] = runtime_pool
        worker = worker_factory(arm_config, **worker_kwargs)
        result = worker.run_once(
            project,
            route=route,
            runtime_id=runtime_id,
            task_id=task_id,
        )
        result = _finish_isolated_writeback(worker, result)
    elapsed = time.monotonic() - started
    projection = build_throughput_projection(events)
    current_task = load_task_package(project, _task_path(project, task_id))
    run_manifest = _run_manifest(result)
    return build_arm_report(
        mode,
        result,
        elapsed,
        projection,
        current_task,
        run_manifest,
    )


def _arm_config(
    config: dict[str, Any],
    mode: str,
    runs_root: Path,
) -> dict[str, Any]:
    value = deepcopy(config)
    worker = value.setdefault("worker", {})
    worker["runs_root"] = str(runs_root)
    budget = worker.setdefault("context_budget", {})
    budget["mode"] = mode
    rollout = budget.setdefault("bounded_rollout", {})
    rollout["enabled"] = False
    return value


def _finish_isolated_writeback(
    worker: AgentWorker,
    result: WorkerRunResult,
) -> WorkerRunResult:
    if result.status != "waiting_writeback":
        return result
    if result.run_root is None:
        raise RuntimeError(
            "context A/B arm requested writeback without a run root"
        )
    try:
        finalized = worker.approve_writeback(
            result.run_root,
            approved_by="experiment:context-ab-isolated",
        )
    except Exception as exc:
        raise RuntimeError(
            "context A/B isolated writeback approval failed"
        ) from exc
    if finalized.status == "waiting_writeback":
        raise RuntimeError(
            "context A/B isolated writeback did not reach a terminal state"
        )
    return finalized


def _remove_prior_outputs(project: Path, task_path: Path) -> None:
    task = load_task_package(project, task_path)
    for relative in task.expected_outputs:
        path = project / Path(relative)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def _refresh_task_contract(
    project: Path,
    route: str,
    task_id: str,
    config: dict[str, Any],
) -> None:
    issued = CoreBridge(config).task_contract_replay(
        project,
        task_id,
    )
    current = str(issued.fields.get("task_id") or "")
    if current != task_id:
        raise ValueError(
            "context A/B source task is no longer the current route task: "
            f"expected {task_id}, received {current or 'route-ready'}"
        )


@contextmanager
def _owned_runtime_pool(
    runtime_id: str,
    config: dict[str, Any],
    arm_root: Path,
) -> Iterator[OpenCodeRuntimePool | None]:
    if runtime_id != "opencode":
        yield None
        return
    manager = ProcessManager(arm_root / "runtime-sidecars")
    pool = OpenCodeRuntimePool(
        config,
        manager,
        idle_timeout_seconds=60,
    )
    try:
        yield pool
    finally:
        pool.shutdown()
        manager.shutdown()


def _run_manifest(result: WorkerRunResult) -> Mapping[str, Any]:
    if result.run_root is None:
        return {}
    path = result.run_root / "run.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _mapping(payload)


def _task_path(project: Path, task_id: str) -> Path:
    path = project / "workflow" / "tasks" / f"{task_id}.task.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"formal task package not found: {task_id}"
        )
    return path


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


__all__ = [
    "CONTEXT_AB_SCHEMA",
    "project_content_digest",
    "run_context_ab_experiment",
]
