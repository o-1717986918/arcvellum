"""New-character declaration gates for formal scene work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...assets.character_identity import is_formal_character


REGISTER_KEY = "new_character_register"
SCHEMA = "literary-engineering-workbench/new-character-register/v0.1"

GENERATION_ALLOWED_STATUSES = {"none", "existing_only", "ephemeral_only", "candidates_ready", "resolved"}
REVIEW_ALLOWED_STATUSES = {"none", "existing_only", "ephemeral_only", "resolved"}
BLOCKING_STATUSES = {"", "unknown", "needs_candidate", "needs_review", "needs_approval", "blocked", "pending"}
PERSISTENT_VALUES = {"recurring", "major", "main", "plot", "persistent", "named", "consequential"}
EPHEMERAL_VALUES = {"", "ephemeral", "walk-on", "walk_on", "cameo", "background", "local"}


def empty_new_character_register() -> dict[str, object]:
    """Return the clean default register for a scene with no new character."""

    return {
        "schema": SCHEMA,
        "status": "none",
        "introduced": [],
        "ephemeral_waivers": [],
        "blocking_issues": [],
    }


def new_character_register_issues(payload: dict[str, Any], root: Path, *, mode: str) -> list[str]:
    """Return blocking issues for a generation manifest or scene review payload."""

    register = payload.get(REGISTER_KEY)
    if not isinstance(register, dict):
        return [f"{REGISTER_KEY} is missing"]

    status = str(register.get("status") or "").strip().lower()
    issues = _status_issues(status, mode)
    blocking = register.get("blocking_issues")
    if isinstance(blocking, list) and blocking:
        issues.append("new_character_register.blocking_issues is not empty")
    introduced = _introduced_rows(register, issues)
    for index, item in enumerate(introduced, 1):
        if not isinstance(item, dict):
            issues.append(f"new_character_register.introduced[{index}] must be an object")
            continue
        issues.extend(_character_row_issues(item, index, root, mode, status))

    if status == "none" and introduced:
        issues.append("new_character_register.status=none but introduced is not empty")
    if status == "ephemeral_only" and not introduced and not register.get("ephemeral_waivers"):
        issues.append("new_character_register.status=ephemeral_only needs introduced entries or ephemeral_waivers")
    return issues


def _status_issues(status: str, mode: str) -> list[str]:
    allowed = (
        GENERATION_ALLOWED_STATUSES
        if mode == "generation"
        else REVIEW_ALLOWED_STATUSES
    )
    if status not in BLOCKING_STATUSES and status in allowed:
        return []
    if mode == "review" and status == "candidates_ready":
        return [
            "new_character_register.status=candidates_ready still needs user approval/promotion before clean pass"
        ]
    return [
        f"new_character_register.status={status or 'missing'} is not clean for {mode}"
    ]


def _introduced_rows(
    register: dict[str, Any], issues: list[str]
) -> list[object]:
    introduced = register.get("introduced")
    if introduced is None:
        return []
    if isinstance(introduced, list):
        return introduced
    issues.append("new_character_register.introduced must be a list")
    return []


def _character_row_issues(
    item: dict[str, Any], index: int, root: Path, mode: str, status: str
) -> list[str]:
    name = _first_text(item, "name", "character", "character_id") or f"#{index}"
    if _row_is_formal(item, root, name):
        return []
    persistence = _first_text(item, "persistence", "scope").lower()
    if persistence in PERSISTENT_VALUES:
        return _persistent_character_issues(item, root, name, mode)
    if persistence not in EPHEMERAL_VALUES:
        return [
            f"new character `{name}` has unclear persistence `{persistence or 'missing'}`"
        ]
    waiver = _first_text(item, "waiver_reason", "waiver", "reason")
    if mode == "review" and status == "ephemeral_only" and not waiver:
        return [
            f"ephemeral new character `{name}` needs waiver_reason explaining why no character asset is required"
        ]
    return []


def _first_text(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def _row_is_formal(item: dict[str, Any], root: Path, name: str) -> bool:
    return (
        _truthy(item.get("already_in_characters"))
        or _path_exists(root, item.get("formal_character_path"))
        or is_formal_character(root, name)
    )


def _persistent_character_issues(
    item: dict[str, Any], root: Path, name: str, mode: str
) -> list[str]:
    candidate_path = str(item.get("candidate_path") or "").strip()
    issues: list[str] = []
    if not candidate_path:
        issues.append(f"persistent new character `{name}` has no candidate_path")
    elif not _path_exists(root, candidate_path):
        issues.append(
            f"persistent new character `{name}` candidate_path does not exist: {candidate_path}"
        )
    if mode != "review":
        return issues
    review_path = str(item.get("review_path") or "").strip()
    promotion = str(item.get("promotion_manifest") or "").strip()
    approval = str(item.get("approval_run_id") or "").strip()
    review_ok = bool(review_path and _path_exists(root, review_path))
    promotion_ok = bool(promotion and _path_exists(root, promotion))
    approval_ok = bool(approval and _has_approval(root, approval))
    if not (promotion_ok or approval_ok):
        issues.append(
            f"persistent new character `{name}` lacks approve record or promotion manifest"
        )
    if not review_ok and not promotion_ok:
        issues.append(f"persistent new character `{name}` lacks candidate asset review")
    return issues


def render_new_character_register_contract() -> str:
    """Return the prompt-facing contract for generation and review tasks."""

    return """# 新角色登记契约

正式场景不得让新角色从正文旁路进入项目。平台 Agent 必须在候选 manifest 和 AgentReview 中写入 `new_character_register`：

```json
{
  "schema": "literary-engineering-workbench/new-character-register/v0.1",
  "status": "none | existing_only | ephemeral_only | candidates_ready | resolved | needs_candidate | needs_review | needs_approval",
  "introduced": [
    {
      "name": "",
      "character_id": "",
      "scene_function": "",
      "persistence": "ephemeral | recurring | major | plot",
      "already_in_characters": false,
      "formal_character_path": "",
      "candidate_path": "characters/candidates/<id>.json",
      "review_path": "reviews/assets/<id>_review.json",
      "approval_run_id": "",
      "promotion_manifest": "",
      "waiver_reason": ""
    }
  ],
  "ephemeral_waivers": [],
  "blocking_issues": []
}
```

规则：

1. 纯路人、一次性称谓、没有后续关系和状态负债的角色可标 `ephemeral_only`，但必须写明豁免理由。
2. 有名字、会再出现、影响关系网、掌握线索、推动主线或改变世界状态的角色，必须先进入 `characters/candidates/`，再走 candidate review、用户 approval 和 promotion。
3. `needs_candidate`、`needs_review`、`needs_approval`、`unknown`、`blocked` 不能 clean pass。
4. 若正文引入新角色但 register 写 `none`，视为审查失败。
"""


def _path_exists(root: Path, value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    path = Path(text)
    if not path.is_absolute():
        path = root / path
    return path.exists()


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是", "已登记"}


def _has_approval(root: Path, run_id: str) -> bool:
    index = root / "workflow" / "approvals" / "index.jsonl"
    if not index.exists():
        return False
    for line in index.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("run_id") == run_id and record.get("decision") == "approve":
            return True
    return False
