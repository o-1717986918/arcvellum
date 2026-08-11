"""Scene draft, generation, revision, and promotion command handlers."""

from __future__ import annotations

from pathlib import Path

from ...candidate_promotion import promote_scene_candidate
from ...cli_support import cli_path, print_agent_task_notice
from ...context_broker import context_trace_status, default_context_trace_path
from ...context_packet import build_context_packet
from ...flow_gates import ensure_scene_pre_generation_tasks_completed
from ...platform_agent_tasks import write_platform_scene_generation_task
from ...prompt_pack import build_scene_prompt_pack, write_prompt_manifest
from ...review_ci import review_scene_draft
from ...scene_character_assets import (
    ensure_scene_character_asset_tasks,
    scene_character_asset_requirements,
)
from ...scene_draft import build_scene_draft
from ...scene_revision import build_scene_revision_task


def handle_draft_scene(args, parser) -> int:
    result = build_scene_draft(
        Path(args.project),
        scene=Path(args.scene),
        context=Path(args.context) if args.context else None,
        query=args.query,
        rebuild_context=args.rebuild_context,
        output=Path(args.out) if args.out else None,
    )
    print(f"draft: {result.draft_path}")
    print(f"context: {result.context_path}")
    print(f"scene: {result.scene_id}")
    return 0


def handle_review_scene(args, parser) -> int:
    result = review_scene_draft(
        Path(args.project),
        Path(args.draft),
        output=Path(args.out) if args.out else None,
    )
    print(f"review: {result.report_path}")
    print(f"conclusion: {result.conclusion}")
    print(f"issues: {result.issue_count}")
    return 0


def handle_generate_scene(args, parser) -> int:
    try:
        root = Path(args.project).resolve()
        scene_path = cli_path(root, args.scene)
        scene_id = scene_path.stem
        context_path = _generation_context(root, scene_path, scene_id, args)
        composition = cli_path(root, args.composition) if args.composition else None
        candidate = (
            cli_path(root, args.out)
            if args.out
            else root / "drafts" / "candidates" / f"{scene_id}-platform-agent.md"
        )
        if not (args.allow_unselected_composition or args.allow_missing_composition):
            ensure_scene_pre_generation_tasks_completed(root, scene_id)
        unresolved_characters = scene_character_asset_requirements(root, scene_path)
        if unresolved_characters:
            ensure_scene_character_asset_tasks(root, scene_path)
            names = "、".join(item.name for item in unresolved_characters)
            raise RuntimeError(
                "scene prose is blocked until named participant assets are reviewed and promoted: "
                f"{names}; run the character-and-world-assets route, then retry generate-scene"
            )
        prompt_pack = build_scene_prompt_pack(
            root,
            scene_path,
            context_path,
            composition=composition,
            allow_unselected_composition=args.allow_unselected_composition,
            allow_missing_composition=args.allow_missing_composition,
            materialization_scope=args.materialization_scope,
        )
        prompt_manifest = candidate.with_suffix(".prompt.json")
        write_prompt_manifest(
            prompt_pack,
            prompt_manifest,
            provider="platform-agent",
            model="tool-layer-agent",
        )
        result = write_platform_scene_generation_task(
            root,
            scene_path=scene_path,
            context_path=context_path,
            composition_path=prompt_pack.composition_path,
            prompt_manifest_path=prompt_manifest,
            candidate_path=candidate,
        )
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(f"scene_generation_task: {result.task_path}")
    print(f"expected_candidate: {result.expected_report_path}")
    print(f"expected_manifest: {result.expected_json_path}")
    print(f"prompt_manifest: {prompt_manifest}")
    print("receiver: platform-agent")
    print(f"scene: {scene_id}")
    print_agent_task_notice(result.task_path, project=root)
    return 0


def handle_prepare_scene_character_assets(args, parser) -> int:
    """Emit candidate-asset sidecars before RP or prose work begins."""

    try:
        root = Path(args.project).resolve()
        scene_path = cli_path(root, args.scene)
        requirements = ensure_scene_character_asset_tasks(root, scene_path)
    except (FileNotFoundError, RuntimeError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(f"scene: {scene_path.stem}")
    print(f"unresolved_character_assets: {len(requirements)}")
    for requirement in requirements:
        print(f"scene_character_asset_task: {requirement.task_path}")
    print("next_route: character-and-world-assets" if requirements else "next_route: scene-development")
    return 0


def _generation_context(root: Path, scene_path: Path, scene_id: str, args) -> Path:
    context_path = (
        cli_path(root, args.context)
        if args.context
        else root / "memory" / "context_packets" / f"{scene_id}.md"
    )
    context_current = (
        context_path.exists()
        and default_context_trace_path(context_path).exists()
        and context_trace_status(root, scene_id, context_path).passed
    )
    if not args.rebuild_context and context_current:
        return context_path
    return build_context_packet(
        root,
        scene=scene_path,
        query=args.query,
        rebuild_index=True,
        output=context_path,
    ).output_path


def handle_revise_scene(args, parser) -> int:
    try:
        result = build_scene_revision_task(
            Path(args.project),
            scene=Path(args.scene),
            draft=Path(args.draft) if args.draft else None,
            review=Path(args.review) if args.review else None,
            query=args.query,
            rebuild_context=args.rebuild_context,
            output=Path(args.out) if args.out else None,
            report_output=Path(args.report_out) if args.report_out else None,
            manifest_output=Path(args.manifest_out) if args.manifest_out else None,
            prompt_manifest_output=(
                Path(args.prompt_manifest_out) if args.prompt_manifest_out else None
            ),
            task_output=Path(args.agent_tasks_out) if args.agent_tasks_out else None,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"revision_task: {result.task_path}")
    print(f"prompt_manifest: {result.prompt_manifest_path}")
    print(f"expected_candidate: {result.expected_candidate_path}")
    print(f"expected_report: {result.expected_report_path}")
    print(f"expected_manifest: {result.expected_manifest_path}")
    print(f"sources: {result.source_count}")
    print("receiver: platform-agent")
    print(f"scene: {result.scene_id}")
    print_agent_task_notice(result.task_path, project=Path(args.project).resolve())
    return 0


def handle_promote_candidate(args, parser) -> int:
    try:
        result = promote_scene_candidate(
            Path(args.project),
            scene=Path(args.scene),
            candidate=Path(args.candidate) if args.candidate else None,
            output=Path(args.out) if args.out else None,
            overwrite=args.overwrite,
            approval_run_id=args.approval_run_id,
            selection_note=args.selection_note,
            allow_unreviewed=args.allow_unreviewed,
            allow_review_notes=args.allow_review_notes,
        )
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"draft: {result.draft_path}")
    print(f"candidate: {result.candidate_path}")
    print(f"manifest: {result.manifest_path}")
    print(f"report: {result.report_path}")
    print(f"scene: {result.scene_id}")
    print(f"chars: {result.chars}")
    print(f"approval_run_id: {result.approval_run_id or 'n/a'}")
    return 0


HANDLERS = {
    "draft-scene": handle_draft_scene,
    "review-scene": handle_review_scene,
    "generate-scene": handle_generate_scene,
    "prepare-scene-character-assets": handle_prepare_scene_character_assets,
    "revise-scene": handle_revise_scene,
    "promote-candidate": handle_promote_candidate,
}
