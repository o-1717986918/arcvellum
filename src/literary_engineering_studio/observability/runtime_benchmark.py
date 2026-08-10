"""Reproducible, content-safe runtime benchmark fixtures and reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ..application.config import default_config
from .runtime_event_timings import recover_event_timings
from .throughput_metrics import build_throughput_projection
from .runtime_benchmark_preparation import drive_benchmark_preparation
from .runtime_benchmark_scene import seed_synthetic_scene
from .prompt_benchmark_projection import prompt_program_projection
from .reasoning_benchmark_projection import reasoning_budget_projection
from literary_engineering_studio_engine.projects.init import InitOptions, init_work_project


CATALOG_SCHEMA = "arcvellum/runtime-benchmark-catalog/v1"
REPORT_SCHEMA = "arcvellum/runtime-benchmark-report/v1"
RECONSTRUCTION_SCHEMA = "arcvellum/runtime-benchmark-reconstruction/v1"


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    benchmark_class: str
    fixture_id: str
    title: str
    premise: str
    work_type: str
    target_length: int
    route: str
    preparation: str
    expected_state: str
    availability: str
    rationale: str


@dataclass(frozen=True)
class ReconstructedBenchmark:
    schema: str
    case_id: str
    benchmark_class: str
    project_root: Path
    task_id: str
    route: str
    current_state: str
    task_type: str
    execution_policy: str
    agent_role: str
    task_json_sha256: str
    task_markdown_sha256: str
    task_contract_sha256: str
    preparation_steps: int
    deterministic_steps: int
    synthetic_agent_steps: int

    def safe_projection(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("project_root", None)
        return payload


def load_benchmark_catalog(path: Path) -> tuple[BenchmarkCase, ...]:
    payload = _read_json(path)
    if payload.get("schema") != CATALOG_SCHEMA:
        raise ValueError(f"unsupported runtime benchmark catalog: {payload.get('schema')}")
    rows = payload.get("cases")
    if not isinstance(rows, list) or not rows:
        raise ValueError("runtime benchmark catalog must contain cases")
    cases = tuple(_case(row) for row in rows)
    identifiers = [item.case_id for item in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("runtime benchmark case ids must be unique")
    classes = {item.benchmark_class for item in cases}
    required = {"structured", "analysis", "prose", "review", "planning"}
    missing = sorted(required - classes)
    if missing:
        raise ValueError("runtime benchmark catalog misses classes: " + ", ".join(missing))
    return cases


def reconstruct_benchmark_case(
    case: BenchmarkCase,
    destination: Path,
    *,
    config: dict[str, Any] | None = None,
) -> ReconstructedBenchmark:
    if case.availability != "ready":
        raise RuntimeError(
            f"benchmark case {case.case_id} is not reconstructable yet: {case.availability}"
        )
    if case.preparation not in {"deterministic-prefix", "synthetic-scene-closure"}:
        raise ValueError(f"unsupported benchmark preparation: {case.preparation}")
    project = destination.resolve()
    if project.exists():
        raise FileExistsError(f"benchmark destination already exists: {project}")
    init_work_project(
        InitOptions(
            target=project,
            title=case.title,
            premise=case.premise,
            work_type=case.work_type,
            target_length=case.target_length,
        )
    )
    if case.preparation == "synthetic-scene-closure":
        seed_synthetic_scene(project)
    runtime_config = dict(config or default_config())
    worker_config = dict(runtime_config.get("worker") or {})
    worker_config["runs_root"] = str(project.parent / ".runtime-benchmark-runs")
    runtime_config["worker"] = worker_config
    task, deterministic_steps, synthetic_agent_steps = drive_benchmark_preparation(
        project,
        route=case.route,
        expected_state=case.expected_state,
        preparation=case.preparation,
        config=runtime_config,
    )
    return ReconstructedBenchmark(
        schema=RECONSTRUCTION_SCHEMA,
        case_id=case.case_id,
        benchmark_class=case.benchmark_class,
        project_root=project,
        task_id=task.task_id,
        route=task.route,
        current_state=task.current_state,
        task_type=task.task_type,
        execution_policy=task.execution_contract.execution_policy,
        agent_role=task.execution_contract.agent_role,
        task_json_sha256=_file_digest(task.task_json_path),
        task_markdown_sha256=_file_digest(task.task_markdown_path),
        task_contract_sha256=_digest(
            {
                "task": task.payload,
                "markdown_sha256": _file_digest(task.task_markdown_path),
            }
        ),
        preparation_steps=deterministic_steps + synthetic_agent_steps,
        deterministic_steps=deterministic_steps,
        synthetic_agent_steps=synthetic_agent_steps,
    )


def build_historical_runtime_report(runs_root: Path, *, limit: int = 0) -> dict[str, object]:
    root = runs_root.expanduser().resolve()
    manifests = sorted(root.rglob("run.json"), key=lambda path: path.stat().st_mtime)
    if limit > 0:
        manifests = manifests[-limit:]
    samples = [_historical_sample(path) for path in manifests]
    samples = [item for item in samples if item is not None]
    body: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "mode": "historical",
        "sample_count": len(samples),
        "status_counts": _counts(samples, "status"),
        "runtime_counts": _counts(samples, "runtime"),
        "task_class_counts": _counts(samples, "task_kind"),
        "samples": samples,
    }
    body["revision"] = _digest(body)[:20]
    return body


def render_historical_report_markdown(report: Mapping[str, object]) -> str:
    lines = [
        "# ArcVellum Runtime Historical Baseline",
        "",
        f"- schema: `{report.get('schema')}`",
        f"- revision: `{report.get('revision')}`",
        f"- samples: `{report.get('sample_count')}`",
        "- privacy: no prompts, prose, reasoning text, absolute paths, credentials, or tool payloads are included.",
        "",
        "| run | task fingerprint | kind | runtime/model | status | first event | total | tools | repairs | tokens |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in report.get("samples") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(_markdown_sample_row(row))
    return "\n".join(lines) + "\n"


def _historical_sample(path: Path) -> dict[str, object] | None:
    try:
        manifest = _read_json(path)
    except (OSError, ValueError):
        return None
    events = _runtime_events(path.parent / "runtime.events.jsonl")
    normalized = _projection_events(manifest, events)
    projection = build_throughput_projection(normalized)
    runtime_metadata = _mapping(manifest.get("runtime_metadata"))
    context = _mapping(manifest.get("context_budget"))
    usage = _mapping(projection.get("usage"))
    model = _last_event_value(events, "model")
    timings = _sample_timings(manifest, runtime_metadata, events)
    return {
        **_sample_identity(manifest, path),
        **_sample_execution(manifest, runtime_metadata, context, model),
        **timings,
        **_sample_metrics(manifest, events, projection, context, timings, usage),
    }


def _sample_identity(manifest: Mapping[str, object], path: Path) -> dict[str, object]:
    return {
        "run_fingerprint": _digest(str(manifest.get("run_id") or path.parent.name))[:12],
        "project_fingerprint": _digest(str(manifest.get("project_root") or "unknown"))[:12],
        "task_fingerprint": _digest(str(manifest.get("task_id") or "unknown"))[:12],
        "route": str(manifest.get("route") or ""),
        "current_state": str(manifest.get("current_state") or ""),
    }


def _sample_execution(
    manifest: Mapping[str, object],
    runtime_metadata: Mapping[str, object],
    context: Mapping[str, object],
    model: str,
) -> dict[str, object]:
    profile = _mapping(manifest.get("execution_profile"))
    return {
        "task_kind": str(context.get("task_kind") or "unknown"),
        "runtime": str(manifest.get("runtime") or ""),
        "model": model or "unavailable",
        "status": str(manifest.get("status") or "unknown"),
        "failure_kind": str(runtime_metadata.get("failure_kind") or ""),
        "retryable": _optional_bool(runtime_metadata.get("retryable")),
        "execution_profile_mode": str(profile.get("mode") or "unavailable"),
        "execution_profile_digest": str(profile.get("digest") or ""),
    }


def _sample_metrics(
    manifest: Mapping[str, object],
    events: list[dict[str, object]],
    projection: Mapping[str, object],
    context: Mapping[str, object],
    timings: Mapping[str, object],
    usage: Mapping[str, object],
) -> dict[str, object]:
    cache = _mapping(manifest.get("prepared_context_cache"))
    return {
        "prepared_context_characters": _integer(manifest.get("prepared_context_characters")),
        "context_mode": str(context.get("mode") or "unavailable"),
        "cache_status": str(cache.get("status") or "unavailable"),
        "tool_calls": sum(1 for item in events if item.get("event") == "tool.started"),
        "persisted_event_count": len(events),
        "reasoning_activity_events": sum(
            1 for item in events if item.get("event") == "runner.reasoning.activity"
        ),
        "text_delta_events": sum(
            1 for item in events if item.get("event") == "agent.message.delta"
        ),
        "repairs": int(projection.get("repairs") or 0),
        "usage": dict(usage),
        "prompt_program": prompt_program_projection(manifest),
        "reasoning_budget": reasoning_budget_projection(manifest, events, usage),
        "coverage": _sample_coverage(timings, usage, context),
    }


def _markdown_sample_row(row: Mapping[str, object]) -> str:
    usage = _mapping(row.get("usage"))
    return (
        "| {run} | `{task}` | {kind} | {runtime}/{model} | {status} | "
        "{first} ms | {total} ms | {tools} | {repairs} | {tokens} |"
    ).format(
        run=row.get("run_fingerprint") or "",
        task=row.get("task_fingerprint") or "",
        kind=row.get("task_kind") or "unknown",
        runtime=row.get("runtime") or "",
        model=row.get("model") or "unknown",
        status=row.get("status") or "",
        first=row.get("time_to_first_event_ms") or "n/a",
        total=row.get("total_ms") or "n/a",
        tools=row.get("tool_calls") or 0,
        repairs=row.get("repairs") or 0,
        tokens=usage.get("total_tokens") or 0,
    )


def _sample_timings(
    manifest: Mapping[str, object],
    runtime_metadata: Mapping[str, object],
    events: list[dict[str, object]],
) -> dict[str, object]:
    created = str(manifest.get("created_at") or "")
    updated = str(manifest.get("updated_at") or "")
    event_timings = recover_event_timings(events, created)
    total = (
        _integer(runtime_metadata.get("total_ms"))
        or _integer(event_timings.get("total_ms"))
        or _elapsed_ms(created, updated)
    )
    return {
        name: _available_integer(runtime_metadata.get(name) or event_timings.get(name))
        for name in (
            "time_to_process_ready_ms",
            "time_to_session_created_ms",
            "time_to_prompt_submitted_ms",
            "time_to_first_reasoning_ms",
            "time_to_first_event_ms",
            "time_to_first_text_ms",
            "time_to_first_tool_ms",
            "time_to_first_output_ms",
        )
    } | {
        "total_ms": total or "unavailable",
    }


def _sample_coverage(
    timings: Mapping[str, object],
    usage: Mapping[str, object],
    context: Mapping[str, object],
) -> dict[str, bool]:
    return {
        "first_event": timings.get("time_to_first_event_ms") != "unavailable",
        "total": timings.get("total_ms") != "unavailable",
        "usage": any(
            _integer(value) > 0
            for key, value in usage.items()
            if str(key).endswith("tokens")
        ),
        "context": bool(context),
    }


def _projection_events(
    manifest: Mapping[str, object],
    events: list[dict[str, object]],
) -> list[dict[str, object]]:
    task = {
        "task_id": str(manifest.get("task_id") or ""),
        "route": str(manifest.get("route") or ""),
        "agent_role": str(_mapping(manifest.get("execution_contract")).get("agent_role") or ""),
    }
    created = str(manifest.get("created_at") or "")
    normalized: list[dict[str, object]] = [
        {"event": "worker.task.opened", "at": created, "data": task},
        {
            "event": "worker.sandbox.context_ready",
            "at": created,
            "data": {
                **task,
                "context_budget": dict(_mapping(manifest.get("context_budget"))),
                "context_ledger_digest": str(manifest.get("context_ledger_digest") or ""),
            },
        },
        {"event": "worker.runner.started", "at": created, "data": task},
    ]
    for item in events:
        event = str(item.get("event") or "")
        if event in {"agent.message.delta", "agent.message.completed"}:
            continue
        data = {key: value for key, value in item.items() if key not in {"event", "at", "text", "detail", "path"}}
        normalized.append(
            {
                "event": event if event.startswith("worker.") else f"worker.{event}",
                "at": str(item.get("at") or ""),
                "data": {**task, **data},
            }
        )
    normalized.append(
        {
            "event": "worker.runner.completed",
            "at": str(manifest.get("updated_at") or created),
            "data": task,
        }
    )
    return normalized


def _runtime_events(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    result: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            result.append(item)
    return result


def _case(value: object) -> BenchmarkCase:
    if not isinstance(value, Mapping):
        raise ValueError("runtime benchmark case must be an object")
    fields = {
        name: str(value.get(name) or "").strip()
        for name in (
            "case_id",
            "benchmark_class",
            "fixture_id",
            "title",
            "premise",
            "work_type",
            "route",
            "preparation",
            "expected_state",
            "availability",
            "rationale",
        )
    }
    missing = [name for name, item in fields.items() if not item]
    if missing:
        raise ValueError("runtime benchmark case misses: " + ", ".join(missing))
    try:
        target = int(value.get("target_length") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("runtime benchmark target_length must be an integer") from exc
    if target <= 0:
        raise ValueError("runtime benchmark target_length must be positive")
    return BenchmarkCase(**fields, target_length=target)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return payload


def _counts(rows: list[dict[str, object]], field: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        result[key] = result.get(key, 0) + 1
    return dict(sorted(result.items()))


def _last_event_value(events: list[dict[str, object]], field: str) -> str:
    for item in reversed(events):
        value = str(item.get(field) or "").strip()
        if value:
            return value
    return ""


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _elapsed_ms(start: str, end: str) -> int:
    from datetime import datetime

    try:
        left = datetime.fromisoformat(start.replace("Z", "+00:00"))
        right = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return 0
    return max(0, round((right - left).total_seconds() * 1000))


def _integer(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _available_integer(value: object) -> int | str:
    parsed = _integer(value)
    return parsed or "unavailable"


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "BenchmarkCase",
    "ReconstructedBenchmark",
    "build_historical_runtime_report",
    "load_benchmark_catalog",
    "reconstruct_benchmark_case",
    "render_historical_report_markdown",
]
