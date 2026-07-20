"""Isolated live probes for Agent Runner readiness."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
from typing import Any

from .runtimes import build_runtime


def probe_agent_runner(
    config: dict[str, Any],
    runner_id: str,
    *,
    model: str = "",
    timeout: int = 90,
) -> dict[str, Any]:
    probe_config = deepcopy(config)
    runners = probe_config.setdefault("agent_runners", {})
    settings = runners.setdefault(runner_id, {})
    if model:
        settings["model"] = model
    runtime = build_runtime(runner_id, probe_config)
    before = runtime.capabilities().as_dict()
    with tempfile.TemporaryDirectory(prefix="les-runner-probe-") as temporary:
        root = Path(temporary)
        workspace = root / "workspace"
        workspace.mkdir()
        prompt = root / "PROBE_TASK.md"
        prompt.write_text(
            "Reply with exactly STUDIO_RUNNER_READY. Do not call tools and do not create or modify files.",
            encoding="utf-8",
        )
        result = runtime.execute(workspace, prompt, root, timeout=max(10, int(timeout)))
        events = _read_events(root / "runtime.events.jsonl")
        actual_model = ""
        provider = str(before.get("provider") or "")
        for event in events:
            if event.get("event") == "runner.ready":
                actual_model = str(event.get("model") or "")
            if event.get("event") == "runner.session.started":
                actual_model = actual_model or str(event.get("model") or "")
            if event.get("event") == "usage.updated" and isinstance(event.get("model_usage"), dict):
                models = list(event["model_usage"])
                if models:
                    actual_model = actual_model or str(models[0])
        output = result.output_path.read_text(encoding="utf-8", errors="replace") if result.output_path else ""
        output_tail = output[-2000:]
        configured_model = str(settings.get("model") or "")
        model_matches = not (configured_model and actual_model) or _models_compatible(configured_model, actual_model)
        warnings = []
        if not model_matches:
            warnings.append(
                f"Runner returned model {actual_model!r} although {configured_model!r} was requested; "
                "the authenticated Agent environment may be applying an alias or provider override."
            )
        return {
            "runner_id": runner_id,
            "status": "ready" if result.status == "completed" and "STUDIO_RUNNER_READY" in output else result.status,
            "returncode": result.returncode,
            "message": result.message,
            "configured_model": configured_model,
            "actual_model": actual_model,
            "model_matches_request": model_matches,
            "provider": provider,
            "capabilities": before,
            "event_count": len(events),
            "response_verified": "STUDIO_RUNNER_READY" in output,
            "diagnostic_output_tail": output_tail if result.status != "completed" else "",
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


def _models_compatible(requested: str, actual: str) -> bool:
    requested_name = requested.strip().lower()
    actual_name = actual.strip().lower()
    return requested_name == actual_name or requested_name in actual_name or actual_name in requested_name
