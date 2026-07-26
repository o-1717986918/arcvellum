"""Explicit registry for capability handlers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .contracts import CapabilityId, HandlerOutput


CapabilityHandler = Callable[[Any, dict[str, Any]], HandlerOutput]


@dataclass(frozen=True)
class RegisteredCapability:
    capability_id: str
    handler: CapabilityHandler


class CapabilityRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, CapabilityHandler] = {}

    def register(self, capability_id: str | CapabilityId, handler: CapabilityHandler) -> None:
        normalized = capability_id.value if isinstance(capability_id, CapabilityId) else str(capability_id)
        CapabilityId(normalized)
        if normalized in self._handlers:
            raise ValueError(f"capability already registered: {normalized}")
        self._handlers[normalized] = handler

    def resolve(self, capability_id: str) -> CapabilityHandler:
        try:
            return self._handlers[capability_id]
        except KeyError as exc:
            raise LookupError(f"capability handler is not registered: {capability_id}") from exc

    def registered_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))
