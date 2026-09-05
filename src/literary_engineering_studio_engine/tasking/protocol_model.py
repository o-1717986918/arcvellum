"""Value object for one human-readable workflow protocol."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ProtocolRoute:
    key: str
    title: str
    purpose: str
    read: tuple[str, ...]
    preflight: tuple[str, ...]
    cli_chain: tuple[str, ...]
    platform_agent_handoffs: tuple[str, ...]
    completion_gates: tuple[str, ...]
    forbidden_shortcuts: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


__all__ = ["ProtocolRoute"]
