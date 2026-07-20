"""Host-platform handoff runtime."""

from __future__ import annotations

from pathlib import Path

from .base import AgentRunnerCapabilities, AgentRuntime, RuntimeAvailability, RuntimeResult


class HostAgentRuntime(AgentRuntime):
    runtime_id = "host-agent"

    def availability(self) -> RuntimeAvailability:
        return RuntimeAvailability(self.runtime_id, True, "host-platform", "waiting for the connected host Agent")

    def build_command(self, workspace: Path):
        return ()

    def capabilities(self) -> AgentRunnerCapabilities:
        return AgentRunnerCapabilities(
            runner_id=self.runtime_id,
            version="host-platform",
            available=True,
            readiness_state="handoff-ready",
            authentication_state="host-owned",
            provider="host-owned",
            selected_model="host-owned",
            execution_modes=("handoff",),
            structured_output=True,
            streaming_events=False,
            model_selection=False,
            read_control=False,
            edit_control=False,
            shell_control=False,
            subagent_control=False,
            web_control=False,
            external_directory_control=False,
            stop=False,
            retry=True,
            resume=False,
            detail="waiting for the connected host Agent",
        )

    def execute(
        self,
        workspace: Path,
        prompt_path: Path,
        run_root: Path,
        *,
        timeout: int,
        event_sink=None,
        cancel_event=None,
    ) -> RuntimeResult:
        return RuntimeResult(
            runtime=self.runtime_id,
            status="waiting_host_agent",
            returncode=None,
            command=(),
            output_path=prompt_path,
            message="task sandbox prepared for a connected Codex/Claude host Agent",
        )
