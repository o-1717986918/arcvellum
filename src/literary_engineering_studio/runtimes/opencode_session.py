"""Role-aware OpenCode model and client-session preparation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..opencode_profiles import OpenCodeRole, agent_id_for_role


@dataclass(frozen=True)
class OpenCodeRoleClient:
    lease: Any
    handle: Any
    client: Any
    component_id: str


def configured_role(settings: dict[str, object]) -> OpenCodeRole:
    return OpenCodeRole(
        str(settings.get("role") or OpenCodeRole.WORKER.value).strip().lower()
    )


def selected_model(
    settings: dict[str, object],
    role: OpenCodeRole | None = None,
) -> str:
    selected_role = role or configured_role(settings)
    models = settings.get("models") if isinstance(settings.get("models"), dict) else {}
    orchestration_fallback = (
        models.get(OpenCodeRole.WORKER.value) or settings.get("worker_model")
        if selected_role in {OpenCodeRole.PLANNER, OpenCodeRole.REVIEWER}
        else ""
    )
    return str(
        models.get(selected_role.value)
        or settings.get(f"{selected_role.value}_model")
        or orchestration_fallback
        or settings.get("model")
        or ""
    ).strip()


def execution_identity(
    settings: dict[str, object],
) -> tuple[OpenCodeRole, str, str]:
    role = configured_role(settings)
    model = selected_model(settings, role)
    if "/" not in model:
        raise RuntimeError("OpenCode requires an explicit provider/model-id connection")
    return role, model, agent_id_for_role(role)


def open_role_client(
    *,
    runtime_pool,
    server,
    workspace: Path,
    run_root: Path,
    component_id: str,
    role: OpenCodeRole,
    model: str,
) -> OpenCodeRoleClient:
    if runtime_pool is not None:
        lease = runtime_pool.acquire(role.value, workspace, model=model)
        return OpenCodeRoleClient(
            lease=lease,
            handle=None,
            client=lease.client,
            component_id=lease.component_id,
        )
    if server is None:
        raise RuntimeError("OpenCode server is unavailable")
    handle = server.start(
        component_id=component_id,
        workspace=workspace,
        run_root=run_root,
        role=role.value,
        model=model,
    )
    return OpenCodeRoleClient(
        lease=None,
        handle=handle,
        client=handle.client,
        component_id=component_id,
    )
