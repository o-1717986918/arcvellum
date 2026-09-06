"""Neutral runtime-pool implementation for runtimes without shared sidecars."""

from __future__ import annotations

from typing import Any


class NullRuntimePool:
    """No-op application port used when registered runtimes own their execution."""

    def status(self) -> dict[str, Any]:
        return {
            "runtime": "none",
            "running": 0,
            "sessions": [],
            "detail": "Registered runtimes own their process lifecycle.",
        }

    def shutdown(self) -> None:
        return None


__all__ = ["NullRuntimePool"]
