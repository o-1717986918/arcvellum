"""Rendering of immutable style versions and legacy-compatible packages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from .review import style_review_paths
from .session import load_style_session
from .version_contracts import (
    COMPATIBLE_STYLE_SKILL_SCHEMA,
    STYLE_VERSION_BUILDER,
    STYLE_VERSION_SCHEMA,
)


def materialize_style_version(plan: Any, temporary: Path) -> None:
    source = plan.profile_dir
    evaluation = source / "evaluation_results" / "formal"
    copies = {
        "prompt.md": source / "style_prompt.md",
        "style-profile.md": source / "style-profile.md",
        "style_metrics.json": source / "style_metrics.json",
        "style_prompt.agent.json": source / "style_prompt.agent.json",
        "corpus_manifest.yaml": source / "corpus_manifest.yaml",
        "evaluation_results/formal/style_eval_current.json": evaluation / "style_eval_current.json",
        "evaluation_results/formal/style_eval_current.md": evaluation / "style_eval_current.md",
        "evaluation_results/formal/style_semantic_review.json": evaluation / "style_semantic_review.json",
        "evaluation_results/formal/style_semantic_review.md": evaluation / "style_semantic_review.md",
    }
    for relative, source_path in copies.items():
        target = temporary / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
    (temporary / "STYLE.md").write_text(_style_markdown(plan), encoding="utf-8")
    (temporary / "style_skill.json").write_text(
        _json_text(_compatibility_manifest(plan)),
        encoding="utf-8",
    )
    artifacts = {
        path.relative_to(temporary).as_posix(): _sha256(path)
        for path in sorted(temporary.rglob("*"))
        if path.is_file()
    }
    (temporary / "style_version.json").write_text(
        _json_text(_version_manifest(plan, artifacts)),
        encoding="utf-8",
    )


def _version_manifest(plan: Any, artifacts: dict[str, str]) -> dict[str, object]:
    session = load_style_session(plan.profile_dir)
    review = _read_object(style_review_paths(plan.profile_dir).review_json)
    score = _read_object(
        plan.profile_dir / "evaluation_results/formal/style_eval_current.json"
    )
    return {
        "schema": STYLE_VERSION_SCHEMA,
        "style_id": plan.style_id,
        "version_id": plan.version_id,
        "content_hash": plan.content_hash,
        "builder": STYLE_VERSION_BUILDER,
        "author_id": str(session.get("author_id") or ""),
        "profile_id": str(session.get("profile_id") or ""),
        "session_id": str(session.get("session_id") or ""),
        "session_request_digest": str(session.get("request_digest") or ""),
        "source_evidence": list(plan.source_evidence),
        "prompt_quality": plan.prompt_quality,
        "review_status": "pass",
        "reviewer_session_id": str(review.get("reviewer_session_id") or ""),
        "evaluation": {
            "overall_score": score.get("overall_score"),
            "risk_level": score.get("risk_level"),
            "candidate_sha256": score.get("candidate_sha256"),
            "reference_sha256": score.get("reference_sha256"),
        },
        "review_evidence": plan.review_evidence,
        "priority": {
            "expression": "highest",
            "cannot_override": [
                "canon",
                "character facts",
                "plot causality",
                "legal and safety boundaries",
                "explicit user constraints",
            ],
        },
        "copy_boundary": (
            "Apply abstract craft mechanisms; do not reproduce source passages or "
            "treat holdout prose as generation context."
        ),
        "artifacts": artifacts,
        "created_at": str(session.get("created_at") or ""),
    }


def _compatibility_manifest(plan: Any) -> dict[str, object]:
    session = load_style_session(plan.profile_dir)
    score = _read_object(
        plan.profile_dir / "evaluation_results/formal/style_eval_current.json"
    )
    return {
        "schema": COMPATIBLE_STYLE_SKILL_SCHEMA,
        "style_id": plan.style_id,
        "version": plan.version_id,
        "version_id": plan.version_id,
        "content_hash": plan.content_hash,
        "author_id": str(session.get("author_id") or ""),
        "author": str(session.get("display_name") or session.get("author_id") or ""),
        "profile_id": str(session.get("profile_id") or ""),
        "mode": "rights-declared-formal-session",
        "priority": 1000,
        "prompt": "prompt.md",
        "profile": "style-profile.md",
        "metrics": "style_metrics.json",
        "style_markdown": "STYLE.md",
        "review_status": "pass",
        "readiness": {
            "ready": True,
            "prompt_detail_chars": int(plan.prompt_quality.get("detail_chars") or 0),
            "prompt_length_ok": bool(plan.prompt_quality.get("length_ok")),
            "prompt_quality": plan.prompt_quality,
            "accepted_evaluations": [
                {
                    "path": "evaluation_results/formal/style_eval_current.json",
                    "mode": score.get("mode", "blind-review"),
                    "overall_score": score.get("overall_score"),
                    "risk_level": score.get("risk_level"),
                }
            ],
            "missing": [],
            "blocking_risks": [],
        },
        "created_at": str(session.get("created_at") or ""),
    }


def _style_markdown(plan: Any) -> str:
    return (
        f"# Style Profile Version: {plan.style_id}\n\n"
        f"- Version: `{plan.version_id}`\n"
        f"- Content hash: `{plan.content_hash}`\n"
        "- Review: `pass`\n\n"
        "This immutable package applies the reviewed prompt in `prompt.md` as the "
        "highest expression-level constraint. It cannot override canon, character "
        "facts, plot causality, explicit user constraints, or legal boundaries.\n"
    )


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
