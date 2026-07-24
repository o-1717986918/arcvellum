"""Persistent reader-question and promise/payoff ledgers.

The ledgers are formal project assets.  A promoted scene creates only a delta
candidate; a separate reviewer validates it; deterministic application merges
the approved delta.  This keeps prose from silently rewriting what the reader
has been promised.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ....agent_tasks import agent_task_completion_status, write_agent_tasks
from ....atomic_io import atomic_write_text


DELTA_SCHEMA = "literary-engineering-workbench/continuity-ledger-delta/v1"
REVIEW_SCHEMA = "literary-engineering-workbench/continuity-ledger-review/v1"
LEDGER_SCHEMA = "literary-engineering-workbench/continuity-ledger/v1"


def delta_path(root: Path, scene_id: str) -> Path:
    return root.resolve() / "plot" / "ledger_deltas" / f"{scene_id}.json"


def author_task_path(root: Path, scene_id: str) -> Path:
    return delta_path(root, scene_id).with_suffix(".agent_tasks.md")


def review_path(root: Path, scene_id: str) -> Path:
    return root.resolve() / "reviews" / "continuity" / f"{scene_id}_ledger_review.json"


def review_task_path(root: Path, scene_id: str) -> Path:
    return review_path(root, scene_id).with_suffix(".agent_tasks.md")


def reader_ledger_path(root: Path) -> Path:
    return root.resolve() / "plot" / "reader_questions" / "ledger.json"


def promise_ledger_path(root: Path) -> Path:
    return root.resolve() / "plot" / "promises" / "ledger.json"


def prepare_continuity_ledger(project_root: Path, scene_id: str) -> tuple[Path, Path]:
    root = project_root.resolve()
    draft = root / "drafts" / "scenes" / f"{scene_id}.md"
    promotion = root / "drafts" / "promotions" / f"{scene_id}_promotion.json"
    if not draft.is_file() or not promotion.is_file():
        raise FileNotFoundError(f"continuity ledger requires promoted draft and promotion manifest for {scene_id}")
    target = delta_path(root, scene_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        payload = {
            "schema": DELTA_SCHEMA,
            "status": "pending_agent_judgment",
            "scene_id": scene_id,
            "source_draft": f"drafts/scenes/{scene_id}.md",
            "source_draft_sha256": _sha256(draft),
            "writer_session_id": "",
            "evidence_paths": [],
            "reader_question_changes": [],
            "promise_changes": [],
            "no_change_reason": "",
            "created_at": _now(),
        }
        atomic_write_text(target, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    sidecar = author_task_path(root, scene_id)
    write_agent_tasks(
        sidecar,
        title=f"场景连续性账本候选 {scene_id}",
        root=root,
        source_paths=[draft, promotion, target, reader_ledger_path(root), promise_ledger_path(root)],
        tasks=[(
            "提取读者问题与承诺变化候选",
            f"由当前主平台 Agent 读取已晋升正文、promotion manifest 和现有账本，填写 `{target.relative_to(root).as_posix()}`。\n\n"
            "只记录正文有证据的变化：提出、推进、延迟、兑现、反转、关闭。每条必须有稳定 ID、type/content/status、evidence 和目标窗口。"
            "若本场没有新变化，两个列表可为空，但 no_change_reason 必须具体。不要把猜测、作者解释或未晋升候选写入正式账本。"
        )],
        notes=["账本变化仍是 Candidate；必须通过独立审查和 apply 才进入下场 Context。"],
    )
    return target, sidecar


def prepare_continuity_ledger_review(project_root: Path, scene_id: str) -> tuple[Path, Path]:
    root = project_root.resolve()
    delta = delta_path(root, scene_id)
    if not delta.is_file():
        raise FileNotFoundError("continuity ledger delta is missing")
    target = review_path(root, scene_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    delta_sha = _sha256(delta)
    if not target.exists():
        payload = {
            "schema": REVIEW_SCHEMA,
            "status": "pending_agent_judgment",
            "scene_id": scene_id,
            "delta_path": _rel(delta, root),
            "delta_sha256": delta_sha,
            "writer_session_id": "",
            "reviewer_session_id": "",
            "verdict": "pending",
            "findings": [],
            "required_changes": [],
            "created_at": _now(),
        }
        atomic_write_text(target, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    sidecar = review_task_path(root, scene_id)
    write_agent_tasks(
        sidecar,
        title=f"场景连续性账本独立审查 {scene_id}",
        root=root,
        source_paths=[root / "drafts" / "scenes" / f"{scene_id}.md", delta, target, reader_ledger_path(root), promise_ledger_path(root)],
        tasks=[(
            "审查连续性账本候选",
            f"作为独立 Reviewer，核对 `{target.relative_to(root).as_posix()}` 是否只登记了正文可证明的 reader question 与 promise/payoff 变化。\n\n"
            "Studio Worker 会将 reviewer_session_id 绑定为不同于 delta Writer 的正式任务身份，并写入精确 delta SHA。发现未证实承诺、重复提问、只有延迟却没有推进或不合理 due window 时，verdict=revise/block。不得直接修改正式账本。"
        )],
        notes=["正式 ledger apply 只有在完整 pass review 后才可执行。"],
    )
    return target, sidecar


def continuity_ledger_status(project_root: Path, scene_id: str, *, require_review: bool = True) -> tuple[bool, str, dict[str, Any]]:
    root = project_root.resolve()
    delta = delta_path(root, scene_id)
    if not delta.is_file():
        return False, f"missing continuity ledger delta: {_rel(delta, root)}", {}
    payload = _read_json(delta)
    if payload.get("schema") != DELTA_SCHEMA:
        return False, "continuity ledger delta schema is invalid", payload
    draft = root / "drafts" / "scenes" / f"{scene_id}.md"
    if str(payload.get("source_draft") or "") != f"drafts/scenes/{scene_id}.md" or not draft.is_file() or str(payload.get("source_draft_sha256") or "") != _sha256(draft):
        return False, "continuity ledger delta is stale for the promoted draft", payload
    if str(payload.get("status") or "").lower() != "complete" or not str(payload.get("writer_session_id") or "").strip():
        return False, "continuity ledger delta is incomplete or lacks writer session", payload
    questions = payload.get("reader_question_changes")
    promises = payload.get("promise_changes")
    evidence = payload.get("evidence_paths")
    if not isinstance(questions, list) or not isinstance(promises, list) or not isinstance(evidence, list):
        return False, "continuity ledger delta fields are malformed", payload
    if not (questions or promises) and not str(payload.get("no_change_reason") or "").strip():
        return False, "empty continuity delta requires a concrete no_change_reason", payload
    if (questions or promises) and not [item for item in evidence if str(item).strip()]:
        return False, "continuity ledger delta requires evidence_paths", payload
    if not require_review:
        return True, "continuity ledger delta is complete", payload
    review = review_path(root, scene_id)
    if not review.is_file():
        return False, "missing continuity ledger review", payload
    reviewed = _read_json(review)
    if reviewed.get("schema") != REVIEW_SCHEMA or str(reviewed.get("delta_sha256") or "") != _sha256(delta):
        return False, "continuity ledger review is invalid or stale", payload
    if str(reviewed.get("status") or "").lower() != "complete" or str(reviewed.get("verdict") or "").lower() != "pass":
        return False, "continuity ledger review is not a complete pass", payload
    if str(reviewed.get("reviewer_session_id") or "") == str(payload.get("writer_session_id") or "") or not str(reviewed.get("reviewer_session_id") or ""):
        return False, "continuity ledger reviewer must use a different session", payload
    return True, "continuity ledger delta and independent review pass", payload


def continuity_ledger_task_status(project_root: Path, scene_id: str, *, review: bool = False) -> tuple[bool, str]:
    root = project_root.resolve()
    sidecar = review_task_path(root, scene_id) if review else author_task_path(root, scene_id)
    marker = agent_task_completion_status(sidecar, root=root)
    if marker.get("complete") is not True:
        return False, str(marker.get("message") or "continuity ledger sidecar pending")
    return continuity_ledger_status(root, scene_id, require_review=review)[:2]


def apply_continuity_ledger(project_root: Path, scene_id: str) -> tuple[Path, Path]:
    root = project_root.resolve()
    passed, message, delta = continuity_ledger_status(root, scene_id, require_review=True)
    if not passed:
        raise ValueError("cannot apply continuity ledger: " + message)
    delta_file = delta_path(root, scene_id)
    delta_sha = _sha256(delta_file)
    questions = _merge_ledger(reader_ledger_path(root), "reader_questions", delta.get("reader_question_changes") if isinstance(delta.get("reader_question_changes"), list) else [], scene_id, delta_sha)
    promises = _merge_ledger(promise_ledger_path(root), "promises", delta.get("promise_changes") if isinstance(delta.get("promise_changes"), list) else [], scene_id, delta_sha)
    receipt = root / "plot" / "ledger_deltas" / f"{scene_id}_apply.json"
    receipt_payload = {
        "schema": "literary-engineering-workbench/continuity-ledger-apply/v1",
        "scene_id": scene_id,
        "delta": _rel(delta_file, root),
        "delta_sha256": delta_sha,
        "reader_ledger": _rel(reader_ledger_path(root), root),
        "promise_ledger": _rel(promise_ledger_path(root), root),
        "applied_at": _now(),
        "status": "applied",
    }
    atomic_write_text(receipt, json.dumps(receipt_payload, ensure_ascii=False, indent=2) + "\n")
    return reader_ledger_path(root), promise_ledger_path(root)


def _merge_ledger(path: Path, collection: str, changes: list[Any], scene_id: str, delta_sha: str) -> dict[str, Any]:
    previous = _read_json(path)
    rows = previous.get(collection) if isinstance(previous.get(collection), list) else []
    merged: dict[str, dict[str, Any]] = {str(item.get("id") or item.get("question_id") or item.get("promise_id") or ""): dict(item) for item in rows if isinstance(item, dict)}
    for index, value in enumerate(changes, start=1):
        if not isinstance(value, dict):
            continue
        item = dict(value)
        item_id = str(item.get("id") or item.get("question_id") or item.get("promise_id") or f"{scene_id}-{collection}-{index}").strip()
        item["id"] = item_id
        item["last_advanced_at"] = scene_id
        item["applied_from_delta_sha256"] = delta_sha
        merged[item_id] = {**merged.get(item_id, {}), **item}
    payload = {
        "schema": LEDGER_SCHEMA,
        "collection": collection,
        "revision": int(previous.get("revision") or 0) + 1,
        "updated_at": _now(),
        collection: [merged[key] for key in sorted(merged)],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()
