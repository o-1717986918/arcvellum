"""Style engineering and reusable style-library command handlers."""

from __future__ import annotations

import json
from pathlib import Path

from ...cli_support import print_agent_task_notice as _print_agent_task_notice
from ...literary.style.review import prepare_style_semantic_review
from ...literary.style.version import build_style_profile_version
from ...platform_agent_tasks import (
    write_platform_style_prompt_eval_task,
    write_platform_style_prompt_task,
)
from ...style_compiler import StyleCompileOptions, compile_style_profile
from ...style_evaluator import StyleEvalOptions, evaluate_style
from ...style_lab import (
    active_project_style,
    build_style_skill,
    create_author_project,
    create_author_work,
    import_work_source,
    list_author_projects,
    list_style_skills,
    mount_style_skill,
    run_author_style_learning_platform_task,
)


def handle(args, parser) -> int | None:
    command = str(args.command or "")
    if command == "style-profile":
        return _compile_profile(args)
    if command == "style-eval":
        return _evaluate(args)
    if command == "style-prompt":
        return _prepare_prompt(args)
    if command == "style-prompt-eval":
        return _prepare_evaluation(args)
    if command == "prepare-style-review":
        return _prepare_review(args, parser)
    if command == "build-style-version":
        return _build_version(args, parser)
    if command == "style-lab-list":
        return _list_library(args)
    if command == "style-lab-author":
        return _create_author(args)
    if command == "style-lab-work":
        return _create_work(args)
    if command == "style-lab-import":
        return _import_source(args, parser)
    if command == "style-lab-compile":
        return _compile_library_profile(args)
    if command == "style-lab-build-skill":
        return _build_skill(args)
    if command == "style-lab-mount":
        return _mount_skill(args)
    return None


def _compile_profile(args) -> int:
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


def _evaluate(args) -> int:
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


def _prepare_prompt(args) -> int:
    result = write_platform_style_prompt_task(
        Path(args.profile_dir),
        output=Path(args.out) if args.out else None,
        json_path=Path(args.manifest_out) if args.manifest_out else None,
    )
    print(f"style_prompt_task: {result.task_path}")
    print(f"expected_style_prompt: {result.expected_report_path}")
    print(f"expected_json: {result.expected_json_path}")
    print("receiver: platform-agent")
    _print_agent_task_notice(result.task_path)
    return 0


def _prepare_evaluation(args) -> int:
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


def _prepare_review(args, parser) -> int:
    try:
        result = prepare_style_semantic_review(
            Path(args.project),
            Path(args.profile_dir),
            target_id=args.target_id,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(f"style_review: {result.review_json}")
    print(f"style_review_report: {result.review_markdown}")
    print(f"agent_tasks: {result.task}")
    _print_agent_task_notice(result.task, project=Path(args.project).resolve())
    return 0


def _build_version(args, parser) -> int:
    try:
        result = build_style_profile_version(
            Path(args.project),
            Path(args.profile_dir),
            target_id=args.target_id,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(f"style_id: {result.style_id}")
    print(f"version_id: {result.version_id}")
    print(f"content_hash: {result.content_hash}")
    print(f"version_dir: {result.version_dir}")
    print(f"manifest: {result.manifest_path}")
    print(f"created: {str(result.created).lower()}")
    return 0


def _list_library(args) -> int:
    library = Path(args.library) if args.library else None
    payload = {
        "authors": list_author_projects(library),
        "style_skills": list_style_skills(library),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _create_author(args) -> int:
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


def _create_work(args) -> int:
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


def _import_source(args, parser) -> int:
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


def _compile_library_profile(args) -> int:
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


def _build_skill(args) -> int:
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


def _mount_skill(args) -> int:
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
