"""Explicit Runtime descriptors and immutable registry composition."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .base import AgentRuntimePort, SubprocessRuntimeBase


@dataclass(frozen=True)
class RuntimeFactoryContext:
    """Optional infrastructure supplied by the application composition root."""

    runtime_pool: object | None = None
    role: str | None = None


RuntimeFactory = Callable[
    [dict[str, object], RuntimeFactoryContext],
    AgentRuntimePort,
]


@dataclass(frozen=True)
class RuntimeDescriptor:
    runtime_id: str
    implementation: type[SubprocessRuntimeBase]
    factory: RuntimeFactory

    def create(
        self,
        settings: Mapping[str, object],
        context: RuntimeFactoryContext | None = None,
    ) -> AgentRuntimePort:
        effective = dict(settings)
        factory_context = context or RuntimeFactoryContext()
        if factory_context.role is not None:
            effective["role"] = factory_context.role
        runtime = self.factory(effective, factory_context)
        if runtime.runtime_id != self.runtime_id:
            raise ValueError(
                f"runtime factory returned {runtime.runtime_id!r} for {self.runtime_id!r}"
            )
        return runtime


class RuntimeRegistry:
    """Immutable descriptor catalog; extensions create a new registry value."""

    def __init__(self, descriptors: Iterable[RuntimeDescriptor]):
        values: dict[str, RuntimeDescriptor] = {}
        for descriptor in descriptors:
            runtime_id = _runtime_id(descriptor.runtime_id)
            if runtime_id in values:
                raise ValueError(f"duplicate Agent runtime descriptor: {runtime_id}")
            if runtime_id != descriptor.runtime_id:
                raise ValueError(f"Agent runtime id must be normalized: {descriptor.runtime_id}")
            values[runtime_id] = descriptor
        self._descriptors = MappingProxyType(values)

    def ids(self) -> tuple[str, ...]:
        return tuple(self._descriptors)

    def descriptor(self, runtime_id: str) -> RuntimeDescriptor:
        normalized = _runtime_id(runtime_id)
        try:
            return self._descriptors[normalized]
        except KeyError as exc:
            raise ValueError(f"unknown Agent runtime: {runtime_id}") from exc

    def create(
        self,
        runtime_id: str,
        settings: Mapping[str, object],
        context: RuntimeFactoryContext | None = None,
    ) -> AgentRuntimePort:
        return self.descriptor(runtime_id).create(settings, context)

    def runtime_types(self) -> Mapping[str, type[SubprocessRuntimeBase]]:
        return MappingProxyType(
            {
                runtime_id: descriptor.implementation
                for runtime_id, descriptor in self._descriptors.items()
            }
        )

    def with_descriptor(self, descriptor: RuntimeDescriptor) -> RuntimeRegistry:
        return RuntimeRegistry((*self._descriptors.values(), descriptor))

    def cache_key(self) -> str:
        return "|".join(
            f"{runtime_id}:{descriptor.implementation.__module__}."
            f"{descriptor.implementation.__qualname__}"
            for runtime_id, descriptor in self._descriptors.items()
        )


def runtime_descriptor(
    implementation: type[SubprocessRuntimeBase],
    factory: RuntimeFactory | None = None,
) -> RuntimeDescriptor:
    return RuntimeDescriptor(
        runtime_id=_runtime_id(implementation.runtime_id),
        implementation=implementation,
        factory=factory or _constructor_factory(implementation),
    )


def _constructor_factory(
    implementation: type[SubprocessRuntimeBase],
) -> RuntimeFactory:
    def create(
        settings: dict[str, object],
        _context: RuntimeFactoryContext,
    ) -> AgentRuntimePort:
        return implementation(settings)

    return create


def _runtime_id(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized or normalized != str(value or ""):
        raise ValueError(f"invalid Agent runtime id: {value!r}")
    return normalized


__all__ = [
    "RuntimeDescriptor",
    "RuntimeFactory",
    "RuntimeFactoryContext",
    "RuntimeRegistry",
    "runtime_descriptor",
]
