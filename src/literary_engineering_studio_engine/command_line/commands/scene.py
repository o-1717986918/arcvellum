"""Scene-development command handlers for the formal literary pipeline."""
from __future__ import annotations

import json
from pathlib import Path

from ...branch_lab import build_branch_simulation
from ...canon_evolver import apply_canon_patch, build_canon_patch_backlog, build_canon_patch_task
from ...candidate_promotion import promote_scene_candidate
from ...character_state_apply import apply_character_state_patch
from ...character_state_evolver import build_character_state_patch
from ...cli_support import cli_path as _cli_path
from ...cli_support import print_agent_task_notice as _print_agent_task_notice
from ...context_broker import context_trace_status, default_context_trace_path
from ...context_packet import build_context_packet
from ...flow_gates import ensure_scene_pre_generation_tasks_completed
from ...platform_agent_tasks import write_platform_scene_generation_task
from ...prompt_pack import build_scene_prompt_pack, write_prompt_manifest
from ...review_ci import review_scene_draft
from ...roleplay_lab import build_roleplay_simulation
from ...scene_character_assets import ensure_scene_character_asset_tasks
from ...scene_composer import build_scene_composition
from ...scene_draft import build_scene_draft
from ...scene_revision import build_scene_revision_task
def handle(args, parser) -> int | None:
    if args.command == "draft-scene":
        context = Path(args.context) if args.context else None
        out = Path(args.out) if args.out else None
        result = build_scene_draft(
            Path(args.project),
            scene=Path(args.scene),
            context=context,
            query=args.query,
            rebuild_context=args.rebuild_context,
            output=out,
        )
        print(f"draft: {result.draft_path}")
        print(f"context: {result.context_path}")
        print(f"scene: {result.scene_id}")
        return 0

    if args.command == "review-scene":
        out = Path(args.out) if args.out else None
        result = review_scene_draft(Path(args.project), Path(args.draft), output=out)
        print(f"review: {result.report_path}")
        print(f"conclusion: {result.conclusion}")
        print(f"issues: {result.issue_count}")
        return 0

    if args.command == "generate-scene":
        try:
            root = Path(args.project).resolve()
            scene_path = _cli_path(root, args.scene)
            scene_id = scene_path.stem
            context_path = _cli_path(root, args.context) if args.context else root / "memory" / "context_packets" / f"{scene_id}.md"
            if (
                args.rebuild_context
                or not context_path.exists()
                or not default_context_trace_path(context_path).exists()
                or not context_trace_status(root, scene_id, context_path).passed
            ):
                context_path = build_context_packet(root, scene=scene_path, query=args.query, rebuild_index=True, output=context_path).output_path
            composition = _cli_path(root, args.composition) if args.composition else None
            candidate = _cli_path(root, args.out) if args.out else root / "drafts" / "candidates" / f"{scene_id}-platform-agent.md"
            if not (args.allow_unselected_composition or args.allow_missing_composition):
                ensure_scene_pre_generation_tasks_completed(root, scene_id)
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
            write_prompt_manifest(prompt_pack, prompt_manifest, provider="platform-agent", model="tool-layer-agent")
            result = write_platform_scene_generation_task(
                root,
                scene_path=scene_path,
                context_path=context_path,
                composition_path=prompt_pack.composition_path,
                prompt_manifest_path=prompt_manifest,
                candidate_path=candidate,
            )
            character_assets = ensure_scene_character_asset_tasks(root, scene_path)
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError, KeyError) as exc:
            parser.error(str(exc))
        print(f"scene_generation_task: {result.task_path}")
        print(f"expected_candidate: {result.expected_report_path}")
        print(f"expected_manifest: {result.expected_json_path}")
        print(f"prompt_manifest: {prompt_manifest}")
        for requirement in character_assets:
            print(f"scene_character_asset_task: {requirement.task_path}")
        print("receiver: platform-agent")
        print(f"scene: {scene_id}")
        _print_agent_task_notice(result.task_path, project=root)
        return 0

    if args.command == "revise-scene":
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
                prompt_manifest_output=Path(args.prompt_manifest_out) if args.prompt_manifest_out else None,
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
        _print_agent_task_notice(result.task_path, project=Path(args.project).resolve())
        return 0

    if args.command == "promote-candidate":
        candidate = Path(args.candidate) if args.candidate else None
        out = Path(args.out) if args.out else None
        try:
            result = promote_scene_candidate(
                Path(args.project),
                scene=Path(args.scene),
                candidate=candidate,
                output=out,
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

    if args.command == "state-evolve":
        source = Path(args.source) if args.source else None
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        result = build_character_state_patch(
            Path(args.project),
            scene=Path(args.scene),
            source=source,
            output=out,
            json_output=json_out,
            agent_tasks=args.agent_tasks,
        )
        print(f"state_patch: {result.output_path}")
        print(f"json: {result.json_path}")
        if result.agent_tasks_path:
            print(f"agent_tasks: {result.agent_tasks_path}")
            _print_agent_task_notice(result.agent_tasks_path, project=Path(args.project).resolve())
        print(f"scene: {result.scene_id}")
        print(f"source: {result.source_path}")
        print(f"characters: {result.character_count}")
        print(f"unresolved: {result.unresolved_count}")
        return 0

    if args.command == "canon-evolve":
        source = Path(args.source) if args.source else None
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        result = build_canon_patch_task(
            Path(args.project),
            scene=Path(args.scene),
            source=source,
            output=out,
            json_output=json_out,
        )
        print(f"canon_patch: {result.report_path}")
        print(f"json: {result.json_path}")
        print(f"agent_tasks: {result.task_path}")
        print(f"scene: {result.scene_id}")
        print(f"source: {result.source_path}")
        _print_agent_task_notice(result.task_path, project=Path(args.project).resolve())
        return 0

    if args.command == "canon-backlog":
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        result = build_canon_patch_backlog(
            Path(args.project),
            output=out,
            json_output=json_out,
        )
        print(f"canon_backlog: {result.output_path}")
        print(f"json: {result.json_path}")
        print(f"pending: {result.pending_count}")
        print(f"applied: {result.applied_count}")
        return 0

    if args.command == "canon-apply":
        patch = Path(args.patch) if args.patch else None
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        try:
            result = apply_canon_patch(
                Path(args.project),
                patch=patch,
                approval_run_id=args.approval_run_id,
                allow_unapproved=args.allow_unapproved,
                output=out,
                json_output=json_out,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"canon_apply: {result.report_path}")
        print(f"json: {result.json_path}")
        print(f"patch: {result.patch_path}")
        print(f"changelog: {result.changelog_path}")
        print(f"status: {result.status}")
        print(f"items: {result.applied_count}")
        return 0

    if args.command == "state-apply":
        patch = Path(args.patch) if args.patch else None
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        try:
            result = apply_character_state_patch(
                Path(args.project),
                patch=patch,
                approval_run_id=args.approval_run_id,
                allow_unapproved=args.allow_unapproved,
                allow_unresolved=args.allow_unresolved,
                output=out,
                json_output=json_out,
            )
        except RuntimeError as exc:
            parser.error(str(exc))
        print(f"state_apply: {result.report_path}")
        print(f"json: {result.manifest_path}")
        print(f"scene: {result.scene_id}")
        print(f"status: {result.status}")
        print(f"characters: {result.applied_character_count}")
        print(f"updates: {result.update_count}")
        print(f"approval_run_id: {result.approval_run_id or 'n/a'}")
        return 0

    if args.command == "simulate-scene":
        context = Path(args.context) if args.context else None
        out = Path(args.out) if args.out else None
        result = build_roleplay_simulation(
            Path(args.project),
            scene=Path(args.scene),
            context=context,
            query=args.query,
            rebuild_context=args.rebuild_context,
            output=out,
            agent_mode=args.agent_tasks,
        )
        print(f"simulation: {result.output_path}")
        print(f"context: {result.context_path}")
        print(f"scene: {result.scene_id}")
        print(f"characters: {result.character_count}")
        if result.agent_tasks_path:
            print(f"agent_tasks: {result.agent_tasks_path}")
            _print_agent_task_notice(result.agent_tasks_path, project=Path(args.project).resolve())
        return 0

    if args.command == "branch-simulate":
        context = Path(args.context) if args.context else None
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        selection_out = Path(args.selection_out) if args.selection_out else None
        try:
            result = build_branch_simulation(
                Path(args.project),
                scene=Path(args.scene),
                context=context,
                query=args.query,
                rebuild_context=args.rebuild_context,
                branch_count=args.branch_count,
                output=out,
                json_output=json_out,
                selection_output=selection_out,
                agent_tasks=args.agent_tasks,
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(f"branch_simulation: {result.output_path}")
        print(f"manifest: {result.manifest_path}")
        print(f"selection: {result.selection_path}")
        if result.agent_tasks_path:
            print(f"agent_tasks: {result.agent_tasks_path}")
            _print_agent_task_notice(result.agent_tasks_path, project=Path(args.project).resolve())
        print(f"context: {result.context_path}")
        print(f"scene: {result.scene_id}")
        print(f"branches: {result.branch_count}")
        print(f"recommended: {result.recommended_branch}")
        return 0

    if args.command == "compose-scene":
        context = Path(args.context) if args.context else None
        manifest = Path(args.branch_manifest) if args.branch_manifest else None
        selection = Path(args.branch_selection) if args.branch_selection else None
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        try:
            result = build_scene_composition(
                Path(args.project),
                scene=Path(args.scene),
                context=context,
                query=args.query,
                rebuild_context=args.rebuild_context,
                branch_manifest=manifest,
                branch_selection=selection,
                output=out,
                json_output=json_out,
                agent_tasks=args.agent_tasks,
                allow_recommended_branch=args.allow_recommended_branch,
                allow_missing_branch=args.allow_missing_branch,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"composition: {result.output_path}")
        print(f"json: {result.json_path}")
        if result.agent_tasks_path:
            print(f"agent_tasks: {result.agent_tasks_path}")
            _print_agent_task_notice(result.agent_tasks_path, project=Path(args.project).resolve())
        print(f"context: {result.context_path}")
        print(f"scene: {result.scene_id}")
        print(f"branch: {result.selected_branch}")
        print(f"characters: {result.character_count}")
        print(f"beats: {result.beat_count}")
        return 0

    return None
