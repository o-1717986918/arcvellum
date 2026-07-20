"""Claude Code non-interactive adapter."""

from pathlib import Path

from .base import AgentRuntime, executable_prefix, resolve_executable


class ClaudeCodeRuntime(AgentRuntime):
    runtime_id = "claude-code"

    def build_command(self, workspace: Path):
        executable = resolve_executable(str(self.settings.get("executable") or "claude"))
        permission_mode = str(self.settings.get("permission_mode") or "acceptEdits")
        return (
            *executable_prefix(executable),
            "-p",
            "--output-format",
            "stream-json",
            "--permission-mode",
            permission_mode,
            "--tools",
            "Read,Write,Edit,Glob,Grep",
            "--no-session-persistence",
        )
