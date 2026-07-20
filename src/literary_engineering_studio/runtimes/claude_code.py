"""Claude Code non-interactive Agent Runner adapter."""

import json
from pathlib import Path
import subprocess
from typing import Any

from .base import AgentRunnerCapabilities, AgentRuntime, executable_prefix, resolve_executable


class ClaudeCodeRuntime(AgentRuntime):
    runtime_id = "claude-code"

    def build_command(self, workspace: Path):
        executable = resolve_executable(str(self.settings.get("executable") or "claude"))
        permission_mode = str(self.settings.get("permission_mode") or "acceptEdits")
        model = str(self.settings.get("model") or "").strip()
        command = [
            *executable_prefix(executable),
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--safe-mode",
            "--disable-slash-commands",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--permission-mode",
            permission_mode,
            "--tools",
            "Read,Write,Edit,Glob,Grep",
            "--disallowedTools",
            "Bash,Task,WebFetch,WebSearch,Skill",
            "--no-session-persistence",
        ]
        if model:
            command.extend(["--model", model])
        max_budget = self.settings.get("max_budget_usd")
        if max_budget not in {None, ""}:
            command.extend(["--max-budget-usd", str(max_budget)])
        return tuple(command)

    def capabilities(self) -> AgentRunnerCapabilities:
        availability = self.availability()
        authentication_state = "not-probed"
        provider = ""
        auth_detail = ""
        if availability.available:
            executable = resolve_executable(str(self.settings.get("executable") or "claude"))
            try:
                completed = subprocess.run(
                    [*executable_prefix(executable), "auth", "status"],
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
                payload = json.loads(completed.stdout) if completed.returncode == 0 else {}
                if isinstance(payload, dict) and payload.get("loggedIn") is True:
                    authentication_state = "authenticated"
                    provider = str(payload.get("apiProvider") or "")
                    auth_detail = str(payload.get("authMethod") or "authenticated")
                else:
                    authentication_state = "unauthenticated"
                    auth_detail = completed.stderr.strip() or "Claude Code is not logged in"
            except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
                authentication_state = "probe-failed"
                auth_detail = str(exc)
        model = str(self.settings.get("model") or "").strip()
        ready = availability.available and authentication_state == "authenticated" and bool(model)
        if not availability.available:
            readiness = "unavailable"
        elif authentication_state != "authenticated":
            readiness = "authentication-required"
        elif not model:
            readiness = "model-selection-required"
        else:
            readiness = "ready-for-live-probe"
        detail = availability.detail
        if auth_detail:
            detail += f"; {auth_detail}"
        if not model:
            detail += "; explicit model selection required"
        return AgentRunnerCapabilities(
            runner_id=self.runtime_id,
            version=availability.detail if availability.available else "",
            available=ready,
            readiness_state=readiness,
            authentication_state=authentication_state,
            provider=provider,
            selected_model=model,
            execution_modes=("single-task", "stream-json"),
            structured_output=True,
            streaming_events=True,
            model_selection=True,
            read_control=True,
            edit_control=True,
            shell_control=True,
            subagent_control=True,
            web_control=True,
            external_directory_control=True,
            stop=True,
            retry=True,
            resume=False,
            detail=detail,
        )

    def normalize_output_line(self, line: str) -> tuple[tuple[str, dict[str, Any]], ...]:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return (("runner.output.delta", {"text": line.rstrip("\r\n")}),)
        if not isinstance(payload, dict):
            return ()
        kind = str(payload.get("type") or "")
        events: list[tuple[str, dict[str, Any]]] = []
        if kind == "system" and payload.get("subtype") == "init":
            events.append(
                (
                    "runner.ready",
                    {
                        "runner_id": self.runtime_id,
                        "session_id": str(payload.get("session_id") or ""),
                        "model": str(payload.get("model") or ""),
                    },
                )
            )
        elif kind == "stream_event":
            stream = payload.get("event") if isinstance(payload.get("event"), dict) else {}
            stream_type = str(stream.get("type") or "")
            delta = stream.get("delta") if isinstance(stream.get("delta"), dict) else {}
            if stream_type == "content_block_delta" and delta.get("type") == "text_delta":
                events.append(("agent.message.delta", {"text": str(delta.get("text") or "")}))
            elif stream_type == "content_block_start":
                block = stream.get("content_block") if isinstance(stream.get("content_block"), dict) else {}
                if block.get("type") == "tool_use":
                    events.append(
                        (
                            "tool.started",
                            {"tool": str(block.get("name") or ""), "tool_use_id": str(block.get("id") or "")},
                        )
                    )
            elif stream_type == "message_delta" and isinstance(stream.get("usage"), dict):
                events.append(("usage.updated", {"usage": stream["usage"]}))
        elif kind == "assistant":
            message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
            for block in message.get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    events.append(
                        (
                            "tool.started",
                            {"tool": str(block.get("name") or ""), "tool_use_id": str(block.get("id") or "")},
                        )
                    )
        elif kind == "result":
            if isinstance(payload.get("usage"), dict) or payload.get("total_cost_usd") is not None:
                events.append(
                    (
                        "usage.updated",
                        {
                            "usage": payload.get("usage") or {},
                            "cost_usd": payload.get("total_cost_usd"),
                            "duration_ms": payload.get("duration_ms"),
                            "model_usage": payload.get("modelUsage") or {},
                        },
                    )
                )
            events.append(
                (
                    "agent.message.completed",
                    {"is_error": bool(payload.get("is_error")), "result": str(payload.get("result") or "")},
                )
            )
        return tuple(events)
