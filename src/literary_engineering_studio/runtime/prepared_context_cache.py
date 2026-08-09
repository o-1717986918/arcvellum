"""Bounded in-memory cache for rebuildable prepared prompt snapshots."""

from __future__ import annotations

from collections import OrderedDict
import json
import threading
from typing import Any

from .context_budget import (
    ContextBudgetMode,
    ContextBudgetReport,
    ContextRiskLevel,
    ContextTaskKind,
)
from .context_cache import (
    ContextCacheKey,
    cache_key_violations,
    context_cache_key_fingerprint,
)
from .prompt_context import PreparedPromptContext


class PreparedContextCache:
    """Thread-safe LRU containing JSON projections, never project facts."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        max_entries: int = 32,
        routes: tuple[str, ...] = (),
        states: tuple[str, ...] = (),
    ):
        self.enabled = bool(enabled)
        self.max_entries = max(1, min(256, int(max_entries)))
        self.routes = _normalized_allowlist(routes)
        self.states = _normalized_allowlist(states)
        self._entries: OrderedDict[str, tuple[ContextCacheKey, str]] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._puts = 0
        self._evictions = 0
        self._bypasses = 0
        self._bypass_reasons: dict[str, int] = {}

    def allows(self, route: str, state: str) -> bool:
        if not self.enabled:
            return False
        return (
            (not self.routes or route in self.routes)
            and (not self.states or state in self.states)
        )

    def get(self, key: ContextCacheKey) -> PreparedPromptContext | None:
        if not self.enabled:
            return None
        _validate_key(key)
        fingerprint = context_cache_key_fingerprint(key)
        with self._lock:
            stored = self._entries.pop(fingerprint, None)
            if stored is None:
                self._misses += 1
                return None
            stored_key, encoded = stored
            if stored_key != key:
                self._misses += 1
                return None
            self._entries[fingerprint] = stored
            self._hits += 1
        return _decode_context(encoded)

    def put(self, key: ContextCacheKey, context: PreparedPromptContext) -> None:
        if not self.enabled:
            return
        _validate_key(key)
        encoded = _encode_context(context)
        fingerprint = context_cache_key_fingerprint(key)
        with self._lock:
            self._entries.pop(fingerprint, None)
            self._entries[fingerprint] = (key, encoded)
            self._puts += 1
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
                self._evictions += 1

    def record_bypass(self, reason: str) -> None:
        normalized = reason.strip() or "unspecified"
        with self._lock:
            self._bypasses += 1
            self._bypass_reasons[normalized] = (
                self._bypass_reasons.get(normalized, 0) + 1
            )

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "enabled": self.enabled,
                "routes": list(self.routes),
                "states": list(self.states),
                "entries": len(self._entries),
                "max_entries": self.max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "puts": self._puts,
                "evictions": self._evictions,
                "bypasses": self._bypasses,
                "bypass_reasons": dict(sorted(self._bypass_reasons.items())),
            }


def _validate_key(key: ContextCacheKey) -> None:
    violations = cache_key_violations(key)
    if violations:
        raise ValueError(
            "prepared context cache key is invalid: "
            + "; ".join(item.message for item in violations)
        )


def _encode_context(context: PreparedPromptContext) -> str:
    payload = {
        "rendered": context.rendered,
        "included_paths": list(context.included_paths),
        "omitted_paths": list(context.omitted_paths),
        "character_count": context.character_count,
        "sha256": context.sha256,
        "budget_report": context.budget_report_dict(),
        "unavailable_paths": list(context.unavailable_paths),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _decode_context(encoded: str) -> PreparedPromptContext:
    payload = json.loads(encoded)
    if not isinstance(payload, dict):
        raise ValueError("prepared context cache payload must be an object")
    return PreparedPromptContext(
        rendered=str(payload.get("rendered") or ""),
        included_paths=_strings(payload.get("included_paths")),
        omitted_paths=_strings(payload.get("omitted_paths")),
        character_count=int(payload.get("character_count") or 0),
        sha256=str(payload.get("sha256") or ""),
        budget_report=_decode_budget_report(payload.get("budget_report")),
        unavailable_paths=_strings(payload.get("unavailable_paths")),
    )


def _decode_budget_report(value: object) -> ContextBudgetReport | None:
    if not isinstance(value, dict) or not value:
        return None
    fields: dict[str, Any] = dict(value)
    fields.pop("schema", None)
    fields["mode"] = ContextBudgetMode(str(fields["mode"]))
    fields["requested_mode"] = ContextBudgetMode(str(fields["requested_mode"]))
    fields["task_kind"] = ContextTaskKind(str(fields["task_kind"]))
    fields["risk_level"] = ContextRiskLevel(str(fields["risk_level"]))
    return ContextBudgetReport(**fields)


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("prepared context cache path fields must be arrays")
    return tuple(str(item) for item in value)


def _normalized_allowlist(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))
