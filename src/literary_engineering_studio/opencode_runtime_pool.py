"""Application-owned persistent OpenCode services separated by Agent role."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from typing import Any

from .opencode_binary import locate_opencode
from .opencode_client import OpenCodeClient, OpenCodeEndpoint
from .opencode_server import OpenCodeServer, OpenCodeServerHandle
from .process_manager import ProcessManager


VALID_ROLES = {"worker", "advisor", "steward"}


@dataclass(frozen=True)
class OpenCodeLease:
    role: str
    model: str
    client: OpenCodeClient
    component_id: str
    profile_path: Path
    generation: int
    reused: bool


@dataclass
class _RoleService:
    role: str
    model: str
    handle: OpenCodeServerHandle
    generation: int
    started_at: str
    last_used_at: float
    active_leases: int = 0
    restart_count: int = 0
    last_health_at: float = 0.0
    last_health: bool = True


class OpenCodeRuntimePool:
    """Keeps one permission-isolated OpenCode service warm per Agent role."""

    def __init__(
        self,
        config: dict[str, Any],
        process_manager: ProcessManager,
        *,
        idle_timeout_seconds: int | None = None,
    ):
        self.config = config
        self.process_manager = process_manager
        application = config.get("application") if isinstance(config.get("application"), dict) else {}
        settings = self.settings
        self.data_root = Path(str(application.get("data_root") or settings.get("data_root") or ".")).expanduser().resolve()
        configured_idle = int(settings.get("idle_timeout_seconds") or 900)
        self.idle_timeout_seconds = max(60, int(idle_timeout_seconds or configured_idle))
        self._services: dict[str, _RoleService] = {}
        self._generations: dict[str, int] = {}
        self._lock = threading.RLock()
        self._closed = False
        self._stop = threading.Event()
        self._reaper = threading.Thread(target=self._reap_loop, name="arcvellum-opencode-reaper", daemon=True)
        self._reaper.start()

    @property
    def settings(self) -> dict[str, Any]:
        runners = self.config.get("agent_runners") if isinstance(self.config.get("agent_runners"), dict) else {}
        value = runners.get("opencode") if isinstance(runners.get("opencode"), dict) else {}
        return value

    def model_for(self, role: str) -> str:
        normalized = _role(role)
        models = self.settings.get("models") if isinstance(self.settings.get("models"), dict) else {}
        value = str(models.get(normalized) or self.settings.get(f"{normalized}_model") or self.settings.get("model") or "").strip()
        if "/" not in value:
            raise RuntimeError(f"select an OpenCode provider/model for the {normalized} role")
        return value

    def acquire(self, role: str, workspace: Path, *, model: str = "") -> OpenCodeLease:
        normalized = _role(role)
        directory = workspace.expanduser().resolve()
        if not directory.is_dir():
            raise FileNotFoundError(f"OpenCode workspace not found: {directory}")
        selected_model = str(model or self.model_for(normalized)).strip()
        executable = locate_opencode(self.settings)
        if executable is None:
            raise RuntimeError("bundled OpenCode Runner is not installed")
        with self._lock:
            if self._closed:
                raise RuntimeError("OpenCode runtime pool is closed")
            service = self._services.get(normalized)
            reused = service is not None
            if service is not None and service.model != selected_model:
                if service.active_leases:
                    raise RuntimeError(f"cannot change {normalized} model while the role is active")
                self._stop_role_locked(normalized)
                service = None
                reused = False
            if service is not None and not self._healthy(service, force=True):
                restarts = service.restart_count + 1
                self._stop_role_locked(normalized, force=True)
                service = self._start_with_backoff_locked(normalized, selected_model, directory, restart_count=restarts)
                reused = False
            elif service is None:
                service = self._start_with_backoff_locked(normalized, selected_model, directory)
            service.active_leases += 1
            service.last_used_at = time.monotonic()
            endpoint = OpenCodeEndpoint(
                service.handle.endpoint.base_url,
                service.handle.endpoint.username,
                service.handle.endpoint.password,
                directory,
            )
            return OpenCodeLease(
                role=normalized,
                model=selected_model,
                client=OpenCodeClient(endpoint),
                component_id=service.handle.component_id,
                profile_path=service.handle.profile_path,
                generation=service.generation,
                reused=reused,
            )

    def release(self, lease: OpenCodeLease) -> None:
        with self._lock:
            service = self._services.get(lease.role)
            if service is None or service.generation != lease.generation:
                return
            service.active_leases = max(0, service.active_leases - 1)
            service.last_used_at = time.monotonic()

    def status(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "role": service.role,
                    "model": service.model,
                    "component_id": service.handle.component_id,
                    "pid": service.handle.process.pid,
                    "generation": service.generation,
                    "active_leases": service.active_leases,
                    "restart_count": service.restart_count,
                    "started_at": service.started_at,
                    "healthy": self._healthy(service),
                    "profile_path": str(service.handle.profile_path),
                }
                for service in self._services.values()
            ]

    def shutdown(self) -> None:
        self._stop.set()
        self._reaper.join(timeout=2)
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for role in list(self._services):
                self._stop_role_locked(role)

    def _start_locked(self, role: str, model: str, workspace: Path, *, restart_count: int = 0) -> _RoleService:
        executable = locate_opencode(self.settings)
        if executable is None:
            raise RuntimeError("bundled OpenCode Runner is not installed")
        role_root = self.data_root / "opencode" / "runtime" / role
        role_root.mkdir(parents=True, exist_ok=True)
        service_workspace = role_root / "service-workspace"
        service_workspace.mkdir(parents=True, exist_ok=True)
        generation = self._generations.get(role, 0) + 1
        self._generations[role] = generation
        server = OpenCodeServer(self.process_manager, executable=executable, shared_data_root=self.data_root)
        handle = server.start(
            component_id=f"opencode-{role}",
            workspace=service_workspace,
            run_root=role_root,
            profile_root=role_root / "profile",
            role=role,
            model=model,
        )
        service = _RoleService(
            role=role,
            model=model,
            handle=handle,
            generation=generation,
            started_at=datetime.now(timezone.utc).isoformat(),
            last_used_at=time.monotonic(),
            restart_count=restart_count,
        )
        self._services[role] = service
        return service

    def _start_with_backoff_locked(
        self,
        role: str,
        model: str,
        workspace: Path,
        *,
        restart_count: int = 0,
    ) -> _RoleService:
        error: RuntimeError | None = None
        for attempt in range(3):
            try:
                return self._start_locked(role, model, workspace, restart_count=restart_count + attempt)
            except RuntimeError as exc:
                error = exc
                if attempt < 2:
                    time.sleep(0.25 * (2 ** attempt))
        assert error is not None
        raise error

    def _stop_role_locked(self, role: str, *, force: bool = False) -> None:
        service = self._services.pop(role, None)
        if service is None:
            return
        if not force:
            try:
                service.handle.client.dispose()
            except RuntimeError:
                pass
        self.process_manager.stop(service.handle.component_id, force=force)

    def _healthy(self, service: _RoleService, *, force: bool = False) -> bool:
        now = time.monotonic()
        if not force and now - service.last_health_at < 2:
            return service.last_health
        try:
            payload = service.handle.client.health()
            healthy = payload.get("healthy") is not False and payload.get("ok") is not False
        except RuntimeError:
            healthy = False
        service.last_health = healthy
        service.last_health_at = now
        return healthy

    def _reap_loop(self) -> None:
        while not self._stop.wait(30):
            now = time.monotonic()
            with self._lock:
                for role, service in list(self._services.items()):
                    if service.active_leases == 0 and now - service.last_used_at >= self.idle_timeout_seconds:
                        self._stop_role_locked(role)


def _role(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in VALID_ROLES:
        raise ValueError(f"unsupported OpenCode role: {value}")
    return normalized
