"""Candidate-revision task blueprint for the formal scene route."""

from __future__ import annotations

from typing import Iterable


def candidate_revision_blueprint(
    *,
    scene_rel: str,
    context_trace: str,
    scene_runtime_sources: Iterable[str],
    revision_source: str,
    review: str,
    revision: str,
    direction_sources: Iterable[str],
    historical_sources: Iterable[str],
    migration_outputs: Iterable[str],
) -> dict[str, object]:
    migration = list(migration_outputs)
    return {
        "task_type": "platform-agent-revision",
        "prompt_asset_id": "route.scene-development.revision.v1",
        "command": (
            f"python -m literary_engineering_studio_engine revise-scene <project> --scene {scene_rel} "
            f"--draft {revision_source} --review {review}.json --out {revision}.md "
            f"--report-out {revision}_report.md --manifest-out {revision}.json "
            f"--prompt-manifest-out {revision}.prompt.json --agent-tasks-out {revision}.agent_tasks.md"
        ),
        "source_paths": list(
            dict.fromkeys(
                [
                    *scene_runtime_sources,
                    revision_source,
                    f"{review}.json",
                    f"{review}.md",
                    *direction_sources,
                    *historical_sources,
                ]
            )
        ),
        "context_trace": context_trace,
        "candidate": f"{revision}.md",
        "revision_source": revision_source,
        "expected_outputs": [
            f"{revision}.md",
            f"{revision}_report.md",
            f"{revision}.json",
            f"{revision}.prompt.json",
            f"{revision}.agent_tasks.md",
            f"{revision}.agent_completion.json",
            *migration,
        ],
        "core_managed_outputs": [
            f"{revision}.prompt.json",
            f"{revision}.agent_tasks.md",
            *migration,
        ],
        "hard_constraints": [
            "The main creative Agent must execute the revision personally; subagents cannot write or polish prose.",
            "Every blocking issue, warning, revision action, style deviation, budget gap, reader-contract gap, and rhythm/bridge gap must map to an observable prose change or remain explicitly blocking.",
            "The revised deliverable body must differ from the exact source candidate; changing only reports or manifests is forbidden.",
            "The revision remains a candidate and must receive a fresh exact-candidate AgentReview before promotion.",
            "When the review requires a human/delegated direction, follow only the consumed revision_direction choice file included in source_paths. It must match the exact revision source path and SHA-256; never reuse a global or stale direction. Do not alter canon or character assets from this prose task.",
        ],
        "style_constraints": [
            "Apply semantic anti-evasion revision rather than regex cleanup.",
            "Do not replace a banned contrast or transition with a cosmetic synonym.",
        ],
        "validation_gates": [
            "revision candidate and provenance files exist",
            "revision candidate differs from source sha256",
            "revision manifest records applied actions and ready_for_review=false",
            "revision sidecar completion marker exists",
        ],
        "next_allowed_states": ["candidate-review"],
    }


__all__ = ["candidate_revision_blueprint"]
