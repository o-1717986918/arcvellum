"""Secret-free model connection projections owned by Agent Runners."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


MODEL_CONNECTION_SCHEMA = "literary-engineering-studio/model-connection/v0.3"


@dataclass(frozen=True)
class ModelConnection:
    connection_id: str
    provider_family: str
    connection_method: str
    agent_runner: str
    authentication_state: str = "unknown"
    selected_model: str = ""
    available_models: tuple[str, ...] = ()
    endpoint_health: str = "unknown"
    privacy_class: str = "cloud"
    last_probe_at: str = ""
    failure_category: str = ""
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema"] = MODEL_CONNECTION_SCHEMA
        payload["available_models"] = list(self.available_models)
        return payload


def model_connection_status(config: dict[str, Any]) -> list[dict[str, Any]]:
    section = config.get("model_connections", {})
    records = section.get("connections", []) if isinstance(section, dict) else []
    if not isinstance(records, list):
        return []
    results: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        connection_id = str(record.get("connection_id") or "").strip()
        provider_family = str(record.get("provider_family") or "").strip()
        agent_runner = str(record.get("agent_runner") or "").strip()
        if not connection_id or not provider_family or not agent_runner:
            continue
        connection = ModelConnection(
            connection_id=connection_id,
            provider_family=provider_family,
            connection_method=str(record.get("connection_method") or "runner-managed"),
            agent_runner=agent_runner,
            authentication_state=str(record.get("authentication_state") or "unknown"),
            selected_model=str(record.get("selected_model") or ""),
            available_models=tuple(str(item) for item in record.get("available_models") or []),
            endpoint_health=str(record.get("endpoint_health") or "unknown"),
            privacy_class=str(record.get("privacy_class") or "cloud"),
            last_probe_at=str(record.get("last_probe_at") or ""),
            failure_category=str(record.get("failure_category") or ""),
            detail=str(record.get("detail") or ""),
        )
        results.append(connection.as_dict())
    return results
