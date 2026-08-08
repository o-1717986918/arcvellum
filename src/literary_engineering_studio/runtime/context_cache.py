"""Context cache key and partition contracts (AO-6, W6-7B).

The key is the identity of a rebuildable Studio context partition.  Cached
partitions are never formal project facts; Canon, character state, style,
word budget, rhythm/bridge or task identity changes invalidate reuse.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Literal

from ..protocols.violations import ContractViolation

CONTEXT_CACHE_KEY_SCHEMA = "arcvellum/context-cache-key/v1"


@dataclass(frozen=True)
class ContextCacheKey:
    project_revision: str
    scope_kind: Literal["chapter", "scene"]
    scope_id: str
    canon_digest: str
    character_state_digest: str
    style_mount_hash: str
    word_budget_revision: str
    rhythm_bridge_hash: str
    task_role: str
    task_kind: str

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": CONTEXT_CACHE_KEY_SCHEMA,
            "project_revision": self.project_revision,
            "scope_kind": self.scope_kind,
            "scope_id": self.scope_id,
            "canon_digest": self.canon_digest,
            "character_state_digest": self.character_state_digest,
            "style_mount_hash": self.style_mount_hash,
            "word_budget_revision": self.word_budget_revision,
            "rhythm_bridge_hash": self.rhythm_bridge_hash,
            "task_role": self.task_role,
            "task_kind": self.task_kind,
        }


CacheKeyViolation = ContractViolation


def context_cache_key_fingerprint(key: ContextCacheKey) -> str:
    """Return the stable content identity for a context cache key."""
    payload = json.dumps(
        key.as_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cache_key_violations(key: ContextCacheKey) -> tuple[CacheKeyViolation, ...]:
    """Return deterministic structural violations for a cache key."""
    issues: list[CacheKeyViolation] = []
    if key.scope_kind not in {"chapter", "scene"}:
        issues.append(
            CacheKeyViolation(
                code="invalid-scope-kind",
                message="scope_kind must be chapter or scene",
            )
        )
    for name in (
        "project_revision",
        "scope_id",
        "canon_digest",
        "character_state_digest",
        "style_mount_hash",
        "word_budget_revision",
        "rhythm_bridge_hash",
        "task_role",
        "task_kind",
    ):
        if not getattr(key, name):
            issues.append(
                CacheKeyViolation(
                    code="missing-field",
                    message=f"{name} must not be empty",
                )
            )
    return tuple(issues)


def partition_reusable(
    previous: ContextCacheKey,
    current: ContextCacheKey,
) -> bool:
    """A cached partition is reusable only when every identity field matches."""
    return previous == current
