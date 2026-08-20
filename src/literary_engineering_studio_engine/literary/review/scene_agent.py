"""Provider-backed scene review orchestration and formal artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from ...agent_provider import run_agent_task
from ...agent_schema import validate_agent_run
from ...creative_quality import creative_quality_profile_exists
from .scene_agent_context import SceneAgentReviewContext, prepare_scene_agent_review_context
from .scene_agent_context import read_text as _read
from .scene_agent_context import relative_path as _rel_str
from .scene_agent_context import resolve_draft as _resolve_draft
from .scene_agent_context import resolve_output as _resolve_output
from .scene_agent_context import resolve_scene as _resolve_scene
from .scene_agent_dry import dry_scene_review as _dry_scene_review
from .scene_agent_dry import style_source_label as _style_source_label
from .scene_agent_prompt import scene_review_system_prompt as _system_prompt
from .scene_agent_prompt import scene_review_user_prompt as _user_prompt
from .scene_agent_report import render_scene_review_report as _render_report


@dataclass(frozen=True)
class AgentSceneReviewResult:
    project_root: Path
    scene_id: str
    run_dir: Path
    report_path: Path
    json_path: Path
    validation_path: Path
    conclusion: str


def review_scene_with_agent(
    project_root: Path,
    *,
    scene: Path | None = None,
    draft: Path | None = None,
    provider: str = "auto",
    output: Path | None = None,
    json_output: Path | None = None,
) -> AgentSceneReviewResult:
    context = prepare_scene_agent_review_context(project_root, scene, draft)
    dry_payload = _dry_scene_review(
        context.scene_id,
        context.draft_text,
        context.source_paths,
        context.word_budget_adherence,
        context.reader_adherence,
        context.quality_profile,
        context.candidate_sha256,
    )
    dry_payload["style_mount_snapshot"] = context.style_mount_snapshot
    run_result = run_agent_task(
        context.root,
        agent_id="scene-reviewer",
        task=f"review-scene:{context.scene_id}",
        system_prompt=_system_prompt(),
        user_prompt=_prompt_from_context(context),
        provider=provider,
        metadata={
            "schema_name": "scene_review.v1",
            "scene_id": context.scene_id,
            "source_paths": context.source_paths,
        },
        dry_run_output=dry_payload,
    )
    validation = validate_agent_run(context.root, run_dir=run_result.run_dir, schema_name="scene_review.v1")
    parsed = json.loads(run_result.parsed_output_path.read_text(encoding="utf-8"))
    _bind_review_metadata(
        parsed,
        context.root,
        run_result.run_dir,
        validation.validation_path,
        context.candidate_sha256,
        context.quality_path,
        context.quality_profile,
        context.style_mount_snapshot,
    )
    report_path, json_path = _write_review_artifacts(context.root, context.scene_id, parsed, validation.status, output, json_output)
    return AgentSceneReviewResult(
        project_root=context.root,
        scene_id=context.scene_id,
        run_dir=run_result.run_dir,
        report_path=report_path,
        json_path=json_path,
        validation_path=validation.validation_path,
        conclusion=str(parsed.get("conclusion", "")),
    )


def _prompt_from_context(context: SceneAgentReviewContext) -> str:
    return _user_prompt(
        context.scene_text,
        context.draft_text,
        context.context_text,
        context.context_trace_text,
        context.style_text,
        context.source_paths,
        context.word_budget_adherence,
        context.reader_adherence,
        context.rhythm_contract_text,
        context.quality_profile,
        context.scene_id,
        context.candidate_sha256,
    )


def _write_review_artifacts(
    root: Path,
    scene_id: str,
    payload: dict[str, object],
    validation_status: str,
    output: Path | None,
    json_output: Path | None,
) -> tuple[Path, Path]:
    report_path = _resolve_output(root, output, "reviews", "agent", f"{scene_id}_scene_review.md")
    json_path = _resolve_output(root, json_output, "reviews", "agent", f"{scene_id}_scene_review.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_render_report(payload, validation_status), encoding="utf-8")
    return report_path, json_path


def _bind_review_metadata(
    payload: dict[str, object],
    root: Path,
    run_dir: Path,
    validation_path: Path,
    candidate_sha256: str,
    quality_path: Path,
    quality_profile: dict[str, object],
    style_mount_snapshot: dict[str, str],
) -> None:
    payload.update(
        {
            "agent_run_dir": _rel_str(run_dir, root),
            "candidate_sha256": candidate_sha256,
            "schema_validation": _rel_str(validation_path, root),
            "creative_quality_profile": {
                "path": _rel_str(quality_path, root) if creative_quality_profile_exists(root) else "implicit-default",
                "revision": quality_profile.get("revision"),
                "digest": quality_profile.get("digest"),
                "name": quality_profile.get("name"),
            },
            "style_mount_snapshot": style_mount_snapshot,
        }
    )


__all__ = ["AgentSceneReviewResult", "review_scene_with_agent"]
