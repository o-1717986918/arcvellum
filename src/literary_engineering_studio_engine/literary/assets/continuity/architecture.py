"""Formal longform story-architecture candidate and independent review contract."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ....agent_tasks import agent_task_completion_status, write_agent_tasks
from ....atomic_io import atomic_write_text


ARCHITECTURE_SCHEMA = "literary-engineering-workbench/story-architecture/v1"
ARCHITECTURE_REVIEW_SCHEMA = "literary-engineering-workbench/story-architecture-review/v1"
REQUIRED_FIELDS = (
    "premise",
    "central_dramatic_question",
    "protagonist_initial_misbelief",
    "protagonist_desire",
    "protagonist_need",
    "counterforce",
    "thematic_contradiction",
    "change_vector",
    "midpoint_irreversibility",
    "endgame_choice",
    "ending_state",
    "volume_obligations",
    "non_negotiable_payoffs",
)


def candidate_path(root: Path) -> Path:
    return root.resolve() / "plot" / "story_architecture.candidate.json"


def task_path(root: Path) -> Path:
    return root.resolve() / "plot" / "story_architecture.agent_tasks.md"


def review_path(root: Path) -> Path:
    return root.resolve() / "reviews" / "longform" / "story_architecture_review.json"


def review_task_path(root: Path) -> Path:
    return root.resolve() / "reviews" / "longform" / "story_architecture_review.agent_tasks.md"


def prepare_story_architecture(project_root: Path) -> tuple[Path, Path]:
    root = project_root.resolve()
    candidate = candidate_path(root)
    candidate.parent.mkdir(parents=True, exist_ok=True)
    if not candidate.exists():
        payload = {
            "schema": ARCHITECTURE_SCHEMA,
            "status": "pending_agent_judgment",
            "writer_session_id": "",
            "created_at": _now(),
            **{field: [] if field in {"volume_obligations", "non_negotiable_payoffs"} else "" for field in REQUIRED_FIELDS},
        }
        atomic_write_text(candidate, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    sidecar = task_path(root)
    write_agent_tasks(
        sidecar,
        title="长篇故事架构候选",
        root=root,
        source_paths=[root / "project.yaml", root / "plot" / "outline.md", candidate],
        tasks=[(
            "建立不可替代的全书脊柱",
            f"读取 `project.yaml`、已有 outline 和 `{candidate.relative_to(root).as_posix()}`。由当前主平台 Agent 填写创作字段；Studio Worker 会写入 status 与 writer_session_id。\n\n"
            "不要把字数、事件数量或人物小传当成故事架构。必须明确中心戏剧问题、主角从误信到改变的向量、中点不可逆、终局选择、结局状态、每卷义务和不可谈判的兑现。"
            "若无法支持目标篇幅，明确写入问题而不是用空泛节点掩盖。只写声明的候选文件，不修改正式 outline 或 scenes。"
        )],
        notes=["这是 Candidate，不是正式大纲；后续独立 Reviewer 必须使用不同 session_id 审查。"],
    )
    return candidate, sidecar


def prepare_story_architecture_review(project_root: Path) -> tuple[Path, Path]:
    root = project_root.resolve()
    candidate = candidate_path(root)
    if not candidate.is_file():
        raise FileNotFoundError("story architecture candidate is missing")
    target = review_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    candidate_sha = _sha256(candidate)
    existing = _read_json(target) if target.exists() else {}
    if str(existing.get("candidate_sha256") or "") != candidate_sha:
        payload = {
            "schema": ARCHITECTURE_REVIEW_SCHEMA,
            "status": "pending_agent_judgment",
            "candidate_path": "plot/story_architecture.candidate.json",
            "candidate_sha256": candidate_sha,
            "writer_session_id": "",
            "reviewer_session_id": "",
            "verdict": "pending",
            "findings": [],
            "required_changes": [],
            "checked_dimensions": list(REQUIRED_FIELDS),
            "created_at": _now(),
        }
        atomic_write_text(target, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    sidecar = review_task_path(root)
    write_agent_tasks(
        sidecar,
        title="长篇故事架构独立审查",
        root=root,
        source_paths=[root / "project.yaml", candidate, target],
        tasks=[(
            "独立审查故事架构",
            f"作为 Reviewer 读取 `{candidate.relative_to(root).as_posix()}` 和项目硬约束。填写 `{target.relative_to(root).as_posix()}`；它必须引用当前 candidate SHA，status=complete，verdict 只能是 pass/revise/block。\n\n"
            "Studio Worker 会将 reviewer_session_id 绑定为不同于 Writer 的正式任务身份。批判检查：终局选择是否存在、人物变化是否由事件而非结论支撑、每卷是否承担不可替代职责、长度目标是否有足够因果库存。不得代替 Writer 重写 Candidate。"
        )],
        notes=["Reviewer 不读取 Writer 自我说明；有必须改变的事项必须 verdict=revise，不能用 pass_with_notes。"],
    )
    return target, sidecar


def story_architecture_status(project_root: Path, *, require_review: bool = True) -> tuple[bool, str, dict[str, Any]]:
    root = project_root.resolve()
    candidate = candidate_path(root)
    if not candidate.is_file():
        return False, "missing plot/story_architecture.candidate.json", {}
    payload = _read_json(candidate)
    if payload.get("schema") != ARCHITECTURE_SCHEMA:
        return False, "story architecture schema is invalid", payload
    missing = [field for field in REQUIRED_FIELDS if not _meaningful(payload.get(field))]
    if str(payload.get("status") or "").lower() != "complete" or missing:
        return False, "story architecture is incomplete: " + ", ".join(missing or ["status"]), payload
    if not require_review:
        return True, "story architecture candidate is complete", payload
    review = review_path(root)
    if not review.is_file():
        return False, "missing independent story architecture review", payload
    review_payload = _read_json(review)
    if review_payload.get("schema") != ARCHITECTURE_REVIEW_SCHEMA:
        return False, "story architecture review schema is invalid", payload
    if str(review_payload.get("candidate_sha256") or "") != _sha256(candidate):
        return False, "story architecture review is stale for current candidate", payload
    writer = str(payload.get("writer_session_id") or "")
    reviewer = str(review_payload.get("reviewer_session_id") or "")
    if not writer or not reviewer or writer == reviewer:
        return False, "story architecture review must use a different non-empty reviewer session", payload
    if str(review_payload.get("status") or "").lower() != "complete" or str(review_payload.get("verdict") or "").lower() != "pass":
        return False, "story architecture review is not a complete pass", payload
    return True, "story architecture candidate and independent review pass", payload


def story_architecture_task_status(project_root: Path, *, review: bool = False) -> tuple[bool, str]:
    root = project_root.resolve()
    sidecar = review_task_path(root) if review else task_path(root)
    marker = agent_task_completion_status(sidecar, root=root)
    if marker.get("complete") is not True:
        return False, str(marker.get("message") or "story architecture sidecar pending")
    if review:
        complete, message, _verdict = story_architecture_review_status(root)
        return complete, message
    return story_architecture_status(root, require_review=False)[:2]


def story_architecture_review_status(project_root: Path) -> tuple[bool, str, str]:
    """Validate a completed review without treating ``revise`` as a final pass."""

    root = project_root.resolve()
    candidate = candidate_path(root)
    review = review_path(root)
    if not candidate.is_file() or not review.is_file():
        return False, "story architecture candidate or review is missing", ""
    candidate_payload = _read_json(candidate)
    payload = _read_json(review)
    if payload.get("schema") != ARCHITECTURE_REVIEW_SCHEMA:
        return False, "story architecture review schema is invalid", ""
    if str(payload.get("candidate_sha256") or "") != _sha256(candidate):
        return False, "story architecture review is stale for current candidate", ""
    writer = str(candidate_payload.get("writer_session_id") or "")
    reviewer = str(payload.get("reviewer_session_id") or "")
    if not writer or not reviewer or writer == reviewer:
        return False, "story architecture review must use a different non-empty reviewer session", ""
    verdict = str(payload.get("verdict") or "").lower()
    if str(payload.get("status") or "").lower() != "complete" or verdict not in {
        "pass",
        "revise",
        "block",
    }:
        return False, "story architecture review has no completed terminal verdict", verdict
    return True, f"story architecture review recorded: {verdict}", verdict


def _meaningful(value: Any) -> bool:
    if isinstance(value, list):
        return bool(value)
    return bool(str(value or "").strip())


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
