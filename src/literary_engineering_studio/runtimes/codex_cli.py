"""Codex CLI non-interactive adapter."""

from pathlib import Path

from .base import AgentRuntime, executable_prefix, resolve_executable


class CodexCliRuntime(AgentRuntime):
    runtime_id = "codex-cli"

    def build_command(self, workspace: Path):
        executable = resolve_executable(str(self.settings.get("executable") or "codex"))
        sandbox = str(self.settings.get("sandbox") or "workspace-write")
        return (
            *executable_prefix(executable),
            "exec",
            "--json",
            "--ephemeral",
            "--sandbox",
            sandbox,
            "--skip-git-repo-check",
            "-C",
            str(workspace),
            "-",
        )
