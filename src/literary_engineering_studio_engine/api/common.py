"""Security, path and response helpers shared by Engine API routers."""

from __future__ import annotations

import json
import secrets
from pathlib import Path

from ..formal_mode import FormalModeBypassError, ensure_no_bypass

try:
    from fastapi import HTTPException, Request
    from fastapi.responses import Response
except ImportError:  # pragma: no cover - optional HTTP dependency
    HTTPException = None
    Request = object
    Response = None


def root_policy(allowed_roots: list[str | Path] | None) -> list[Path]:
    return [Path(item).expanduser().resolve() for item in allowed_roots or [] if str(item).strip()]


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def safe_project_root(project_root: str | Path, allowed_roots: list[Path]) -> Path:
    root = Path(project_root).expanduser().resolve()
    if allowed_roots and not any(root == allowed or is_relative_to(root, allowed) for allowed in allowed_roots):
        raise HTTPException(status_code=403, detail=f"project root is outside allowed roots: {root}")
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=404, detail=f"project root not found: {root}")
    return root


def ensure_target_allowed(target: Path, allowed_roots: list[Path]) -> None:
    parent = target.parent.resolve()
    if allowed_roots and not any(parent == allowed or is_relative_to(parent, allowed) for allowed in allowed_roots):
        raise HTTPException(status_code=403, detail=f"target is outside allowed roots: {target}")


def safe_relative_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise HTTPException(status_code=400, detail="artifact path must be relative")
    resolved = (root / path).resolve()
    if not is_relative_to(resolved, root):
        raise HTTPException(status_code=403, detail="artifact path escapes project root")
    return resolved


def safe_agent_run_dir(root: Path, run_id: str) -> Path:
    if "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=400, detail="invalid run_id")
    return safe_relative_path(root, Path("agents") / "runs" / run_id)


def run_state_path(root: Path, run_id: str) -> Path:
    if "/" in run_id or "\\" in run_id or ".." in run_id:
        raise HTTPException(status_code=400, detail="invalid run_id")
    return safe_relative_path(root, Path("workflow") / "runs" / run_id / "workflow_state.json")


def require_api_token(request: Request, api_token: str) -> None:
    if not api_token:
        return
    authorization = request.headers.get("authorization", "")
    bearer_token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    header_token = request.headers.get("x-lew-api-token", "").strip()
    if not ((bearer_token and secrets.compare_digest(bearer_token, api_token)) or (header_token and secrets.compare_digest(header_token, api_token))):
        raise HTTPException(status_code=401, detail="missing or invalid API token")


def reject_bypass(payload: object, surface: str) -> None:
    try:
        ensure_no_bypass(payload, surface=surface)
    except FormalModeBypassError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def tail_jsonl(path: Path, limit: int) -> list[dict[str, object]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def read_text(path: Path, limit: int) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")[:limit] if path.exists() else ""


def frontend_file(path: str, content_type: str):
    if "/" in path or "\\" in path:
        clean = Path(path)
        if any(part == ".." for part in clean.parts):
            raise HTTPException(status_code=400, detail="invalid frontend path")
    frontend_root = Path(__file__).resolve().parents[3] / "frontend"
    target = (frontend_root / path).resolve()
    if not is_relative_to(target, frontend_root) or not target.is_file():
        raise HTTPException(status_code=404, detail=f"frontend asset not found: {path}")
    if content_type.startswith("image/") and "svg" not in content_type:
        return Response(content=target.read_bytes(), media_type=content_type)
    return Response(content=target.read_text(encoding="utf-8"), media_type=content_type)
