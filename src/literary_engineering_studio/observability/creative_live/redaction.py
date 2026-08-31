"""Redact secrets and host-specific details before Runtime data reaches a client."""

from __future__ import annotations

import re
from typing import Any


_RESTRICTED_KEYS = {
    "api_key", "authorization", "credential", "password", "private",
    "raw_prompt", "secret", "system_prompt", "token",
}
_SECRET = re.compile(r"(?:sk-|ghp_)[A-Za-z0-9_-]{16,}")
_WINDOWS_PATH = re.compile(r"[A-Za-z]:[\\/][^\s'\"`]+")


def public_runtime_data(value: Any, *, maximum_text: int = 2_100_000) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "<redacted>"
                if str(key).casefold() in _RESTRICTED_KEYS
                else public_runtime_data(item, maximum_text=maximum_text)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [public_runtime_data(item, maximum_text=maximum_text) for item in value]
    if isinstance(value, tuple):
        return [public_runtime_data(item, maximum_text=maximum_text) for item in value]
    if isinstance(value, str):
        text = _SECRET.sub("<redacted-secret>", value)
        text = _WINDOWS_PATH.sub("<redacted-path>", text)
        return text[:maximum_text]
    return value


__all__ = ["public_runtime_data"]
