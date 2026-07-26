"""Machine-only receipt recording around the existing Worker writeback transaction."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable

from ..contracts import TaskPackage
from ..observability.change_groups import change_group_id
from ..observability.mutation_receipts import (
    FormalEffect,
    MutationAction,
    MutationReceipt,
    build_mutation_receipt,
    parse_mutation_receipt,
)
from .sandbox import SandboxManifest, WritebackPreview


RECEIPTS_FILENAME = "mutation-receipts.jsonl"


class WorkerMutationTracker:
    """Append immutable evidence outside both the Agent and formal project views."""

    def __init__(
        self,
        task: TaskPackage,
        sandbox: SandboxManifest,
        *,
        session_id: str,
        event_sink: Callable[[str, dict[str, Any]], None] | None,
    ):
        self.task = task
        self.sandbox = sandbox
        self.session_id = session_id.strip() or f"worker-run:{sandbox.run_id}"
        self.event_sink = event_sink
        self.path = sandbox.run_root / RECEIPTS_FILENAME
        self.project_key = _project_key(task.project_root)
        self.change_group_id = change_group_id(
            project_key=self.project_key,
            run_id=sandbox.run_id,
            task_id=task.task_id,
        )
        self.plan_id = str(
            task.payload.get("creative_plan_id")
            or task.payload.get("plan_id")
            or "fixed-route"
        ).strip()
        self.plan_revision = _non_negative_int(
            task.payload.get("creative_plan_revision")
            or task.payload.get("plan_revision")
        )
        self.node_id = str(
            task.payload.get("creative_plan_node_id")
            or task.payload.get("node_id")
            or task.task_id
        ).strip()
        self.context_ledger_id = _run_field(
            sandbox.manifest_path,
            "context_ledger_id",
        )
        self._known = {
            receipt.receipt_id
            for receipt in load_worker_mutation_receipts(sandbox.run_root)
        }

    def candidate_outputs(self, *, preflight_status: str) -> tuple[MutationReceipt, ...]:
        receipts: list[MutationReceipt] = []
        workspace = self.sandbox.control_workspace or self.sandbox.workspace
        for relative in self.sandbox.expected_outputs:
            source = workspace / Path(relative)
            if not source.exists():
                continue
            target = self.task.resolve_project_path(relative)
            receipts.append(
                self._record(
                    action=(
                        MutationAction.CANDIDATE_MODIFIED
                        if target.exists()
                        else MutationAction.CANDIDATE_CREATED
                    ),
                    target=relative,
                    base_sha256=_path_digest(target),
                    result_sha256=_path_digest(source),
                    preflight_status=preflight_status,
                    writeback_status="pending",
                    formal_effect=FormalEffect.NONE,
                )
            )
        return tuple(receipts)

    def preflight_rejected(self) -> MutationReceipt:
        return self._record(
            action=MutationAction.PREFLIGHT_REJECTED,
            target=f"task:{self.task.task_id}",
            base_sha256="",
            result_sha256="",
            preflight_status="rejected",
            writeback_status="not_applicable",
            formal_effect=FormalEffect.NONE,
        )

    def previewed(self, preview: WritebackPreview) -> tuple[MutationReceipt, ...]:
        return tuple(
            self._record_from_change(
                change,
                action=MutationAction.WRITEBACK_PREVIEWED,
                preflight_status="pass",
                writeback_status="previewed",
                formal_effect=FormalEffect.NONE,
            )
            for change in preview.changes
        )

    def rejected(self, preview: WritebackPreview) -> tuple[MutationReceipt, ...]:
        return tuple(
            self._record_from_change(
                change,
                action=MutationAction.WRITEBACK_PREVIEWED,
                preflight_status="pass",
                writeback_status="rejected",
                formal_effect=FormalEffect.NONE,
            )
            for change in preview.changes
        )

    def applied(self, preview: WritebackPreview) -> tuple[MutationReceipt, ...]:
        effect = FormalEffect.FORMAL if _is_promotion(self.task) else FormalEffect.CANDIDATE
        return tuple(
            self._record_from_change(
                change,
                action=MutationAction.WRITEBACK_APPLIED,
                preflight_status="pass",
                writeback_status="applied",
                formal_effect=effect,
            )
            for change in preview.changes
        )

    def rolled_back(self, preview: WritebackPreview) -> tuple[MutationReceipt, ...]:
        return tuple(
            self._record_from_change(
                change,
                action=MutationAction.WRITEBACK_ROLLED_BACK,
                preflight_status="pass",
                writeback_status="rolled_back",
                formal_effect=FormalEffect.NONE,
                reverse=True,
            )
            for change in preview.changes
        )

    def promoted(self, preview: WritebackPreview) -> tuple[MutationReceipt, ...]:
        if not _is_promotion(self.task):
            return ()
        return tuple(
            self._record_from_change(
                change,
                action=MutationAction.FORMAL_PROMOTED,
                preflight_status="pass",
                writeback_status="applied",
                formal_effect=FormalEffect.FORMAL,
            )
            for change in preview.changes
        )

    def _record_from_change(
        self,
        change: dict[str, object],
        *,
        action: MutationAction,
        preflight_status: str,
        writeback_status: str,
        formal_effect: FormalEffect,
        reverse: bool = False,
    ) -> MutationReceipt:
        before = str(change.get("before_sha256") or "")
        after = str(change.get("after_sha256") or "")
        return self._record(
            action=action,
            target=str(change.get("path") or ""),
            base_sha256=after if reverse else before,
            result_sha256=before if reverse else after,
            preflight_status=preflight_status,
            writeback_status=writeback_status,
            formal_effect=formal_effect,
        )

    def _record(
        self,
        *,
        action: MutationAction,
        target: str,
        base_sha256: str,
        result_sha256: str,
        preflight_status: str,
        writeback_status: str,
        formal_effect: FormalEffect,
    ) -> MutationReceipt:
        receipt = build_mutation_receipt(
            change_group_id=self.change_group_id,
            project_key=self.project_key,
            plan_id=self.plan_id,
            plan_revision=self.plan_revision,
            node_id=self.node_id,
            task_id=self.task.task_id,
            run_id=self.sandbox.run_id,
            session_id=self.session_id,
            context_ledger_id=self.context_ledger_id,
            action=action,
            target=target,
            base_sha256=base_sha256,
            result_sha256=result_sha256,
            preflight_status=preflight_status,
            writeback_status=writeback_status,
            formal_effect=formal_effect,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        if receipt.receipt_id in self._known:
            return receipt
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt.as_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        self._known.add(receipt.receipt_id)
        if self.event_sink is not None:
            self.event_sink("mutation.receipt", {"receipt": receipt.as_dict()})
        return receipt


def load_worker_mutation_receipts(run_root: Path) -> tuple[MutationReceipt, ...]:
    path = run_root.expanduser().resolve() / RECEIPTS_FILENAME
    if not path.is_file():
        return ()
    receipts: list[MutationReceipt] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            receipts.append(parse_mutation_receipt(json.loads(line)))
    return tuple(receipts)


def _run_field(path: Path, field: str) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(payload.get(field) or "") if isinstance(payload, dict) else ""


def _project_key(project: Path) -> str:
    digest = hashlib.sha256(str(project.resolve()).encode("utf-8")).hexdigest()[:10]
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", project.name).strip("-") or "project"
    return f"{safe[:36]}-{digest}"


def _path_digest(path: Path) -> str:
    if not path.exists():
        return ""
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    hashes = {
        item.relative_to(path).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    }
    encoded = json.dumps(hashes, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _non_negative_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _is_promotion(task: TaskPackage) -> bool:
    return task.current_state in {"promotion-manifest", "asset-promotion"} or (
        "promote-candidate" in task.command
    )
