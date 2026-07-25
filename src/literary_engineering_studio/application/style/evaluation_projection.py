"""Safe style-evaluation projections with quality and leakage kept separate."""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import EvaluationProjection


def project_evaluations(profile_dir: Path) -> tuple[list[dict[str, object]], list[str]]:
    items: list[dict[str, object]] = []
    issues: list[str] = []
    for path in sorted((profile_dir / "evaluation_results").glob("*/style_eval_*.json")):
        payload = _read_json(path)
        if payload is None:
            issues.append(f"invalid evaluation JSON: {path.name}")
            continue
        risk = str(payload.get("risk_level") or "")
        try:
            score = float(payload.get("overall_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
            issues.append(f"invalid evaluation score: {path.name}")
        items.append(
            EvaluationProjection(
                evaluation_id=path.stem,
                mode=str(payload.get("mode") or ""),
                overall_score=score,
                risk_level=risk,
                style_quality_status="pass" if score >= 45 and risk != "low_similarity" else "needs-work",
                leakage_risk_status="blocked" if risk == "high_copy_risk" else "clear",
                candidate_sha256=str(payload.get("candidate_sha256") or ""),
                reference_sha256=str(payload.get("reference_sha256") or ""),
            ).as_dict()
        )
    return items, issues


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None
