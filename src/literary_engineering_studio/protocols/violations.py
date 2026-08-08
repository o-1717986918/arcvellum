"""Shared immutable violation values for deterministic contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContractViolation:
    code: str
    message: str


@dataclass(frozen=True)
class RelatedContractViolation(ContractViolation):
    related: tuple[str, ...] = ()


__all__ = ["ContractViolation", "RelatedContractViolation"]
