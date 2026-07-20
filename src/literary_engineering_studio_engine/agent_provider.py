"""Shared agent provider layer for LLM-backed workbench tasks."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

from .model_config import MODEL_PROVIDER_CHOICES, get_model_settings, resolve_model_provider


AGENT_PROVIDERS = MODEL_PROVIDER_CHOICES


@dataclass(frozen=True)
class AgentMessage:
    role: str
    content: str


@dataclass(frozen=True)
class AgentRunResult:
    project_root: Path
    run_id: str
    run_dir: Path
    input_path: Path
    raw_output_path: Path
    parsed_output_path: Path
    validation_path: Path
    provider: str
    status: str
    parse_status: str


def run_agent_task(
    project_root: Path,
    *,
    agent_id: str,
    task: str,
    system_prompt: str,
    user_prompt: str,
    provider: str = "auto",
    output_dir: Path | None = None,
    metadata: dict[str, Any] | None = None,
    dry_run_output: dict[str, Any] | None = None,
) -> AgentRunResult:
    """Run a generic agent task and persist auditable input/output artifacts."""

    _validate_agent_id(agent_id)
    if not task.strip():
        raise ValueError("task is required")
    if not system_prompt.strip():
        raise ValueError("system_prompt is required")
    if not user_prompt.strip():
        raise ValueError("user_prompt is required")
    resolved_provider = resolve_model_provider(provider, purpose=f"agent task {agent_id}/{task}")

    root = project_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"project root does not exist: {root}")
    run_id = _build_run_id(agent_id)
    run_dir = _resolve_run_dir(root, output_dir, run_id)
    run_id = run_dir.name
    run_dir.mkdir(parents=True, exist_ok=False)

    input_path = run_dir / "input.prompt.json"
    raw_output_path = run_dir / "raw_output.md"
    parsed_output_path = run_dir / "parsed_output.json"
    validation_path = run_dir / "validation_report.md"

    messages = [
        AgentMessage(role="system", content=system_prompt.strip()),
        AgentMessage(role="user", content=user_prompt.strip()),
    ]
    input_payload = _build_input_payload(
        agent_id=agent_id,
        task=task,
        provider=resolved_provider,
        messages=messages,
        metadata={**(metadata or {}), "requested_provider": provider},
    )
    input_path.write_text(json.dumps(input_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    raw_output = _generate_output(
        agent_id=agent_id,
        task=task,
        messages=messages,
        provider=resolved_provider,
        dry_run_output=dry_run_output,
    )
    raw_output_path.write_text(raw_output.rstrip() + "\n", encoding="utf-8")

    parsed_output, parse_status, parse_error = _parse_agent_json(raw_output)
    parsed_output_path.write_text(json.dumps(parsed_output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    validation_path.write_text(
        _build_validation_report(
            run_id=run_id,
            agent_id=agent_id,
            task=task,
            provider=resolved_provider,
            parse_status=parse_status,
            parse_error=parse_error,
            input_path=input_path,
            raw_output_path=raw_output_path,
            parsed_output_path=parsed_output_path,
        ),
        encoding="utf-8",
    )

    return AgentRunResult(
        project_root=root,
        run_id=run_id,
        run_dir=run_dir,
        input_path=input_path,
        raw_output_path=raw_output_path,
        parsed_output_path=parsed_output_path,
        validation_path=validation_path,
        provider=resolved_provider,
        status="completed",
        parse_status=parse_status,
    )


def _build_input_payload(
    *,
    agent_id: str,
    task: str,
    provider: str,
    messages: list[AgentMessage],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "literary-engineering-workbench/agent-input/v0.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "task": task,
        "provider": provider,
        "model": _model_label(provider),
        "environment": {
            "api_base_env": "LEW_MODEL_API_BASE",
            "model_env": "LEW_MODEL_NAME",
            "api_key_env": "LEW_MODEL_API_KEY",
            "timeout_env": "LEW_MODEL_TIMEOUT",
            "temperature_env": "LEW_MODEL_TEMPERATURE",
            "max_tokens_env": "LEW_MODEL_MAX_TOKENS",
        },
        "messages": [{"role": message.role, "content": message.content} for message in messages],
        "metadata": metadata,
    }


def _generate_output(
    *,
    agent_id: str,
    task: str,
    messages: list[AgentMessage],
    provider: str,
    dry_run_output: dict[str, Any] | None,
) -> str:
    if provider == "dry-run":
        payload = dry_run_output or {
            "schema": "literary-engineering-workbench/agent-output/v0.1",
            "agent_id": agent_id,
            "task": task,
            "status": "dry_run",
            "findings": [],
            "recommendations": [
                "dry-run provider only records the agent contract. Switch to http-chat for real LLM output."
            ],
        }
        return "# Agent Dry Run Output\n\n```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```\n"
    if provider == "http-chat":
        return _http_chat(messages)
    raise ValueError(f"unknown agent provider: {provider}")


def _http_chat(messages: list[AgentMessage]) -> str:
    settings = get_model_settings(default_temperature=0.4, default_max_tokens=2500)
    if not settings.api_base or not settings.model:
        raise RuntimeError(
            "http-chat agent provider requires model config. Set LEW_MODEL_API_BASE and LEW_MODEL_NAME, "
            "or configure the global config file. Set LEW_MODEL_API_KEY, the configured api_key_env, or a saved profile api_key if needed."
        )
    if not settings.api_key:
        raise RuntimeError(
            f"http-chat agent provider requires an API key. Set LEW_MODEL_API_KEY, {settings.api_key_env}, or save api_key in the active profile."
        )
    payload = {
        "model": settings.model,
        "messages": [{"role": message.role, "content": message.content} for message in messages],
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {settings.api_key}"}
    req = request.Request(_chat_url(settings.api_base), data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=settings.timeout) as response:
            response_text = response.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"http-chat agent provider request failed: HTTP {exc.code}. {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"http-chat agent provider request failed: {exc.reason}") from exc
    data = json.loads(response_text)
    return _extract_chat_text(data)


def _parse_agent_json(raw_output: str) -> tuple[dict[str, Any], str, str]:
    candidates = [raw_output.strip()]
    candidates.extend(match.strip() for match in re.findall(r"```(?:json)?\s*(.*?)```", raw_output, flags=re.S | re.I))
    brace_match = re.search(r"(\{.*\})", raw_output, flags=re.S)
    if brace_match:
        candidates.append(brace_match.group(1).strip())

    errors = []
    for candidate in candidates:
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            errors.append(str(exc))
            continue
        if isinstance(data, dict):
            return data, "json_parsed", ""
        return {"value": data}, "json_parsed", ""

    return (
        {
            "schema": "literary-engineering-workbench/agent-parsed-output/v0.1",
            "parse_status": "not_json",
            "content": raw_output,
        },
        "not_json",
        "; ".join(errors[-3:]),
    )


def _build_validation_report(
    *,
    run_id: str,
    agent_id: str,
    task: str,
    provider: str,
    parse_status: str,
    parse_error: str,
    input_path: Path,
    raw_output_path: Path,
    parsed_output_path: Path,
) -> str:
    lines = [
        "# Agent Run Validation",
        "",
        f"- run_id: `{run_id}`",
        f"- agent_id: `{agent_id}`",
        f"- task: {task}",
        f"- provider: `{provider}`",
        f"- status: `completed`",
        f"- parse_status: `{parse_status}`",
        f"- input: `{input_path.as_posix()}`",
        f"- raw_output: `{raw_output_path.as_posix()}`",
        f"- parsed_output: `{parsed_output_path.as_posix()}`",
    ]
    if parse_error:
        lines.append(f"- parse_error: `{parse_error}`")
    lines.append("")
    if parse_status == "json_parsed":
        lines.append("Agent output contains machine-readable JSON and is ready for downstream schema checks.")
    else:
        lines.append("Agent output was preserved as raw text. Add a repair/schema pass before automated consumption.")
    return "\n".join(lines) + "\n"


def _extract_chat_text(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(first.get("text"), str):
                return first["text"]
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    raise RuntimeError("http-chat agent provider response did not contain generated text")


def _chat_url(api_base: str) -> str:
    base = api_base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _resolve_run_dir(root: Path, output_dir: Path | None, run_id: str) -> Path:
    if output_dir is None:
        return root / "agents" / "runs" / run_id
    return output_dir if output_dir.is_absolute() else root / output_dir


def _build_run_id(agent_id: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{agent_id}-{uuid.uuid4().hex[:8]}"


def _validate_agent_id(agent_id: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,96}", agent_id):
        raise ValueError("agent_id must use 1-96 ASCII letters, digits, dot, underscore, or hyphen")
    if ".." in agent_id:
        raise ValueError("agent_id must not contain '..'")


def _model_label(provider: str) -> str:
    if provider == "http-chat":
        return get_model_settings().model
    return provider
