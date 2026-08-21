"""Route blueprint and deterministic gate for whole-work scene length repair."""

from __future__ import annotations

from pathlib import Path

from ...foundation.draft_text import (
    count_delivery_chinese_content_chars,
    final_body_from_draft_path,
)
from ...literary.planning.length_repair import scene_length_repair_allocation
from ...literary.scene.promotion.historical_context import (
    historical_revision_source_paths,
)


def target_length_revision_blueprint(
    root: Path,
    scene_id: str,
    scene_rel: str,
    revision_source: str,
    revision: str,
    scene_runtime_sources: list[str],
    base: dict[str, object],
) -> dict[str, object] | None:
    allocation = scene_length_repair_allocation(root, scene_id)
    if not allocation:
        return None
    historical_sources = historical_revision_source_paths(
        root,
        scene_id,
        root / revision_source,
    )
    result = dict(base)
    result.update({
        "prompt_asset_id": "route.scene-development.target-length-revision.v1",
        "command": (
            f"python -m literary_engineering_studio_engine revise-scene <project> --scene {scene_rel} "
            f"--draft {revision_source} --review reviews/longform/target_length_repair.json "
            f"--out {revision}.md --report-out {revision}_report.md "
            f"--manifest-out {revision}.json --prompt-manifest-out {revision}.prompt.json "
            f"--agent-tasks-out {revision}.agent_tasks.md"
        ),
        "source_paths": list(dict.fromkeys([
            *scene_runtime_sources,
            revision_source,
            "reviews/longform/target_length_repair.json",
            "reviews/longform/target_length_repair.md",
            *historical_sources,
        ])),
        "hard_constraints": _hard_constraints(allocation),
        "validation_gates": [
            "revision candidate differs from promoted draft sha256",
            "clean deliverable body reaches the exact repair minimum",
            "revision provenance and completion files exist",
            "revision manifest records applied actions and ready_for_review=false",
        ],
    })
    return result


def target_length_revision_entry(
    root: Path,
    scene_id: str,
    scene_rel: str,
    revision_source: str,
    revision: str,
    scene_runtime_sources: list[str],
    base: dict[str, object],
) -> dict[str, dict[str, object]]:
    blueprint = target_length_revision_blueprint(
        root, scene_id, scene_rel, revision_source, revision,
        scene_runtime_sources, base,
    )
    return {"target-length-revision": blueprint} if blueprint is not None else {}


def target_length_revision_gate_errors(
    root: Path,
    scene_id: str,
    candidate: Path | None,
) -> list[str]:
    allocation = scene_length_repair_allocation(root, scene_id)
    if not allocation:
        return ["target-length revision has no current scene allocation"]
    if candidate is None or not candidate.is_file():
        return ["target-length revision candidate is missing"]
    minimum = int(allocation.get("minimum_scene_chars") or 0)
    actual = count_delivery_chinese_content_chars(final_body_from_draft_path(candidate))
    return [] if actual >= minimum else [
        f"target-length revision remains short: actual={actual}; required={minimum}"
    ]


def _hard_constraints(allocation: dict[str, object]) -> list[str]:
    minimum = int(allocation.get("minimum_scene_chars") or 0)
    growth = int(allocation.get("required_growth_chars") or 0)
    return [
        "The main creative Agent must revise the prose personally; subagents cannot write or polish prose.",
        (
            "Return the complete revised scene with at least "
            f"{minimum} Chinese-content characters, measured on the clean deliverable body."
        ),
        (
            "Net meaningful growth must satisfy this allocation: "
            f"{growth} characters. Use causal action, relationship pressure, "
            "information release, consequence, or earned aftermath."
        ),
        "Do not pad with repeated emotion, redundant scenery, paraphrased recap, cosmetic dialogue, Markdown, or workflow traces.",
        "The result remains a candidate and must receive fresh exact-candidate AgentReview, promotion, static review, state, Canon, and continuity processing.",
    ]


__all__ = [
    "target_length_revision_blueprint",
    "target_length_revision_entry",
    "target_length_revision_gate_errors",
]
