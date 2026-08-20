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
        connection = _model_connection(record)
        if connection is not None:
            results.append(connection.as_dict())
    return results


def _model_connection(record: object) -> ModelConnection | None:
    if not isinstance(record, dict):
        return None
    connection_id = _record_text(record, "connection_id").strip()
    provider_family = _record_text(record, "provider_family").strip()
    agent_runner = _record_text(record, "agent_runner").strip()
    if not all((connection_id, provider_family, agent_runner)):
        return None
    return ModelConnection(
        connection_id=connection_id,
        provider_family=provider_family,
        connection_method=_record_text(record, "connection_method", "runner-managed"),
        agent_runner=agent_runner,
        authentication_state=_record_text(record, "authentication_state", "unknown"),
        selected_model=_record_text(record, "selected_model"),
        available_models=_record_text_tuple(record, "available_models"),
        endpoint_health=_record_text(record, "endpoint_health", "unknown"),
        privacy_class=_record_text(record, "privacy_class", "cloud"),
        last_probe_at=_record_text(record, "last_probe_at"),
        failure_category=_record_text(record, "failure_category"),
        detail=_record_text(record, "detail"),
    )


def _record_text(record: dict[str, Any], key: str, default: str = "") -> str:
    return str(record.get(key) or default)


def _record_text_tuple(record: dict[str, Any], key: str) -> tuple[str, ...]:
    return tuple(str(item) for item in record.get(key) or [])
