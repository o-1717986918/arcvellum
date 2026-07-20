"""OpenCode localhost sidecar startup with isolated application-owned state."""

from __future__ import annotations

from dataclasses import dataclass
import base64
from pathlib import Path
import secrets
import socket

from .opencode_client import OpenCodeClient, OpenCodeEndpoint
from .opencode_profiles import write_profile
from .process_manager import ProcessManager, ProcessRecord, ProcessSpec


@dataclass(frozen=True)
class OpenCodeServerHandle:
    component_id: str
    endpoint: OpenCodeEndpoint
    client: OpenCodeClient
    process: ProcessRecord
    profile_path: Path


class OpenCodeServer:
    def __init__(self, process_manager: ProcessManager, *, executable: Path, shared_data_root: Path):
        self.process_manager = process_manager
        self.executable = executable.expanduser().resolve()
        self.shared_data_root = shared_data_root.expanduser().resolve()

    def start(
        self,
        *,
        component_id: str,
        workspace: Path,
        run_root: Path,
        role: str,
        model: str,
    ) -> OpenCodeServerHandle:
        profile_root = run_root / "opencode-profile"
        profile_path = write_profile(profile_root, role=role, model=model)
        state_root = self.shared_data_root / "opencode"
        for path in (state_root / "config", state_root / "data", state_root / "cache", state_root / "state"):
            path.mkdir(parents=True, exist_ok=True)
        port = _free_port()
        username = "studio"
        password = secrets.token_urlsafe(32)
        endpoint = OpenCodeEndpoint(f"http://127.0.0.1:{port}", username, password, workspace.resolve())
        auth = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        environment = {
            "OPENCODE_SERVER_USERNAME": username,
            "OPENCODE_SERVER_PASSWORD": password,
            "OPENCODE_CONFIG": str(profile_path),
            "OPENCODE_CONFIG_DIR": str(profile_root),
            "OPENCODE_DISABLE_CLAUDE_CODE_PROMPT": "1",
            "XDG_CONFIG_HOME": str(state_root / "config"),
            "XDG_DATA_HOME": str(state_root / "data"),
            "XDG_CACHE_HOME": str(state_root / "cache"),
            "XDG_STATE_HOME": str(state_root / "state"),
        }
        spec = ProcessSpec(
            component_id=component_id,
            kind="agent-runner-sidecar",
            command=(
                str(self.executable),
                "serve",
                "--pure",
                "--hostname",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "WARN",
            ),
            cwd=workspace.resolve(),
            environment=environment,
            readiness_url=endpoint.base_url + "/global/health",
            readiness_headers={"Authorization": f"Basic {auth}"},
            readiness_timeout=30,
            graceful_timeout=8,
        )
        record = self.process_manager.start(spec)
        return OpenCodeServerHandle(
            component_id=component_id,
            endpoint=endpoint,
            client=OpenCodeClient(endpoint),
            process=record,
            profile_path=profile_path,
        )

    def stop(self, handle: OpenCodeServerHandle) -> None:
        try:
            handle.client.dispose()
        except RuntimeError:
            pass
        self.process_manager.stop(handle.component_id)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])
