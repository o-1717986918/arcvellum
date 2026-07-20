"""Host-platform handoff runtime."""

from __future__ import annotations

from pathlib import Path

from .base import AgentRuntime, RuntimeAvailability, RuntimeResult


class HostAgentRuntime(AgentRuntime):
    runtime_id = "host-agent"

    def availability(self) -> RuntimeAvailability:
        return RuntimeAvailability(self.runtime_id, True, "host-platform", "waiting for the connected host Agent")

    def build_command(self, workspace: Path):
        return ()

    def execute(self, workspace: Path, prompt_path: Path, run_root: Path, *, timeout: int) -> RuntimeResult:
        return RuntimeResult(
            runtime=self.runtime_id,
            status="waiting_host_agent",
            returncode=None,
            command=(),
            output_path=prompt_path,
            message="task sandbox prepared for a connected Codex/Claude host Agent",
        )

