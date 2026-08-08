"""Machine-owned evidence for one bounded project mutation stage."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Mapping

from ..protocols.canonical_json import canonical_json_digest

MUTATION_RECEIPT_SCHEMA = "arcvellum/worker-mutation-receipt/v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class MutationAction(str, Enum):
    CANDIDATE_CREATED = "candidate_created"
    CANDIDATE_MODIFIED = "candidate_modified"
    PREFLIGHT_REJECTED = "preflight_rejected"
    WRITEBACK_PREVIEWED = "writeback_previewed"
    WRITEBACK_APPLIED = "writeback_applied"
    WRITEBACK_ROLLED_BACK = "writeback_rolled_back"
    FORMAL_PROMOTED = "formal_promoted"


class FormalEffect(str, Enum):
    NONE = "none"
    CANDIDATE = "candidate"
    FORMAL = "formal"


@dataclass(frozen=True)
class MutationReceipt:
    receipt_id: str
    change_group_id: str
    project_key: str
    plan_id: str
    plan_revision: int
    node_id: str
    task_id: str
    run_id: str
    session_id: str
    context_ledger_id: str
    action: MutationAction
    target: str
    base_sha256: str
    result_sha256: str
    preflight_status: str
    writeback_status: str
    formal_effect: FormalEffect
    created_at: str

    def __post_init__(self) -> None:
        for name, value in (
            ("receipt_id", self.receipt_id),
            ("change_group_id", self.change_group_id),
            ("project_key", self.project_key),
            ("plan_id", self.plan_id),
            ("node_id", self.node_id),
            ("task_id", self.task_id),
            ("run_id", self.run_id),
            ("session_id", self.session_id),
            ("target", self.target),
            ("created_at", self.created_at),
        ):
            if not value.strip():
                raise ValueError(f"mutation receipt {name} is required")
        if self.plan_revision < 0:
            raise ValueError("mutation receipt plan_revision cannot be negative")
        _optional_digest(self.base_sha256, "base")
        _optional_digest(self.result_sha256, "result")
        if self.preflight_status not in {"pending", "pass", "rejected"}:
            raise ValueError(f"unsupported preflight status: {self.preflight_status}")
        if self.writeback_status not in {
            "pending",
            "previewed",
            "applied",
            "rolled_back",
            "rejected",
            "not_applicable",
        }:
            raise ValueError(f"unsupported writeback status: {self.writeback_status}")
        if (
            self.action == MutationAction.WRITEBACK_ROLLED_BACK
            and self.formal_effect != FormalEffect.NONE
        ):
            raise ValueError("rolled-back mutation receipts must have formal_effect=none")

    @property
    def digest(self) -> str:
        return _digest(self._body())

    def _body(self) -> dict[str, object]:
        return {
            "schema": MUTATION_RECEIPT_SCHEMA,
            "receipt_id": self.receipt_id,
            "change_group_id": self.change_group_id,
            "authority": "studio-machine",
            "project_key": self.project_key,
            "plan_id": self.plan_id,
            "plan_revision": self.plan_revision,
            "node_id": self.node_id,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "context_ledger_id": self.context_ledger_id,
            "action": self.action.value,
            "target": self.target,
            "base_sha256": self.base_sha256,
            "result_sha256": self.result_sha256,
            "preflight_status": self.preflight_status,
            "writeback_status": self.writeback_status,
            "formal_effect": self.formal_effect.value,
            "created_at": self.created_at,
        }

    def as_dict(self) -> dict[str, object]:
        return {**self._body(), "digest": self.digest}


def build_mutation_receipt(
    *,
    change_group_id: str,
    project_key: str,
    plan_id: str,
    plan_revision: int,
    node_id: str,
    task_id: str,
    run_id: str,
    session_id: str,
    context_ledger_id: str,
    action: MutationAction,
    target: str,
    base_sha256: str,
    result_sha256: str,
    preflight_status: str,
    writeback_status: str,
    formal_effect: FormalEffect,
    created_at: str,
) -> MutationReceipt:
    return MutationReceipt(
        receipt_id=_receipt_id(
            change_group_id=change_group_id,
            task_id=task_id,
            run_id=run_id,
            session_id=session_id,
            action=action,
            target=target,
            base_sha256=base_sha256,
            result_sha256=result_sha256,
            preflight_status=preflight_status,
            writeback_status=writeback_status,
            formal_effect=formal_effect,
        ),
        change_group_id=change_group_id,
        project_key=project_key,
        plan_id=plan_id,
        plan_revision=plan_revision,
        node_id=node_id,
        task_id=task_id,
        run_id=run_id,
        session_id=session_id,
        context_ledger_id=context_ledger_id,
        action=action,
        target=target,
        base_sha256=base_sha256,
        result_sha256=result_sha256,
        preflight_status=preflight_status,
        writeback_status=writeback_status,
        formal_effect=formal_effect,
        created_at=created_at,
    )


def parse_mutation_receipt(payload: Mapping[str, Any]) -> MutationReceipt:
    if _text(payload, "schema") != MUTATION_RECEIPT_SCHEMA:
        raise ValueError("unsupported mutation receipt schema")
    if _text(payload, "authority") != "studio-machine":
        raise ValueError("Worker mutation receipts must be machine-owned")
    receipt = _receipt_from_payload(payload)
    supplied = _text(payload, "digest")
    if supplied and supplied != receipt.digest:
        raise ValueError("mutation receipt digest does not match its body")
    if receipt.receipt_id != _expected_receipt_id(receipt):
        raise ValueError("mutation receipt identity does not match its body")
    return receipt


def _receipt_from_payload(payload: Mapping[str, Any]) -> MutationReceipt:
    return MutationReceipt(
        receipt_id=_text(payload, "receipt_id"),
        change_group_id=_text(payload, "change_group_id"),
        project_key=_text(payload, "project_key"),
        plan_id=_text(payload, "plan_id"),
        plan_revision=_integer(payload, "plan_revision"),
        node_id=_text(payload, "node_id"),
        task_id=_text(payload, "task_id"),
        run_id=_text(payload, "run_id"),
        session_id=_text(payload, "session_id"),
        context_ledger_id=_text(payload, "context_ledger_id"),
        action=MutationAction(_text(payload, "action")),
        target=_text(payload, "target"),
        base_sha256=_text(payload, "base_sha256"),
        result_sha256=_text(payload, "result_sha256"),
        preflight_status=_text(payload, "preflight_status"),
        writeback_status=_text(payload, "writeback_status"),
        formal_effect=FormalEffect(_text(payload, "formal_effect")),
        created_at=_text(payload, "created_at"),
    )


def _expected_receipt_id(receipt: MutationReceipt) -> str:
    return _receipt_id(
        change_group_id=receipt.change_group_id,
        task_id=receipt.task_id,
        run_id=receipt.run_id,
        session_id=receipt.session_id,
        action=receipt.action,
        target=receipt.target,
        base_sha256=receipt.base_sha256,
        result_sha256=receipt.result_sha256,
        preflight_status=receipt.preflight_status,
        writeback_status=receipt.writeback_status,
        formal_effect=receipt.formal_effect,
    )


def _receipt_id(
    *,
    change_group_id: str,
    task_id: str,
    run_id: str,
    session_id: str,
    action: MutationAction,
    target: str,
    base_sha256: str,
    result_sha256: str,
    preflight_status: str,
    writeback_status: str,
    formal_effect: FormalEffect,
) -> str:
    identity = {
        "change_group_id": change_group_id,
        "task_id": task_id,
        "run_id": run_id,
        "session_id": session_id,
        "action": action.value,
        "target": target,
        "base_sha256": base_sha256,
        "result_sha256": result_sha256,
        "preflight_status": preflight_status,
        "writeback_status": writeback_status,
        "formal_effect": formal_effect.value,
    }
    return f"receipt-{_digest(identity)[:24]}"


def _optional_digest(value: str, label: str) -> None:
    if value and not _SHA256.fullmatch(value):
        raise ValueError(f"mutation receipt {label}_sha256 is invalid")


def _text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    return "" if value is None else str(value)


def _integer(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    return int(value) if value is not None else 0


def _digest(value: object) -> str:
    return canonical_json_digest(value)
