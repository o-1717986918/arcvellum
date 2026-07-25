"""Project setup, retrieval, and source-ingest command handlers."""
from __future__ import annotations

from pathlib import Path

from ...canon_lint import build_canon_lint
from ...context_broker import default_context_trace_path
from ...context_packet import build_context_packet
from ...demo_project import build_demo_project
from ...init_project import InitOptions, init_work_project
from ...knowledge_store import build_knowledge_store, search_knowledge_store
from ...memory_index import build_memory_index, search_memory
from ...source_ingest import ingest_existing_work
from ...cli_support import print_agent_task_notice as _print_agent_task_notice
from .style import handle as handle_style


def handle(args, parser) -> int | None:
    style_result = handle_style(args, parser)
    if style_result is not None:
        return style_result
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

    return None
