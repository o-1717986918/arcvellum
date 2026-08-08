"""Context cache key and partition contracts (AO-6, W6-7B).

The key is the identity of a rebuildable Studio context partition.  Cached
partitions are never formal project facts; Canon, character state, style,
word budget, rhythm/bridge or task identity changes invalidate reuse.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable
from typing import Literal

from ..contracts import TaskPackage, normalize_relative_path
from ..protocols.violations import ContractViolation
from .context_budget import TaskContextBudget

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


def build_context_cache_key(
    task: TaskPackage,
    workspace: Path,
    paths: Iterable[str],
    *,
    budget: TaskContextBudget | None,
    mandatory_paths: Iterable[str],
    exact_on_demand_paths: Iterable[str],
) -> tuple[ContextCacheKey | None, str]:
    """Build a key from declared task inputs; never discover extra project files."""

    trace_path = _declared_trace_path(task, workspace)
    if trace_path is None:
        return None, "context-trace-not-declared"
    trace = _read_trace(trace_path)
    if trace is None:
        return None, "context-trace-unavailable"
    scene_id = str(task.payload.get("scene_id") or "").strip()
    if not scene_id or scene_id != str(trace.get("scene_id") or "").strip():
        return None, "scene-identity-mismatch"
    revisions = _trace_revisions(trace)
    if revisions is None:
        return None, "context-trace-revisions-incomplete"
    try:
        content_digest = _declared_content_digest(workspace, paths)
    except (OSError, ValueError):
        return None, "declared-context-digest-failed"
    compound_revision = _digest(
        {
            "trace_project_revision": revisions["project_revision"],
            "declared_content_digest": content_digest,
            "context_tiers": {
                "mandatory": list(_unique(mandatory_paths)),
                "exact_on_demand": list(_unique(exact_on_demand_paths)),
            },
            "budget": budget.as_dict() if budget is not None else {"mode": "legacy-default"},
            "prompt": _prompt_identity(task),
        }
    )
    rhythm_bridge = _digest(
        {
            "rhythm": revisions["rhythm_plan_revision"],
            "previous_scene": str(trace.get("previous_promoted_scene_sha") or ""),
        }
    )
    key = ContextCacheKey(
        project_revision=compound_revision,
        scope_kind="scene",
        scope_id=scene_id,
        canon_digest=revisions["canon_revision"],
        character_state_digest=revisions["state_revision"],
        style_mount_hash=revisions["style_mount_revision"],
        word_budget_revision=revisions["word_budget_revision"],
        rhythm_bridge_hash=rhythm_bridge,
        task_role=task.execution_contract.agent_role,
        task_kind=f"{task.task_type}:{task.current_state}",
    )
    if cache_key_violations(key):
        return None, "cache-key-contract-invalid"
    return key, ""


def _declared_trace_path(task: TaskPackage, workspace: Path) -> Path | None:
    relative = str(task.payload.get("context_trace") or "").strip()
    if not relative:
        return None
    return workspace / Path(str(normalize_relative_path(relative)))


def _read_trace(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _trace_revisions(trace: dict[str, Any]) -> dict[str, str] | None:
    fields = (
        "project_revision",
        "canon_revision",
        "state_revision",
        "style_mount_revision",
        "word_budget_revision",
        "rhythm_plan_revision",
    )
    revisions = {field: str(trace.get(field) or "").strip() for field in fields}
    return revisions if all(revisions.values()) else None


def _declared_content_digest(workspace: Path, paths: Iterable[str]) -> str:
    records: list[dict[str, object]] = []
    for relative in _unique(paths):
        normalized = str(normalize_relative_path(relative))
        path = workspace / Path(normalized)
        records.append(_content_record(workspace, normalized, path))
    return _digest(records)


def _content_record(workspace: Path, relative: str, path: Path) -> dict[str, object]:
    if path.is_file():
        return {"path": relative, "kind": "file", "sha256": _file_digest(path)}
    if path.is_dir():
        files = [
            {
                "path": item.relative_to(workspace).as_posix(),
                "sha256": _file_digest(item),
            }
            for item in sorted(path.rglob("*"))
            if item.is_file()
        ]
        return {"path": relative, "kind": "directory", "files": files}
    return {"path": relative, "kind": "missing"}


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prompt_identity(task: TaskPackage) -> dict[str, object]:
    prompt = task.payload.get("prompt_asset")
    prompt_asset = prompt if isinstance(prompt, dict) else {}
    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "current_state": task.current_state,
        "role": task.execution_contract.agent_role,
        "prompt_id": str(prompt_asset.get("resolved_id") or ""),
        "prompt_version": str(prompt_asset.get("version") or ""),
    }


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).replace("\\", "/") for value in values))


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
