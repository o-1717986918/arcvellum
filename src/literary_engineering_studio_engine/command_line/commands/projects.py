"""Project setup, retrieval, ingest, and style command handlers."""
from __future__ import annotations

import json
from pathlib import Path

from ...canon_lint import build_canon_lint
from ...context_broker import default_context_trace_path
from ...context_packet import build_context_packet
from ...demo_project import build_demo_project
from ...init_project import InitOptions, init_work_project
from ...knowledge_store import build_knowledge_store, search_knowledge_store
from ...memory_index import build_memory_index, search_memory
from ...platform_agent_tasks import write_platform_style_prompt_eval_task, write_platform_style_prompt_task
from ...source_ingest import ingest_existing_work
from ...style_compiler import StyleCompileOptions, compile_style_profile
from ...style_evaluator import StyleEvalOptions, evaluate_style
from ...style_lab import (
    active_project_style, build_style_skill, create_author_project, create_author_work,
    import_work_source, list_author_projects, list_style_skills, mount_style_skill,
    run_author_style_learning_platform_task,
)
from ...cli_support import print_agent_task_notice as _print_agent_task_notice
def handle(args, parser) -> int | None:
    if args.command == "init":
        result = init_work_project(
            InitOptions(
                target=Path(args.target),
                title=args.title,
                work_type=args.type,
                target_length=args.target_length,
                language=args.language,
                premise=args.premise,
                genre=args.genre,
                style_mode=args.style_mode,
            )
        )
        print(f"created: {result.root}")
        print(f"files: {len(result.files)}")
        for file in result.files:
            print(f"- {file.relative_to(result.root).as_posix()}")
        return 0

    if args.command == "demo-project":
        try:
            result = build_demo_project(Path(args.target), title=args.title, run_agent_workflow=not args.skip_workflow)
        except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        print(f"demo: {result.root}")
        print(f"draft: {result.draft_path}")
        print(f"review: {result.review_path}")
        print(f"agent_scene_review: {result.agent_scene_review}")
        print(f"agent_canon_review: {result.agent_canon_review}")
        print(f"committee: {result.committee_review}")
        print(f"workflow_state: {result.workflow_state or 'n/a'}")
        print(f"report: {result.report_path}")
        return 0

    if args.command == "index":
        result = build_memory_index(Path(args.project))
        print(f"indexed: {result.project_root}")
        print(f"index: {result.index_path}")
        print(f"sources: {result.source_count}")
        print(f"chunks: {result.chunk_count}")
        return 0

    if args.command == "search":
        hits = search_memory(Path(args.project), args.query, top_k=args.top_k)
        print(f"hits: {len(hits)}")
        for i, hit in enumerate(hits, 1):
            preview = " ".join(hit.text.split())[:160]
            print(f"{i}. score={hit.score:.1f} source={hit.source} id={hit.chunk_id}")
            print(f"   {preview}")
        return 0

    if args.command == "knowledge-build":
        out = Path(args.out) if args.out else None
        result = build_knowledge_store(Path(args.project), backend=args.backend, output=out)
        print(f"knowledge_store: {result.store_path}")
        print(f"backend: {result.backend}")
        print(f"sources: {result.source_count}")
        print(f"items: {result.item_count}")
        return 0

    if args.command == "knowledge-search":
        hits = search_knowledge_store(
            Path(args.project),
            args.query,
            top_k=args.top_k,
            backend=args.backend,
            kind=args.kind,
            canon_status=args.canon_status,
        )
        print(f"hits: {len(hits)}")
        for i, hit in enumerate(hits, 1):
            preview = " ".join(hit.text.split())[:160]
            print(
                f"{i}. score={hit.score:.1f} source={hit.source} "
                f"kind={hit.kind} canon_status={hit.canon_status} id={hit.chunk_id}"
            )
            print(f"   {preview}")
        return 0

    if args.command == "canon-lint":
        out = Path(args.out) if args.out else None
        json_out = Path(args.json_out) if args.json_out else None
        result = build_canon_lint(Path(args.project), output=out, json_output=json_out)
        print(f"canon_lint: {result.report_path}")
        print(f"json: {result.json_path}")
        print(f"status: {result.status}")
        print(f"issues: {result.issue_count}")
        print(f"blocking: {result.blocking_count}")
        print(f"warnings: {result.warning_count}")
        return 0

    if args.command == "context":
        out = Path(args.out) if args.out else None
        trace_out = Path(args.trace_out) if args.trace_out else None
        result = build_context_packet(
            Path(args.project),
            scene=Path(args.scene),
            query=args.query,
            top_k=args.top_k,
            rebuild_index=args.rebuild_index,
            output=out,
            trace_output=trace_out,
        )
        print(f"context: {result.output_path}")
        print(f"context_trace: {result.trace_path}")
        print(f"retrievals: {result.retrieval_count}")
        return 0

    if args.command in {"source-ingest", "extract-existing-work"}:
        if not args.source and not args.text:
            parser.error(f"{args.command} requires --source or --text")
        result = ingest_existing_work(
            Path(args.project),
            source=Path(args.source) if args.source else None,
            text=args.text,
            title=args.title,
            work_id=args.work_id,
            mode=args.mode,
            chunk_size=args.chunk_size,
            overwrite=args.overwrite,
        )
        print(f"source_import: {result.import_dir}")
        print(f"work_id: {result.work_id}")
        print(f"manifest: {result.manifest_path}")
        print(f"report: {result.report_path}")
        print(f"agent_task: {result.task_path}")
        print(f"sources: {result.source_count}")
        print(f"chunks: {result.chunk_count}")
        print("candidate_outputs:")
        for key, value in result.candidate_outputs.items():
            print(f"- {key}: {value}")
        print("receiver: platform-agent")
        _print_agent_task_notice(result.task_path, project=Path(args.project).resolve())
        return 0

    if args.command == "style-profile":
        result = compile_style_profile(
            StyleCompileOptions(
                corpus=Path(args.corpus),
                output_dir=Path(args.out_dir),
                name=args.name,
                author=args.author,
                mode=args.mode,
                source_note=args.source_note,
            )
        )
        print(f"style: {result.output_dir}")
        print(f"profile: {result.profile_path}")
        print(f"metrics: {result.metrics_path}")
        print(f"manifest: {result.corpus_manifest_path}")
        print(f"evaluation: {result.evaluation_dir}")
        print(f"sources: {result.source_count}")
        return 0

    if args.command == "style-eval":
        result = evaluate_style(
            StyleEvalOptions(
                profile_dir=Path(args.profile_dir),
                reference=Path(args.reference),
                candidate=Path(args.candidate),
                mode=args.mode,
                out_dir=Path(args.out_dir) if args.out_dir else None,
            )
        )
        print(f"style_eval_report: {result.report_path}")
        print(f"style_eval_metrics: {result.metrics_path}")
        print(f"mode: {result.mode}")
        print(f"overall_score: {result.overall_score}")
        print(f"risk_level: {result.risk_level}")
        return 0

    if args.command == "style-prompt":
        out = Path(args.out) if args.out else None
        manifest_out = Path(args.manifest_out) if args.manifest_out else None
        result = write_platform_style_prompt_task(
            Path(args.profile_dir),
            output=out,
            json_path=manifest_out,
        )
        print(f"style_prompt_task: {result.task_path}")
        print(f"expected_style_prompt: {result.expected_report_path}")
        print(f"expected_json: {result.expected_json_path}")
        print("receiver: platform-agent")
        _print_agent_task_notice(result.task_path)
        return 0

    if args.command == "style-prompt-eval":
        result = write_platform_style_prompt_eval_task(
            Path(args.profile_dir),
            reference=Path(args.reference),
            task_input=Path(args.input),
            mode=args.mode,
            style_prompt=Path(args.style_prompt) if args.style_prompt else None,
            output_dir=Path(args.out_dir) if args.out_dir else None,
        )
        print(f"style_prompt_eval_task: {result.task_path}")
        print(f"expected_candidate: {result.expected_report_path}")
        print(f"expected_prompt_manifest: {result.expected_json_path}")
        print("receiver: platform-agent")
        _print_agent_task_notice(result.task_path)
        return 0

    if args.command == "style-lab-list":
        library = Path(args.library) if args.library else None
        print(json.dumps({"authors": list_author_projects(library), "style_skills": list_style_skills(library)}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "style-lab-author":
        result = create_author_project(
            Path(args.library) if args.library else None,
            name=args.name,
            author_id=args.author_id,
            mode=args.mode,
            source_note=args.source_note,
        )
        print(f"style_library: {result.library_root}")
        print(f"author_id: {result.author_id}")
        print(f"author_dir: {result.author_dir}")
        print(f"manifest: {result.manifest_path}")
        return 0

    if args.command == "style-lab-work":
        result = create_author_work(
            Path(args.library) if args.library else None,
            author_id=args.author_id,
            title=args.title,
            work_id=args.work_id,
            year=args.year,
            notes=args.notes,
        )
        print(f"style_library: {result.library_root}")
        print(f"author_id: {result.author_id}")
        print(f"work_id: {result.work_id}")
        print(f"work_dir: {result.work_dir}")
        print(f"manifest: {result.manifest_path}")
        return 0

    if args.command == "style-lab-import":
        if not args.text and not args.file:
            parser.error("style-lab-import requires --text or --file")
        result = import_work_source(
            Path(args.library) if args.library else None,
            author_id=args.author_id,
            work_id=args.work_id,
            text=args.text,
            source_path=Path(args.file) if args.file else None,
            filename=args.filename,
            chunk_chars=args.chunk_chars,
        )
        print(f"source_id: {result.source_id}")
        print(f"raw: {result.raw_path}")
        print(f"normalized: {result.normalized_path}")
        print(f"manifest: {result.manifest_path}")
        print(f"chunks: {result.chunk_count}")
        print(f"chars: {result.char_count}")
        return 0

    if args.command == "style-lab-compile":
        result = run_author_style_learning_platform_task(
            Path(args.library) if args.library else None,
            author_id=args.author_id,
            profile_id=args.profile_id,
        )
        print(f"profile_dir: {result.profile_dir}")
        print(f"profile: {result.profile_path}")
        print(f"metrics: {result.metrics_path}")
        print(f"style_prompt_task: {result.style_prompt_task_path}")
        print(f"expected_style_prompt: {result.expected_style_prompt_path}")
        print(f"expected_json: {result.expected_json_path}")
        print(f"sources: {result.source_count}")
        _print_agent_task_notice(result.style_prompt_task_path)
        return 0

    if args.command == "style-lab-build-skill":
        result = build_style_skill(
            Path(args.library) if args.library else None,
            author_id=args.author_id,
            profile_id=args.profile_id,
            style_id=args.style_id,
        )
        print(f"style_id: {result.style_id}")
        print(f"skill_dir: {result.skill_dir}")
        print(f"manifest: {result.manifest_path}")
        print(f"style_markdown: {result.style_markdown_path}")
        print(f"prompt: {result.prompt_path}")
        return 0

    if args.command == "style-lab-mount":
        result = mount_style_skill(
            Path(args.project),
            library_root=Path(args.library) if args.library else None,
            style_id=args.style_id,
            allow_unreviewed=args.allow_unreviewed,
        )
        print(f"style_id: {result.style_id}")
        print(f"mount_dir: {result.mount_dir}")
        print(f"mount_manifest: {result.mount_manifest_path}")
        print(f"project_style: {result.project_style_path}")
        print(json.dumps(active_project_style(Path(args.project)), ensure_ascii=False, indent=2))
        return 0

    return None
