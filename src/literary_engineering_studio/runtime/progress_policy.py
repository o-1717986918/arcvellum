"""Task-local progress identity used to stop identical repair turns."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ..contracts import TaskPackage
from ..preflight.common import PreflightResult
from .sandbox import SandboxManifest


PROGRESS_DIGEST_SCHEMA = "arcvellum/runtime-progress-digest/v1"


@dataclass(frozen=True)
class RuntimeProgressDigest:
    digest: str
    output_digests: tuple[tuple[str, str], ...]
    issue_ids: tuple[str, ...]
    context_access_digest: str
    task_state: str

    def event_fields(self) -> dict[str, object]:
        return {
            "progress_digest": self.digest,
            "output_count": len(self.output_digests),
            "issue_ids": list(self.issue_ids),
            "context_access_digest": self.context_access_digest,
            "task_state": self.task_state,
        }


def build_runtime_progress_digest(
    task: TaskPackage,
    sandbox: SandboxManifest,
    preflight: PreflightResult,
    *,
    context_access: Mapping[str, Any] | None = None,
) -> RuntimeProgressDigest:
    output_digests = tuple(
        (relative, _path_digest(sandbox.workspace / Path(relative)))
        for relative in _agent_owned_outputs(task)
    )
    issue_ids = tuple(
        sorted(f"{item.code}:{item.path}" for item in preflight.issues)
    )
    context_digest = _canonical_digest(dict(context_access or {}))
    task_state = f"{task.route}:{task.current_state}:{task.task_id}"
    payload = {
        "schema": PROGRESS_DIGEST_SCHEMA,
        "output_digests": output_digests,
        "issue_ids": issue_ids,
        "context_access_digest": context_digest,
        "task_state": task_state,
    }
    return RuntimeProgressDigest(
        digest=_canonical_digest(payload),
        output_digests=output_digests,
        issue_ids=issue_ids,
        context_access_digest=context_digest,
        task_state=task_state,
    )


def _agent_owned_outputs(task: TaskPackage) -> tuple[str, ...]:
    protected = set(task.core_managed_outputs)
    completion = {
        item.path
        for item in task.execution_contract.outputs
        if item.kind == "completion-evidence"
    }
    return tuple(
        relative
        for relative in task.expected_outputs
        if relative not in protected and relative not in completion
    )


def _path_digest(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    rows = [
        (item.relative_to(path).as_posix(), hashlib.sha256(item.read_bytes()).hexdigest())
        for item in sorted(path.rglob("*"))
        if item.is_file()
    ]
    return _canonical_digest(rows)


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "PROGRESS_DIGEST_SCHEMA",
    "RuntimeProgressDigest",
    "build_runtime_progress_digest",
]
