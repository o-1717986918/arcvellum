"""Short-lived OpenCode control sessions for provider catalog and auth setup."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import Any, Iterator

from .config import default_data_root, save_config
from .opencode_binary import locate_opencode
from .opencode_server import OpenCodeServer, OpenCodeServerHandle
from .process_manager import ProcessManager


def provider_catalog(config: dict[str, Any]) -> dict[str, Any]:
    with _control_session(config) as handle:
        payload = handle.client.providers()
        auth_methods = handle.client.provider_auth_methods()
        connected = {str(item) for item in payload.get("connected") or []}
        defaults = payload.get("default") if isinstance(payload.get("default"), dict) else {}
        providers: list[dict[str, Any]] = []
        for item in payload.get("all") or []:
            if not isinstance(item, dict):
                continue
            provider_id = str(item.get("id") or "")
            if not provider_id:
                continue
            models = item.get("models") if isinstance(item.get("models"), dict) else {}
            model_items = []
            for model_id, detail in models.items():
                values = detail if isinstance(detail, dict) else {}
                model_items.append(
                    {
                        "id": str(model_id),
                        "qualified_id": f"{provider_id}/{model_id}",
                        "name": str(values.get("name") or model_id),
                        "context": _context_window(values),
                    }
                )
            methods = auth_methods.get(provider_id) if isinstance(auth_methods, dict) else []
            providers.append(
                {
                    "id": provider_id,
                    "name": str(item.get("name") or provider_id),
                    "connected": provider_id in connected,
                    "default_model": str(defaults.get(provider_id) or ""),
                    "auth_methods": _public_auth_methods(methods),
                    "models": model_items if provider_id in connected else [],
                    "model_count": len(model_items),
                }
            )
        providers.sort(key=lambda item: (not item["connected"], item["name"].lower()))
        return {
            "runner": "opencode",
            "version": str(handle.client.health().get("version") or ""),
            "selected_model": _selected_model(config),
            "providers": providers,
            "connected_provider_count": sum(1 for item in providers if item["connected"]),
            "available_model_count": sum(len(item["models"]) for item in providers),
        }


def set_api_credential(config: dict[str, Any], provider_id: str, credential: str) -> dict[str, Any]:
    normalized_id = _validated_provider_id(provider_id)
    secret = str(credential or "").strip()
    if not secret or len(secret) > 8192:
        raise ValueError("credential must contain between 1 and 8192 characters")
    with _control_session(config) as handle:
        if not handle.client.set_auth(normalized_id, {"type": "api", "key": secret}):
            raise RuntimeError("OpenCode rejected the provider credential")
    return provider_catalog(config)


def disconnect_provider(config: dict[str, Any], provider_id: str) -> dict[str, Any]:
    normalized_id = _validated_provider_id(provider_id)
    if normalized_id == "opencode":
        raise ValueError("the built-in OpenCode starter provider cannot be disconnected")
    with _control_session(config) as handle:
        if not handle.client.delete_auth(normalized_id):
            raise RuntimeError("OpenCode rejected the provider disconnect request")

    fallback = "opencode/big-pickle"
    runners = config.setdefault("agent_runners", {})
    opencode = runners.setdefault("opencode", {})
    selected_model = str(opencode.get("model") or "")
    if selected_model.startswith(normalized_id + "/"):
        opencode["model"] = fallback
        section = config.setdefault("model_connections", {})
        connections = section.setdefault("connections", [])
        record = next(
            (
                item
                for item in connections
                if isinstance(item, dict) and item.get("connection_id") == "opencode-starter"
            ),
            None,
        )
        if record is None:
            record = {"connection_id": "opencode-starter", "agent_runner": "opencode"}
            connections.append(record)
        record.update(
            {
                "provider_family": "opencode",
                "connection_method": "bundled-free-provider",
                "authentication_state": "runner-managed",
                "selected_model": fallback,
                "endpoint_health": "probe-required",
                "privacy_class": "cloud",
                "detail": "Starter connection; availability and limits are verified by the bundled Runner.",
            }
        )
    save_config(config)
    return provider_catalog(config)


def select_model(config: dict[str, Any], qualified_model: str) -> dict[str, Any]:
    model = str(qualified_model or "").strip()
    if "/" not in model or any(char.isspace() for char in model):
        raise ValueError("model must use provider/model-id format")
    runners = config.setdefault("agent_runners", {})
    opencode = runners.setdefault("opencode", {})
    opencode["model"] = model
    section = config.setdefault("model_connections", {})
    connections = section.setdefault("connections", [])
    record = next(
        (item for item in connections if isinstance(item, dict) and item.get("connection_id") == "opencode-starter"),
        None,
    )
    if record is None:
        record = {
            "connection_id": "opencode-starter",
            "provider_family": model.split("/", 1)[0],
            "connection_method": "opencode-auth",
            "agent_runner": "opencode",
        }
        connections.append(record)
    record["provider_family"] = model.split("/", 1)[0]
    record["selected_model"] = model
    record["authentication_state"] = "runner-managed"
    record["endpoint_health"] = "probe-required"
    save_config(config)
    return {"selected_model": model, "saved": True}


@contextmanager
def _control_session(config: dict[str, Any]) -> Iterator[OpenCodeServerHandle]:
    settings = _opencode_settings(config)
    executable = locate_opencode(settings)
    if executable is None:
        raise RuntimeError("OpenCode is not installed; install the bundled Runner first")
    model = str(settings.get("model") or "opencode/big-pickle")
    data_root = Path(str(settings.get("data_root") or default_data_root())).expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="les-opencode-control-") as temporary:
        root = Path(temporary)
        workspace = root / "workspace"
        workspace.mkdir()
        manager = ProcessManager(root / "logs")
        server = OpenCodeServer(manager, executable=executable, shared_data_root=data_root)
        handle = server.start(
            component_id="opencode-control",
            workspace=workspace,
            run_root=root / "run",
            role="advisor",
            model=model,
        )
        try:
            yield handle
        finally:
            server.stop(handle)
            manager.shutdown()


def _opencode_settings(config: dict[str, Any]) -> dict[str, object]:
    runners = config.get("agent_runners", {}) if isinstance(config.get("agent_runners"), dict) else {}
    values = runners.get("opencode", {}) if isinstance(runners.get("opencode"), dict) else {}
    return values


def _selected_model(config: dict[str, Any]) -> str:
    return str(_opencode_settings(config).get("model") or "")


def _validated_provider_id(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for char in normalized):
        raise ValueError("invalid OpenCode provider id")
    return normalized


def _public_auth_methods(value: Any) -> list[dict[str, str]]:
    methods: list[dict[str, str]] = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        methods.append({"type": str(item.get("type") or ""), "label": str(item.get("label") or item.get("type") or "")})
    return methods


def _context_window(values: dict[str, Any]) -> int:
    limit = values.get("limit") if isinstance(values.get("limit"), dict) else {}
    return int(limit.get("context") or 0)
