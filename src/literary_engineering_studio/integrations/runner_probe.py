"""Isolated live probes for registered Agent runtimes."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import time
from typing import Any

from ..runtimes import build_runtime


def probe_agent_runner(
    config: dict[str, Any],
    runner_id: str,
    *,
    model: str = "",
    role: str = "worker",
    timeout: int = 90,
    runtime_pool=None,
) -> dict[str, Any]:
    probe_config = deepcopy(config)
    runners = probe_config.setdefault("agent_runners", {})
    settings = runners.setdefault(runner_id, {})
    if model:
        settings["model"] = model
        models = settings.setdefault("models", {})
        models[role] = model
    runtime = build_runtime(runner_id, probe_config, runtime_pool=runtime_pool, role=role)
    before = runtime.capabilities().as_dict()
    with tempfile.TemporaryDirectory(prefix="arcvellum-runner-probe-") as temporary:
        root = Path(temporary)
        workspace = root / "workspace"
        workspace.mkdir()
        prompt = root / "PROBE_TASK.md"
        prompt.write_text(
            "Reply with exactly STUDIO_RUNNER_READY. Do not call tools and do not create or modify files.",
            encoding="utf-8",
        )
        started = time.monotonic()
        execute_options: dict[str, object] = {"timeout": max(10, int(timeout))}
        if runner_id == "pi-worker":
            execute_options["worker_mode"] = "conversation"
        result = runtime.execute(workspace, prompt, root, **execute_options)
        total_ms = round((time.monotonic() - started) * 1000)
        events = _read_events(root / "runtime.events.jsonl")
        actual_model = _actual_model(events)
        output = _read_runtime_output(result.output_path)
        configured_model = str(settings.get("model") or "")
        model_matches = not (configured_model and actual_model) or _models_compatible(
            configured_model, actual_model
        )
        return _probe_report(
            runner_id=runner_id,
            before=before,
            result=result,
            events=events,
            output=output,
            total_ms=total_ms,
            configured_model=configured_model,
            actual_model=actual_model,
            model_matches=model_matches,
        )


def _actual_model(events: list[dict[str, Any]]) -> str:
    for event in events:
        if event.get("event") in {"runner.ready", "runner.session.started"}:
            model = str(event.get("model") or "")
            if model:
                return model
        if event.get("event") == "usage.updated" and isinstance(event.get("model_usage"), dict):
            models = list(event["model_usage"])
            if models:
                return str(models[0])
    return ""


def _probe_report(
    *,
    runner_id: str,
    before: dict[str, Any],
    result,
    events: list[dict[str, Any]],
    output: str,
    total_ms: int,
    configured_model: str,
    actual_model: str,
    model_matches: bool,
) -> dict[str, Any]:
    verified = "STUDIO_RUNNER_READY" in output
    warnings = [] if model_matches else [
        f"Runner returned model {actual_model!r} although {configured_model!r} was requested."
    ]
    return {
        "runner_id": runner_id,
        "status": "ready" if result.status == "completed" and verified else result.status,
        "returncode": result.returncode,
        "message": result.message,
        "configured_model": configured_model,
        "actual_model": actual_model,
        "model_matches_request": model_matches,
        "provider": str(before.get("provider") or ""),
        "capabilities": before,
        "event_count": len(events),
        "total_ms": total_ms,
        "time_to_first_event_ms": next(
            (int(item.get("elapsed_ms") or 0) for item in events if item.get("event") == "runner.first_event"),
            0,
        ),
        "service_reused": bool((result.metadata or {}).get("service_reused")),
        "response_verified": verified,
        "diagnostic_output_tail": output[-2000:] if result.status != "completed" else "",
        "warnings": warnings,
    }


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _read_runtime_output(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _models_compatible(requested: str, actual: str) -> bool:
    requested_name = requested.strip().lower()
    actual_name = actual.strip().lower()
    return requested_name == actual_name or requested_name in actual_name or actual_name in requested_name


__all__ = ["probe_agent_runner"]
