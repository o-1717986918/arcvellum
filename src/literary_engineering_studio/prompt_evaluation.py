"""Deterministic regression checks for high-risk literary prompt assets."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.prompt_registry import resolve_prompt_asset


REPORT_SCHEMA = "literary-engineering-studio/prompt-evaluation/v0.1"
HIGH_RISK_CASES: dict[str, tuple[str, ...]] = {
    "route.scene-development.roleplay.execute.v1": ("character", "canon", "consequence"),
    "route.scene-development.branch.execute.v1": ("branch", "cost", "canon"),
    "route.scene-development.branch.selection.v1": ("select", "rejected", "human"),
    "route.scene-development.composition.execute.v1": ("rhythm", "bridge", "target"),
    "route.scene-development.prose.generate.v1": ("style", "word budget", "reader"),
    "route.scene-development.agent-review.v1": ("exact candidate", "style lint", "pass_with_notes"),
    "route.scene-development.revision.v1": ("revision", "review", "candidate"),
    "route.scene-development.canon-evolve.v1": ("canon", "candidate", "approval"),
    "route.longform-planning.budget-review.v1": ("inventory", "target", "padding"),
    "route.longform-planning.budget-expansion.execute.v1": ("inventory", "pass", "completion"),
    "route.longform-planning.scene-inventory.execute.v1": ("scene", "function", "target"),
    "route.source-ingest.extract-project-files.v1": ("source", "inference", "provenance"),
    "route.source-ingest.extraction-review.v1": ("source", "evidence", "uncertainty"),
    "route.character-world-assets.create.v1": ("candidate", "canon", "background"),
    "route.character-world-assets.review.execute.v1": ("review", "canon", "approval"),
    "route.review-audit.committee.execute.v1": ("committee", "blocking", "pass_with_notes"),
    "route.export-release.approval.v1": ("approval", "manuscript", "release"),
}


def evaluate_prompt_assets() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for prompt_id, semantic_terms in HIGH_RISK_CASES.items():
        preview = resolve_prompt_asset(prompt_id)
        errors: list[str] = []
        asset = preview.asset
        if asset is None:
            errors.append("missing prompt asset")
            body = ""
            metadata_text = ""
            resolved_id = ""
        else:
            body = asset.body.strip()
            metadata_text = json.dumps(asset.metadata, ensure_ascii=False).lower()
            resolved_id = asset.prompt_asset_id
            if not preview.exact:
                errors.append(f"high-risk task resolved through wildcard {asset.match}")
            for field in ("required_inputs", "hard_constraints", "output_contract", "review_requirements", "forbidden_shortcuts"):
                value = asset.metadata.get(field)
                if not isinstance(value, list) or not value:
                    errors.append(f"missing non-empty {field}")
            searchable = (metadata_text + "\n" + body.lower()).replace("-", " ")
            for term in semantic_terms:
                if term.lower().replace("-", " ") not in searchable:
                    errors.append(f"missing semantic anchor: {term}")
            if len(body) < 100:
                errors.append("prompt body is too short for a high-risk exact asset")
        cases.append(
            {
                "prompt_asset_id": prompt_id,
                "resolved_id": resolved_id,
                "exact": bool(preview.exact),
                "status": "pass" if not errors else "fail",
                "errors": errors,
                "digest": hashlib.sha256((metadata_text + "\n" + body).encode("utf-8")).hexdigest(),
            }
        )
    failures = sum(1 for case in cases if case["status"] != "pass")
    return {
        "schema": REPORT_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if failures == 0 else "fail",
        "case_count": len(cases),
        "failure_count": failures,
        "cases": cases,
        "metrics": {
            "exact_asset_rate": (len(cases) - failures) / len(cases) if cases else 0.0,
            "live_semantic_evaluation": "not-run",
        },
    }


def write_prompt_evaluation(path: Path) -> dict[str, Any]:
    report = evaluate_prompt_assets()
    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
