"""Longform planning, continuity, export, and release command handlers."""
from __future__ import annotations

from pathlib import Path

from ...approval import build_approval_summary
from ...chapter_pipeline import build_chapter_workspace
from ...cli_support import print_agent_task_notice as _print_agent_task_notice
from ...continuity_ledger import apply_continuity_ledger, prepare_continuity_ledger, prepare_continuity_ledger_review
from ...docx_export import export_markdown_to_docx
from ...export_package import build_export_package
from ...longform_audit import build_longform_audit
from ...longform_materializer import materialize_longform_plan
from ...orchestration_blueprint import build_orchestration_blueprint
from ...publish import publish_chapter
from ...reader_experience import build_chapter_obligation_tasks
from ...scene_handoff import build_scene_handoff
from ...story_architecture import prepare_story_architecture, prepare_story_architecture_review, story_architecture_status
from ...workflow_runner import run_workflow
from ...word_budget import build_word_budget
def handle(args, parser) -> int | None:
    if args.command == "orchestration-plan":
        platforms = [item.strip() for item in args.platforms.split(",")] if args.platforms else None
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        try:
            result = build_orchestration_blueprint(
                Path(args.project),
                platforms=platforms,
                output=out,
                json_output=json_out,
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(f"blueprint: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"platforms: {result.platform_count}")
        print(f"nodes: {result.node_count}")
        return 0

    if args.command == "chapter-workspace":
        scenes = [Path(item.strip()) for item in args.scenes.split(",") if item.strip()] if args.scenes else None
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        result = build_chapter_workspace(
            Path(args.project),
            chapter_id=args.chapter_id,
            scenes=scenes,
            build_missing=args.build_missing,
            review_drafts=args.review_drafts,
            agent_review=args.agent_review,
            output=out,
            json_output=json_out,
        )
        print(f"chapter: {result.chapter_id}")
        print(f"workspace: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"scenes: {result.scene_count}")
        print(f"ready: {result.ready_count}")
        print(f"blocked: {result.blocked_count}")
        return 0

    if args.command in {"word-budget", "longform-budget"}:
        try:
            result = build_word_budget(
                Path(args.project),
                target_words=args.target_words,
                volumes=args.volumes,
                genre=args.genre,
                time_span=args.time_span,
                outline=Path(args.outline) if args.outline else None,
                output=Path(args.out) if args.out else None,
                json_output=Path(args.json_out) if args.json_out else None,
                agent_tasks_output=Path(args.agent_tasks_out) if args.agent_tasks_out else None,
            )
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        print(f"word_budget: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"agent_tasks: {result.agent_tasks_path}")
        print(f"scene_inventory_tasks: {result.scene_inventory_tasks_path}")
        print(f"chapter_obligation_tasks: {result.chapter_obligation_tasks_path}")
        _print_agent_task_notice(result.agent_tasks_path, project=Path(args.project).resolve())
        _print_agent_task_notice(result.scene_inventory_tasks_path, project=Path(args.project).resolve())
        _print_agent_task_notice(result.chapter_obligation_tasks_path, project=Path(args.project).resolve())
        print(f"target_words: {result.target_words}")
        print(f"target_chinese_chars: {result.target_words}")
        print(f"volumes: {result.volume_count}")
        print(f"chapters: {result.chapter_count}")
        print(f"scenes: {result.scene_count}")
        print(f"status: {result.status}")
        print(f"issues: {result.issue_count}")
        print("receiver: platform-agent")
        return 0

    if args.command == "chapter-obligation":
        try:
            result = build_chapter_obligation_tasks(
                Path(args.project),
                chapter_id=args.chapter_id,
                output=Path(args.out) if args.out else None,
                json_output=Path(args.json_out) if args.json_out else None,
                agent_tasks_output=Path(args.agent_tasks_out) if args.agent_tasks_out else None,
            )
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        print(f"chapter_obligation: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"agent_tasks: {result.agent_tasks_path}")
        _print_agent_task_notice(result.agent_tasks_path, project=Path(args.project).resolve())
        print(f"chapter_id: {result.chapter_id}")
        print(f"status: {result.status}")
        print("receiver: platform-agent")
        return 0

    if args.command == "materialize-longform-plan":
        try:
            result = materialize_longform_plan(Path(args.project))
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        print(f"manifest: {result.manifest_path}")
        print(f"outline: {result.outline_path}")
        print(f"chapters: {result.chapter_count}")
        print(f"scenes: {len(result.scene_paths)}")
        return 0

    if args.command == "scene-handoff":
        scene_id = Path(args.scene).stem
        try:
            path = build_scene_handoff(Path(args.project), scene_id)
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        print(f"handoff: {path}")
        return 0

    if args.command == "prepare-story-architecture":
        candidate, sidecar = prepare_story_architecture(Path(args.project))
        print(f"candidate: {candidate}")
        print(f"agent_tasks: {sidecar}")
        _print_agent_task_notice(sidecar, project=Path(args.project).resolve())
        return 0

    if args.command == "prepare-story-architecture-review":
        review, sidecar = prepare_story_architecture_review(Path(args.project))
        print(f"review: {review}")
        print(f"agent_tasks: {sidecar}")
        _print_agent_task_notice(sidecar, project=Path(args.project).resolve())
        return 0

    if args.command == "story-architecture-status":
        passed, message, _payload = story_architecture_status(Path(args.project), require_review=True)
        print(f"status: {'pass' if passed else 'blocked'}")
        print(f"message: {message}")
        return 0 if passed else 2

    if args.command == "prepare-continuity-ledger":
        target, sidecar = prepare_continuity_ledger(Path(args.project), Path(args.scene).stem)
        print(f"delta: {target}")
        print(f"agent_tasks: {sidecar}")
        _print_agent_task_notice(sidecar, project=Path(args.project).resolve())
        return 0

    if args.command == "prepare-continuity-ledger-review":
        target, sidecar = prepare_continuity_ledger_review(Path(args.project), Path(args.scene).stem)
        print(f"review: {target}")
        print(f"agent_tasks: {sidecar}")
        _print_agent_task_notice(sidecar, project=Path(args.project).resolve())
        return 0

    if args.command == "apply-continuity-ledger":
        questions, promises = apply_continuity_ledger(Path(args.project), Path(args.scene).stem)
        print(f"reader_questions: {questions}")
        print(f"promises: {promises}")
        return 0

    if args.command == "longform-audit":
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        graph_out = Path(args.graph_out) if args.graph_out else None
        result = build_longform_audit(
            Path(args.project),
            target_length=args.target_length,
            output=out,
            json_output=json_out,
            graph_output=graph_out,
        )
        print(f"audit: {result.markdown_path}")
        print(f"json: {result.json_path}")
        print(f"graph: {result.graph_path}")
        print(f"chapters: {result.chapter_count}")
        print(f"scenes: {result.scene_count}")
        print(f"draft_chars: {result.draft_chars}")
        print(f"issues: {result.issue_count}")
        return 0

    if args.command == "export-package":
        out_dir = Path(args.out_dir) if args.out_dir else None
        try:
            result = build_export_package(
                Path(args.project),
                chapter_id=args.chapter_id,
                include_blocked=args.include_blocked,
                rebuild_chapter=args.rebuild_chapter,
                output_dir=out_dir,
                formats=args.formats,
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(f"chapter: {result.chapter_id}")
        print(f"output_dir: {result.output_dir}")
        print(f"manifest: {result.manifest_path}")
        print(f"novel: {result.novel_path}")
        print(f"screenplay: {result.screenplay_path}")
        print(f"video_prompt_pack: {result.video_prompt_path}")
        for key, path in result.docx_outputs.items():
            print(f"{key}_docx: {path}")
        for key, path in result.docx_layout_plans.items():
            print(f"{key}_docx_layout: {path}")
        for key, path in result.docx_inspections.items():
            print(f"{key}_docx_inspection: {path}")
        print(f"exported_scenes: {result.exported_scene_count}")
        print(f"skipped_scenes: {result.skipped_scene_count}")
        return 0

    if args.command == "export-docx":
        out = Path(args.out) if args.out else None
        try:
            result = export_markdown_to_docx(
                Path(args.source),
                out,
                title=args.title,
                kind=args.kind,
                overwrite=not args.no_overwrite,
            )
        except (FileNotFoundError, FileExistsError, ValueError) as exc:
            parser.error(str(exc))
        print(f"source: {result.source_path}")
        print(f"docx: {result.docx_path}")
        print(f"layout_plan: {result.layout_plan_path}")
        print(f"inspection: {result.inspection_path}")
        print(f"title: {result.title}")
        print(f"paragraphs: {result.paragraph_count}")
        print(f"warnings: {result.warning_count}")
        return 0

    if args.command == "publish-chapter":
        out_dir = Path(args.out_dir) if args.out_dir else None
        try:
            result = publish_chapter(
                Path(args.project),
                chapter_id=args.chapter_id,
                release_id=args.release_id,
                approval_run_id=args.approval_run_id,
                allow_unapproved=args.allow_unapproved,
                rebuild_chapter=args.rebuild_chapter,
                rebuild_export=args.rebuild_export,
                output_dir=out_dir,
                overwrite=args.overwrite,
                export_formats=args.export_formats,
            )
        except (RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"release: {result.release_dir}")
        print(f"manifest: {result.manifest_path}")
        print(f"notes: {result.notes_path}")
        print(f"rollback: {result.rollback_path}")
        print(f"latest: {result.latest_path}")
        print(f"status: {result.status}")
        print(f"chapter: {result.chapter_id}")
        print(f"release_id: {result.release_id}")
        print(f"published_scenes: {result.published_scene_count}")
        print(f"approval_run_id: {result.approval_run_id or 'n/a'}")
        return 0

    if args.command == "run-workflow":
        out_dir = Path(args.out_dir) if args.out_dir else None
        result = run_workflow(
            Path(args.project),
            mode=args.mode,
            scene=Path(args.scene),
            chapter_id=args.chapter_id,
            target_length=args.target_length,
            include_blocked=args.include_blocked,
            overwrite_draft=args.overwrite_draft,
            generate_candidate=args.generate_candidate,
            promote_candidate=args.promote_candidate,
            agent_review=args.agent_review,
            agent_tasks=args.agent_tasks,
            provider=args.provider,
            output_dir=out_dir,
            run_id=args.run_id or None,
            resumed_from=args.resume_run_id,
            overwrite_run=args.overwrite_run,
        )
        print(f"run_id: {result.run_id}")
        print(f"status: {result.status}")
        print(f"state: {result.state_path}")
        print(f"log: {result.log_path}")
        print(f"nodes: {result.node_count}")
        print(f"blocked: {str(result.blocked).lower()}")
        return 0

    if args.command == "approval-summary":
        out = Path(args.out) if args.out else None
        result = build_approval_summary(Path(args.project), run_id=args.run_id, output=out)
        print(f"approval_summary: {result.output_path}")
        print(f"records: {result.record_count}")
        print(f"tasks: {result.task_count}")
        return 0

    return None
