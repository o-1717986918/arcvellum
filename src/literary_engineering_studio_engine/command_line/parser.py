"""Parser registration for the stable Engine CLI command surface."""
from __future__ import annotations

import argparse

from ..agent_provider import AGENT_PROVIDERS
from ..asset_workshop import ASSET_TYPES
from .policy import FORMAL_HELP_COMMANDS, FORMAL_HELP_METAVAR
from ..dify_dsl import DEFAULT_DIFY_DSL_PATH
from ..docx_export import DOCX_KINDS
from ..knowledge_store import KNOWLEDGE_BACKENDS
from ..source_ingest import INGEST_MODES
from ..workflow_runner import WORKFLOW_MODES
from .parser_style import register_style_commands
def build_parser(*, full_help: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lew",
        description="Literary Engineering Workbench command line tools.",
        epilog="Formal hosts should start with: lew formal-help, then lew workflow-dashboard <project>, lew task-next <project> --route <route>, lew task-open <project> --task-id <id>. Low-level commands are route internals unless a task package asks for them.",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar=None if full_help else FORMAL_HELP_METAVAR)

    formal_help = sub.add_parser("formal-help", help="Show the state-machine-first host loop for formal Skill work.")
    formal_help.add_argument("project", nargs="?", default="", help="Optional work project directory for copyable commands.")
    formal_help.add_argument("--route", default="scene-development", help="Route to demonstrate, such as scene-development or longform-planning.")

    sub.add_parser("help-all", help="Show every low-level command for maintainers and debugging.")

    protocol = sub.add_parser("protocol", help="Print the mandatory agent/CLI run protocol for a route.")
    protocol.add_argument("route", nargs="?", default="", help="Route key such as scene-development, style-engineering, or export-and-release. Omit to list routes.")
    protocol.add_argument("--json", action="store_true", help="Output machine-readable JSON.")

    init = sub.add_parser("init", help="Initialize a fictional work project.")
    init.add_argument("target", help="Target project directory.")
    init.add_argument("--title", required=True, help="Work title.")
    init.add_argument("--type", default="novel", choices=["novel", "screenplay", "pseudo-record"])
    init.add_argument("--target-length", type=int, default=30000)
    init.add_argument("--language", default="zh-CN")
    init.add_argument("--premise", default="")
    init.add_argument("--genre", default="")
    init.add_argument("--style-mode", default="public_domain_or_authorized")

    demo = sub.add_parser("demo-project", help="Build a deterministic demo project with agent review artifacts.")
    demo.add_argument("target", help="Target demo project directory.")
    demo.add_argument("--title", default="文学工程 Demo")
    demo.add_argument("--skip-workflow", action="store_true", help="Create artifacts without running the demo workflow.")

    index = sub.add_parser("index", help="Build a lightweight memory index for a work project.")
    index.add_argument("project", help="Work project directory.")

    search = sub.add_parser("search", help="Search the lightweight memory index.")
    search.add_argument("project", help="Work project directory.")
    search.add_argument("query", help="Search query.")
    search.add_argument("--top-k", type=int, default=8)

    knowledge_build = sub.add_parser("knowledge-build", help="Build a metadata-rich knowledge store for a work project.")
    knowledge_build.add_argument("project", help="Work project directory.")
    knowledge_build.add_argument("--backend", default="json", choices=sorted(KNOWLEDGE_BACKENDS))
    knowledge_build.add_argument("--out", default="", help="Output store path. Defaults to memory/knowledge_store.json.")

    knowledge_search = sub.add_parser("knowledge-search", help="Search the metadata-rich knowledge store.")
    knowledge_search.add_argument("project", help="Work project directory.")
    knowledge_search.add_argument("query", help="Search query.")
    knowledge_search.add_argument("--top-k", type=int, default=8)
    knowledge_search.add_argument("--backend", default="json", choices=sorted(KNOWLEDGE_BACKENDS))
    knowledge_search.add_argument("--kind", default="", help="Filter by source kind, such as canon, characters, drafts.")
    knowledge_search.add_argument("--canon-status", default="", help="Filter by confirmed, planned, candidate, or working.")

    canon_lint = sub.add_parser("canon-lint", help="Lint project canon, character, scene, chapter, and foreshadowing consistency.")
    canon_lint.add_argument("project", help="Work project directory.")
    canon_lint.add_argument("--out", default="", help="Output markdown report path. Defaults to reviews/canon_lint.md.")
    canon_lint.add_argument("--json-out", default="", help="Output JSON report path. Defaults to reviews/canon_lint.json.")

    context = sub.add_parser("context", help="Build a scene context packet.")
    context.add_argument("project", help="Work project directory.")
    context.add_argument("--scene", default="scenes/scene_0001.yaml", help="Scene yaml path.")
    context.add_argument("--query", default="", help="Extra retrieval query.")
    context.add_argument("--top-k", type=int, default=8)
    context.add_argument("--rebuild-index", action="store_true")
    context.add_argument("--out", default="", help="Output markdown path.")
    context.add_argument("--trace-out", default="", help="Output context trace JSON path. Defaults to the context packet sidecar.")

    for command, help_text in (
        ("source-ingest", "Import an existing work and write a platform-agent reverse extraction task."),
        ("extract-existing-work", "Alias for source-ingest."),
    ):
        source_ingest = sub.add_parser(command, help=help_text)
        source_ingest.add_argument("project", help="Work project directory.")
        source_ingest.add_argument("--source", default="", help="Source .txt/.md/.docx file or directory.")
        source_ingest.add_argument("--text", default="", help="Inline source text.")
        source_ingest.add_argument("--title", default="", help="Source work title.")
        source_ingest.add_argument("--work-id", default="", help="Stable import id. Defaults to title/source stem.")
        source_ingest.add_argument("--mode", default="continuation", choices=sorted(INGEST_MODES))
        source_ingest.add_argument(
            "--chunk-size",
            type=int,
            default=6000,
            help="Target characters per semantic source chunk; structural boundaries are preserved.",
        )
        source_ingest.add_argument(
            "--rights-declaration",
            default="",
            help="Rights or authorization declaration recorded with every preserved source.",
        )
        source_ingest.add_argument("--overwrite", action="store_true", help="Overwrite an existing import directory.")

    archaeology_aggregate = sub.add_parser(
        "archaeology-aggregate",
        help="Deterministically aggregate completed source chunk extractions.",
    )
    archaeology_aggregate.add_argument("project", help="Work project directory.")
    archaeology_aggregate.add_argument("--work-id", required=True, help="Stable source import id.")

    archaeology_materialize = sub.add_parser(
        "archaeology-materialize",
        help="Materialize passed archaeology reconstruction assets into the Archive candidate queue.",
    )
    archaeology_materialize.add_argument("project", help="Work project directory.")
    archaeology_materialize.add_argument("--work-id", required=True, help="Stable source import id.")

    register_style_commands(sub)

    agent_run = sub.add_parser("agent-run", help="Run a generic auditable agent task.")
    agent_run.add_argument("project", help="Work project directory.")
    agent_run.add_argument("--agent-id", required=True, help="Stable agent id, such as scene-reviewer.")
    agent_run.add_argument("--task", required=True, help="Short task name or review objective.")
    agent_run.add_argument("--system", default="", help="System prompt file. Relative paths resolve from project root.")
    agent_run.add_argument("--user", default="", help="User prompt file. Relative paths resolve from project root.")
    agent_run.add_argument("--system-text", default="", help="Inline system prompt text.")
    agent_run.add_argument("--user-text", default="", help="Inline user prompt text.")
    agent_run.add_argument("--provider", default="auto", choices=sorted(AGENT_PROVIDERS))
    agent_run.add_argument("--out-dir", default="", help="Output directory. Defaults to agents/runs/{run_id}.")

    agent_validate = sub.add_parser("agent-validate", help="Validate a parsed agent output against a workbench schema.")
    agent_validate.add_argument("project", help="Work project directory.")
    agent_validate.add_argument("--schema", required=True, help="Schema name, such as scene_review.v1.")
    agent_validate.add_argument("--run-id", default="", help="Agent run id under agents/runs/.")
    agent_validate.add_argument("--run-dir", default="", help="Agent run directory. Relative paths resolve from project root.")

    agent_repair = sub.add_parser("agent-repair", help="Repair an agent JSON output through provider and validate it.")
    agent_repair.add_argument("project", help="Work project directory.")
    agent_repair.add_argument("--schema", required=True, help="Schema name, such as scene_review.v1.")
    agent_repair.add_argument("--run-id", default="", help="Agent run id under agents/runs/.")
    agent_repair.add_argument("--run-dir", default="", help="Agent run directory. Relative paths resolve from project root.")
    agent_repair.add_argument("--provider", default="auto", choices=sorted(AGENT_PROVIDERS))

    agent_review_scene = sub.add_parser("agent-review-scene", help="Write a formal platform-agent scene review task.")
    agent_review_scene.add_argument("project", help="Work project directory.")
    agent_review_scene.add_argument("--scene", default="scenes/scene_0001.yaml")
    agent_review_scene.add_argument("--draft", default="", help="Draft path. Defaults to drafts/scenes/{scene_id}.md.")
    agent_review_scene.add_argument("--out", default="", help="Expected markdown report path.")
    agent_review_scene.add_argument("--json-out", default="", help="Expected JSON result path.")
    agent_review_scene.add_argument(
        "--materialization-scope",
        choices=("full", "scene"),
        default="full",
        help="Validate the full inventory or only the staged active scene.",
    )

    agent_canon_review = sub.add_parser("agent-canon-review", help="Write a formal platform-agent canon and continuity review task.")
    agent_canon_review.add_argument("project", help="Work project directory.")

    agent_build_json = sub.add_parser("agent-build-json", help="Write a platform-agent task to draft JSON for a named schema.")
    agent_build_json.add_argument("project", help="Work project directory.")
    agent_build_json.add_argument("--schema", required=True, help="Schema name, such as json_patch_plan.v1.")
    agent_build_json.add_argument("--agent-id", default="json-builder")
    agent_build_json.add_argument("--task", default="build-json")
    agent_build_json.add_argument("--source", default="", help="Optional source file.")
    agent_build_json.add_argument("--target", default="", help="Optional target path or object.")
    agent_build_json.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
    agent_build_json.add_argument("--out-dir", default="", help="Output run directory.")

    agent_plan_patch = sub.add_parser("agent-plan-patch", help="Write a platform-agent task for a controlled writeback patch plan.")
    agent_plan_patch.add_argument("project", help="Work project directory.")
    agent_plan_patch.add_argument("--target", required=True, help="Safe relative target path.")
    agent_plan_patch.add_argument("--source", default="", help="Optional source file.")
    agent_plan_patch.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
    agent_plan_patch.add_argument("--out", default="", help="Output markdown path.")
    agent_plan_patch.add_argument("--json-out", default="", help="Output JSON path.")

    agent_style_prompt = sub.add_parser("agent-style-prompt", help="Write a platform-agent task for style_prompt.md and schema JSON.")
    agent_style_prompt.add_argument("profile_dir", help="Directory containing style-profile.md and style_metrics.json.")
    agent_style_prompt.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
    agent_style_prompt.add_argument("--out", default="", help="Output style prompt path. Defaults to profile_dir/style_prompt.md.")
    agent_style_prompt.add_argument("--json-out", default="", help="Output agent JSON path. Defaults to profile_dir/style_prompt.agent.json.")

    agent_committee = sub.add_parser("agent-committee", help="Write a formal platform-agent review committee task.")
    agent_committee.add_argument("project", help="Work project directory.")
    agent_committee.add_argument("--subject", required=True, help="Review subject label.")
    agent_committee.add_argument("--source", default="", help="Optional source file.")

    agent_task_status = sub.add_parser("agent-task-status", help="Scan platform-agent sidecars and expected artifacts.")
    agent_task_status.add_argument("project", help="Work project directory.")
    agent_task_status.add_argument("--out", default="", help="Output markdown path. Defaults to workflow/agent_task_status.md.")
    agent_task_status.add_argument("--json-out", default="", help="Output JSON path. Defaults to workflow/agent_task_status.json.")

    route_audit = sub.add_parser("route-audit", help="Audit route gates and pending platform-agent tasks.")
    route_audit.add_argument("project", help="Work project directory.")
    route_audit.add_argument("--route", default="", help="Route key such as scene-development, longform-planning, or export-and-release.")
    route_audit.add_argument("--out", default="", help="Output markdown path. Defaults to workflow/route_audit.md.")
    route_audit.add_argument("--json-out", default="", help="Output JSON path. Defaults to workflow/route_audit.json.")
    route_audit.add_argument("--full-state", action="store_true", help="Also rebuild the full route state; scene-development defaults to a current-scene snapshot.")

    workflow_state = sub.add_parser("workflow-state", help="Write a persistent formal-route state ledger.")
    workflow_state.add_argument("project", help="Work project directory.")
    workflow_state.add_argument("--route", default="scene-development", help="Route key. Supports scene-development, longform-planning, source-ingest, style-engineering, character-and-world-assets, review-and-audit, export-and-release, and overall.")
    workflow_state.add_argument("--out", default="", help="Output markdown path. Defaults to workflow/route_state.md.")
    workflow_state.add_argument("--json-out", default="", help="Output JSON path. Defaults to workflow/route_state.json.")

    task_next = sub.add_parser("task-next", help="Issue the next CLI-mediated platform-agent task for a formal route.")
    task_next.add_argument("project", help="Work project directory.")
    task_next.add_argument("--route", default="scene-development", help="Route key. Supports scene-development, longform-planning, source-ingest, style-engineering, character-and-world-assets, review-and-audit, and export-and-release.")
    task_next.add_argument("--scene", default="", help="Optional scene yaml path. Defaults to the first blocked scene.")
    task_next.add_argument("--force", action="store_true", help="Refresh an existing active task for the current state.")

    task_open = sub.add_parser("task-open", help="Open a CLI-mediated platform-agent task package.")
    task_open.add_argument("project", help="Work project directory.")
    task_open.add_argument("--task-id", required=True)

    task_submit = sub.add_parser("task-submit", help="Record platform-agent outputs for a CLI-mediated task.")
    task_submit.add_argument("project", help="Work project directory.")
    task_submit.add_argument("--task-id", required=True)
    task_submit.add_argument("--from", dest="artifacts", action="append", default=[], help="Artifact path to submit. May be repeated.")
    task_submit.add_argument("--note", default="")

    task_complete = sub.add_parser("task-complete", help="Validate expected outputs and complete a CLI-mediated task.")
    task_complete.add_argument("project", help="Work project directory.")
    task_complete.add_argument("--task-id", required=True)
    task_complete.add_argument("--handled-by", default="platform-agent")
    task_complete.add_argument("--note", action="append", default=[])

    task_revert = sub.add_parser("task-revert-submission", help="Maintainer/runtime recovery: revoke a failed task submission after output rollback.")
    task_revert.add_argument("project", help="Work project directory.")
    task_revert.add_argument("--task-id", required=True)
    task_revert.add_argument("--reason", default="")

    task_contract_audit = sub.add_parser("task-contract-audit", help="Audit emitted task packages against authoritative semantic contracts.")
    task_contract_audit.add_argument("project", help="Work project directory.")
    task_contract_audit.add_argument("--out", default="")
    task_contract_audit.add_argument("--json-out", default="")

    workflow_advance = sub.add_parser("workflow-advance", help="Refresh derived workflow state without manually overriding gates.")
    workflow_advance.add_argument("project", help="Work project directory.")
    workflow_advance.add_argument("--route", default="scene-development", help="Route key. Supports scene-development, longform-planning, source-ingest, style-engineering, character-and-world-assets, review-and-audit, and export-and-release.")

    workflow_events = sub.add_parser("workflow-events", help="Render CLI-mediated task event history.")
    workflow_events.add_argument("project", help="Work project directory.")
    workflow_events.add_argument("--out", default="", help="Output markdown path. Defaults to workflow/events.md.")

    workflow_dashboard = sub.add_parser("workflow-dashboard", help="Build a cross-route read-only workflow dashboard.")
    workflow_dashboard.add_argument("project", help="Work project directory.")
    workflow_dashboard.add_argument("--out", default="", help="Output markdown path. Defaults to workflow/dashboard/workflow_dashboard.md.")
    workflow_dashboard.add_argument("--json-out", default="", help="Output JSON path. Defaults to workflow/dashboard/workflow_dashboard.json.")
    workflow_dashboard.add_argument("--html-out", default="", help="Output HTML path. Defaults to workflow/dashboard/workflow_dashboard.html.")

    workflow_validate = sub.add_parser("workflow-validate", help="Validate workflow state, task, submission, completion, and event ledgers.")
    workflow_validate.add_argument("project", help="Work project directory.")
    workflow_validate.add_argument("--route", default="scene-development", help="Route key used when refreshing state before validation.")
    workflow_validate.add_argument("--state", default="", help="Existing workflow state JSON. Defaults to rebuilding workflow/route_state.json.")
    workflow_validate.add_argument("--out", default="", help="Output markdown path. Defaults to workflow/workflow_contract.md.")
    workflow_validate.add_argument("--json-out", default="", help="Output JSON path. Defaults to workflow/workflow_contract.json.")

    prompt_list = sub.add_parser("prompt-registry-list", help="List registered file-backed prompt assets.")
    prompt_list.add_argument("--skill-root", default="", help="Skill root containing templates/prompt_assets. Defaults to auto-detect.")
    prompt_list.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")

    prompt_validate = sub.add_parser("prompt-registry-validate", help="Validate prompt assets and task registry prompt ids.")
    prompt_validate.add_argument("--skill-root", default="", help="Skill root containing templates/prompt_assets. Defaults to auto-detect.")
    prompt_validate.add_argument("--no-task-registry", action="store_true", help="Do not verify task_registry prompt ids.")
    prompt_validate.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")

    prompt_preview = sub.add_parser("prompt-preview", help="Preview the prompt asset resolved for one prompt_asset_id.")
    prompt_preview.add_argument("prompt_asset_id")
    prompt_preview.add_argument("--skill-root", default="", help="Skill root containing templates/prompt_assets. Defaults to auto-detect.")
    prompt_preview.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")

    director_chat = sub.add_parser("director-chat", help="Run the top-level creative director agent for one user direction.")
    director_chat.add_argument("project", help="Work project directory.")
    director_chat.add_argument("--message", required=True, help="High-level creative direction from the user.")
    director_chat.add_argument("--provider", default="auto", choices=sorted(AGENT_PROVIDERS))
    director_chat.add_argument("--no-execute", action="store_true", help="Plan and record the director decision without running the delegated workflow.")
    director_chat.add_argument("--agent-tasks", action="store_true", help="Ask delegated workflows to emit platform-agent task sidecars.")

    director_status = sub.add_parser("director-status", help="Show project status as seen by the creative director.")
    director_status.add_argument("project", help="Work project directory.")
    director_status.add_argument("--limit", type=int, default=8)

    for command, asset_type, help_text in [
        ("agent-create-character", "character", "Write a platform-agent task for a character profile candidate."),
        ("agent-create-background-story", "background-story", "Write a platform-agent task for a hidden background-story candidate."),
        ("agent-create-relationship", "relationship", "Write a platform-agent task for a relationship graph candidate."),
        ("agent-create-world", "world", "Write a platform-agent task for a world-rules candidate."),
        ("agent-create-location", "location", "Write a platform-agent task for a location candidate."),
        ("agent-create-organization", "organization", "Write a platform-agent task for an organization candidate."),
        ("agent-create-outline", "outline", "Write a platform-agent task for a plot outline candidate."),
        ("agent-create-chapter-plan", "chapter-plan", "Write a platform-agent task for a chapter-plan candidate."),
        ("agent-create-scene-list", "scene-list", "Write a platform-agent task for a scene-list candidate."),
    ]:
        create = sub.add_parser(command, help=help_text)
        create.set_defaults(asset_type=asset_type)
        create.add_argument("project", help="Work project directory.")
        create.add_argument("--brief", default="", help="Creative brief or constraints for the candidate.")
        create.add_argument("--target-id", default="", help="Stable id for the target character/location/organization when useful.")
        create.add_argument("--source", default="", help="Optional source file. Relative paths resolve from project root.")
        create.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
        create.add_argument("--out-dir", default="", help="Legacy compatibility only; formal command writes task sidecars next to expected outputs.")

    create_asset = sub.add_parser("asset-create", help="Write a platform-agent task for any supported candidate asset by type.")
    create_asset.add_argument("project", help="Work project directory.")
    create_asset.add_argument("--type", required=True, choices=ASSET_TYPES)
    create_asset.add_argument("--brief", default="")
    create_asset.add_argument("--target-id", default="")
    create_asset.add_argument("--source", default="")
    create_asset.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
    create_asset.add_argument("--out-dir", default="", help="Legacy compatibility only; formal command writes task sidecars next to expected outputs.")

    seed_assets = sub.add_parser("seed-project-assets", help="Create stable platform-agent sidecars for a project's foundational world and protagonist assets.")
    seed_assets.add_argument("project", help="Work project directory.")

    list_assets = sub.add_parser("list-candidate-assets", help="List candidate assets created by agent asset commands.")
    list_assets.add_argument("project", help="Work project directory.")
    list_assets.add_argument("--type", default="", choices=("", *ASSET_TYPES))

    review_asset = sub.add_parser("review-candidate-asset", help="Write a platform-agent task to review a candidate asset before promotion.")
    review_asset.add_argument("project", help="Work project directory.")
    review_asset.add_argument("candidate", help="Candidate path or candidate id.")
    review_asset.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")

    promote_asset = sub.add_parser("promote-candidate-asset", help="Promote any reviewed and approved candidate asset.")
    promote_asset.add_argument("project", help="Work project directory.")
    promote_asset.add_argument("candidate", help="Candidate path or candidate id.")
    promote_asset.add_argument("--group", default="", choices=("", "character", "world", "outline"))
    promote_asset.add_argument("--approval-run-id", default="")
    promote_asset.add_argument("--allow-unapproved", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass approval gates.")

    for command, group, help_text in [
        ("promote-character-candidate", "character", "Promote a character/background/relationship candidate."),
        ("promote-world-candidate", "world", "Promote a world/location/organization candidate."),
        ("promote-outline-candidate", "outline", "Promote an outline/chapter/scene-list candidate."),
    ]:
        promote = sub.add_parser(command, help=help_text)
        promote.set_defaults(promote_group=group)
        promote.add_argument("project", help="Work project directory.")
        promote.add_argument("candidate", help="Candidate path or candidate id.")
        promote.add_argument("--approval-run-id", default="")
        promote.add_argument("--allow-unapproved", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass approval gates.")

    draft = sub.add_parser("draft-scene", help="Create a scene draft workspace from a context packet.")
    draft.add_argument("project", help="Work project directory.")
    draft.add_argument("--scene", default="scenes/scene_0001.yaml")
    draft.add_argument("--context", default="", help="Existing context packet path.")
    draft.add_argument("--query", default="", help="Extra retrieval query when context needs rebuilding.")
    draft.add_argument("--rebuild-context", action="store_true")
    draft.add_argument("--out", default="", help="Output draft path.")

    review = sub.add_parser("review-scene", help="Review a scene draft workspace.")
    review.add_argument("project", help="Work project directory.")
    review.add_argument("draft", help="Draft markdown path.")
    review.add_argument("--out", default="", help="Output review report path.")

    generate = sub.add_parser("generate-scene", help="Write a formal platform-agent scene generation task.")
    generate.add_argument("project", help="Work project directory.")
    generate.add_argument("--scene", default="scenes/scene_0001.yaml")
    generate.add_argument("--context", default="", help="Existing context packet path.")
    generate.add_argument("--composition", default="", help="Existing scene composition path. Defaults to drafts/compositions/{scene_id}_composition.md.")
    generate.add_argument("--query", default="", help="Extra retrieval query when context needs rebuilding.")
    generate.add_argument("--rebuild-context", action="store_true")
    generate.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal command always targets the platform agent.")
    generate.add_argument("--out", default="", help="Output candidate markdown path.")
    generate.add_argument("--agent-tasks", action="store_true", help="Legacy compatibility only; formal command always writes a platform-agent task.")
    generate.add_argument("--materialization-scope", choices=("full", "scene"), default="full", help="Validate the full inventory or only the staged active scene.")
    generate.add_argument("--allow-unselected-composition", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass branch-selection gates.")
    generate.add_argument("--allow-missing-composition", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass scene-composition gates.")

    revise = sub.add_parser("revise-scene", help="Write a formal platform-agent scene revision task.")
    revise.add_argument("project", help="Work project directory.")
    revise.add_argument("--scene", default="scenes/scene_0001.yaml")
    revise.add_argument("--draft", default="", help="Draft path. Defaults to drafts/scenes/{scene_id}.md.")
    revise.add_argument("--review", default="", help="Review JSON/Markdown path. Defaults to platform Agent review JSON or static review.")
    revise.add_argument("--query", default="", help="Extra retrieval query when context needs rebuilding.")
    revise.add_argument("--rebuild-context", action="store_true")
    revise.add_argument("--out", default="", help="Expected revision candidate path. Defaults to drafts/revisions/{scene_id}_revision.md.")
    revise.add_argument("--report-out", default="", help="Expected revision report path.")
    revise.add_argument("--manifest-out", default="", help="Expected revision manifest JSON path.")
    revise.add_argument("--prompt-manifest-out", default="", help="Revision prompt manifest JSON path.")
    revise.add_argument("--agent-tasks-out", default="", help="Revision task sidecar path.")

    promote = sub.add_parser("promote-candidate", help="Promote a generated scene candidate into the draft review lane.")
    promote.add_argument("project", help="Work project directory.")
    promote.add_argument("--scene", default="scenes/scene_0001.yaml")
    promote.add_argument("--candidate", default="", help="Candidate markdown path. Defaults to latest candidate for the scene.")
    promote.add_argument("--out", default="", help="Output draft path. Defaults to drafts/scenes/{scene_id}.md.")
    promote.add_argument("--overwrite", action="store_true", help="Replace an existing scene draft.")
    promote.add_argument("--approval-run-id", default="", help="Optional workflow approve run id used as selection evidence.")
    promote.add_argument("--selection-note", default="", help="Human note explaining why this candidate was selected.")
    promote.add_argument("--allow-unreviewed", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass candidate-specific platform review.")
    promote.add_argument("--allow-review-notes", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass unresolved review notes.")

    state_evolve = sub.add_parser("state-evolve", help="Create a reviewable character state evolution patch from a scene artifact.")
    state_evolve.add_argument("project", help="Work project directory.")
    state_evolve.add_argument("--scene", default="scenes/scene_0001.yaml")
    state_evolve.add_argument("--source", default="", help="Draft, candidate, composition markdown, or composition JSON path. Defaults to the scene draft when present.")
    state_evolve.add_argument("--out", default="", help="Output patch markdown path.")
    state_evolve.add_argument("--json-out", default="", help="Output patch JSON path.")
    state_evolve.add_argument("--agent-tasks", action="store_true", help="Write a platform-agent task sidecar for reviewing the state patch.")

    canon_evolve = sub.add_parser("canon-evolve", help="Create a platform-agent canon writeback candidate task for a promoted scene.")
    canon_evolve.add_argument("project", help="Work project directory.")
    canon_evolve.add_argument("--scene", default="scenes/scene_0001.yaml")
    canon_evolve.add_argument("--source", default="", help="Promoted draft or candidate path. Defaults to promoted scene draft.")
    canon_evolve.add_argument("--out", default="", help="Output canon patch markdown path.")
    canon_evolve.add_argument("--json-out", default="", help="Output canon patch JSON path.")

    canon_backlog = sub.add_parser("canon-backlog", help="List canon writeback candidates and applied patch state.")
    canon_backlog.add_argument("project", help="Work project directory.")
    canon_backlog.add_argument("--out", default="", help="Output backlog markdown path. Defaults to canon/patches/canon_backlog.md.")
    canon_backlog.add_argument("--json-out", default="", help="Output backlog JSON path. Defaults to canon/patches/canon_backlog.json.")

    canon_apply = sub.add_parser("canon-apply", help="Apply an approved canon patch into the canon change ledger.")
    canon_apply.add_argument("project", help="Work project directory.")
    canon_apply.add_argument("--patch", default="", help="Canon patch JSON path. Defaults to latest unapplied patch.")
    canon_apply.add_argument("--approval-run-id", default="", help="Workflow approval run id. Defaults to patch id.")
    canon_apply.add_argument("--allow-unapproved", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass approval gates.")
    canon_apply.add_argument("--out", default="", help="Output apply markdown report path.")
    canon_apply.add_argument("--json-out", default="", help="Output apply JSON manifest path.")

    state_apply = sub.add_parser("state-apply", help="Apply an approved character state patch to character files.")
    state_apply.add_argument("project", help="Work project directory.")
    state_apply.add_argument("--patch", default="", help="State patch JSON path. Defaults to latest *_state_patch.json.")
    state_apply.add_argument("--approval-run-id", default="", help="Workflow run id with an approve record.")
    state_apply.add_argument("--allow-unapproved", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass approval gates.")
    state_apply.add_argument("--allow-unresolved", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass unresolved patch gates.")
    state_apply.add_argument("--out", default="", help="Output apply markdown report path.")
    state_apply.add_argument("--json-out", default="", help="Output apply JSON manifest path.")

    simulate = sub.add_parser("simulate-scene", help="Create a roleplay simulation workspace for a scene.")
    simulate.add_argument("project", help="Work project directory.")
    simulate.add_argument("--scene", default="scenes/scene_0001.yaml")
    simulate.add_argument("--context", default="", help="Existing context packet path.")
    simulate.add_argument("--query", default="", help="Extra retrieval query when context needs rebuilding.")
    simulate.add_argument("--rebuild-context", action="store_true")
    simulate.add_argument("--out", default="", help="Output simulation path.")
    simulate.add_argument("--agent", "--agent-tasks", dest="agent_tasks", action="store_true", help="Generate platform-agent executable task directives instead of empty placeholders.")

    branch = sub.add_parser("branch-simulate", help="Create scored multi-branch plot candidates for a scene.")
    branch.add_argument("project", help="Work project directory.")
    branch.add_argument("--scene", default="scenes/scene_0001.yaml")
    branch.add_argument("--context", default="", help="Existing context packet path.")
    branch.add_argument("--query", default="", help="Extra retrieval query when context needs rebuilding.")
    branch.add_argument("--rebuild-context", action="store_true")
    branch.add_argument("--branch-count", type=int, default=4, help="Number of branches to create, between 2 and 5.")
    branch.add_argument("--out", default="", help="Output markdown path.")
    branch.add_argument("--json-out", default="", help="Output JSON manifest path.")
    branch.add_argument("--selection-out", default="", help="Output human selection record path.")
    branch.add_argument("--agent", "--agent-tasks", dest="agent_tasks", action="store_true", help="Write a platform-agent task sidecar for reviewing branch decisions.")

    compose = sub.add_parser("compose-scene", help="Create a scene composition packet from context, characters, and branch artifacts.")
    compose.add_argument("project", help="Work project directory.")
    compose.add_argument("--scene", default="scenes/scene_0001.yaml")
    compose.add_argument("--context", default="", help="Existing context packet path.")
    compose.add_argument("--query", default="", help="Extra retrieval query when context needs rebuilding.")
    compose.add_argument("--rebuild-context", action="store_true")
    compose.add_argument("--branch-manifest", default="", help="Existing branch manifest path. Defaults to branches/{scene_id}/branch_manifest.json.")
    compose.add_argument("--branch-selection", default="", help="Existing branch selection path. Defaults to branches/{scene_id}/branch_selection.md.")
    compose.add_argument("--out", default="", help="Output composition markdown path.")
    compose.add_argument("--json-out", default="", help="Output composition JSON path.")
    compose.add_argument("--agent-tasks", action="store_true", help="Write a platform-agent task sidecar without polluting composition artifacts.")
    compose.add_argument("--allow-recommended-branch", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass branch-selection gates.")
    compose.add_argument("--allow-missing-branch", action="store_true", help="Maintainer/debug only; formal Skill hosts must not bypass branch-simulation gates.")

    orchestration = sub.add_parser("orchestration-plan", help="Create an agent workflow platform blueprint.")
    orchestration.add_argument("project", help="Work project directory.")
    orchestration.add_argument(
        "--platforms",
        default="",
        help="Comma-separated platform keys. Defaults to langgraph,dify,llamaindex-workflows,crewai,microsoft-agent-framework.",
    )
    orchestration.add_argument("--out", default="", help="Output markdown path.")
    orchestration.add_argument("--json-out", default="", help="Output JSON path.")

    chapter = sub.add_parser("chapter-workspace", help="Assemble a chapter-level workspace from scene artifacts.")
    chapter.add_argument("project", help="Work project directory.")
    chapter.add_argument("--chapter-id", default="chapter_0001")
    chapter.add_argument("--scenes", default="", help="Comma-separated scene yaml paths. Defaults to chapter scenes.")
    chapter.add_argument("--build-missing", action="store_true", help="Create missing scene draft workspaces.")
    chapter.add_argument("--review-drafts", action="store_true", help="Run review on available scene drafts.")
    chapter.add_argument("--agent-review", action="store_true", help="Write platform-agent review tasks and require completed platform review JSON for ready scenes.")
    chapter.add_argument("--out", default="", help="Output chapter markdown path.")
    chapter.add_argument("--json-out", default="", help="Output chapter JSON path.")

    for command, help_text in (
        ("word-budget", "Build a long-form word budget and platform-agent expansion task."),
        ("longform-budget", "Alias for word-budget."),
    ):
        word_budget = sub.add_parser(command, help=help_text)
        word_budget.add_argument("project", help="Work project directory.")
        word_budget.add_argument("--target-words", type=int, default=0, help="Target total Chinese-content character count, including Han characters and Chinese punctuation. Defaults to project.yaml target_length.")
        word_budget.add_argument("--volumes", type=int, default=0, help="Volume count. Defaults to project.yaml volumes or an inferred value.")
        word_budget.add_argument("--genre", default="", help="Genre preset, such as general, mystery, speculative, urban, or literary.")
        word_budget.add_argument("--time-span", default="", help="Story time-span note for platform-agent planning.")
        word_budget.add_argument("--outline", default="", help="Existing outline path. Defaults to plot/outline.md.")
        word_budget.add_argument("--out", default="", help="Output markdown path. Defaults to plot/word_budget/word_budget.md.")
        word_budget.add_argument("--json-out", default="", help="Output JSON path. Defaults to plot/word_budget/word_budget.json.")
        word_budget.add_argument("--agent-tasks-out", default="", help="Output agent task sidecar. Defaults to plot/word_budget/word_budget.agent_tasks.md.")

    obligation = sub.add_parser("chapter-obligation", help="Create a chapter obligation and reader-experience platform-agent task.")
    obligation.add_argument("project", help="Work project directory.")
    obligation.add_argument("--chapter-id", default="", help="Chapter id. Defaults to the first scene chapter or chapter_0001.")
    obligation.add_argument("--out", default="", help="Output markdown path. Defaults to plot/chapter_obligations/{chapter_id}.md.")
    obligation.add_argument("--json-out", default="", help="Output JSON path. Defaults to plot/chapter_obligations/{chapter_id}.json.")
    obligation.add_argument("--agent-tasks-out", default="", help="Output agent task sidecar. Defaults to plot/chapter_obligations/{chapter_id}.agent_tasks.md.")

    materialize_longform = sub.add_parser(
        "materialize-longform-plan",
        help="Materialize reviewed longform candidates into formal outline and scene contracts.",
    )
    materialize_longform.add_argument("project", help="Work project directory.")

    handoff = sub.add_parser("scene-handoff", help="Materialize a promoted scene continuity handoff for the next formal scene.")
    handoff.add_argument("project", help="Work project directory.")
    handoff.add_argument("--scene", default="scenes/scene_0001.yaml", help="Promoted scene whose post-scene handoff is recorded.")

    architecture = sub.add_parser("prepare-story-architecture", help="Prepare the formal story-architecture candidate task.")
    architecture.add_argument("project", help="Work project directory.")
    architecture_review = sub.add_parser("prepare-story-architecture-review", help="Prepare an independent review task for the current story architecture candidate.")
    architecture_review.add_argument("project", help="Work project directory.")
    architecture_status = sub.add_parser("story-architecture-status", help="Validate story architecture candidate and independent review.")
    architecture_status.add_argument("project", help="Work project directory.")

    ledger_prepare = sub.add_parser("prepare-continuity-ledger", help="Prepare reader-question and promise/payoff delta task for a promoted scene.")
    ledger_prepare.add_argument("project", help="Work project directory.")
    ledger_prepare.add_argument("--scene", default="scenes/scene_0001.yaml")
    ledger_review = sub.add_parser("prepare-continuity-ledger-review", help="Prepare independent continuity-ledger review task.")
    ledger_review.add_argument("project", help="Work project directory.")
    ledger_review.add_argument("--scene", default="scenes/scene_0001.yaml")
    ledger_apply = sub.add_parser("apply-continuity-ledger", help="Apply reviewed continuity ledger delta into formal ledgers.")
    ledger_apply.add_argument("project", help="Work project directory.")
    ledger_apply.add_argument("--scene", default="scenes/scene_0001.yaml")

    longform = sub.add_parser("longform-audit", help="Audit long-form continuity, readiness, and graph structure.")
    longform.add_argument("project", help="Work project directory.")
    longform.add_argument("--target-length", type=int, default=100000)
    longform.add_argument("--out", default="", help="Output audit markdown path.")
    longform.add_argument("--json-out", default="", help="Output audit JSON path.")
    longform.add_argument("--graph-out", default="", help="Output lightweight graph JSON path.")

    export = sub.add_parser("export-package", help="Export a chapter as Markdown and optional DOCX artifacts.")
    export.add_argument("project", help="Work project directory.")
    export.add_argument("--chapter-id", default="chapter_0001")
    export.add_argument("--include-blocked", action="store_true", help="Maintainer/debug only; formal Skill hosts must not export non-ready scenes.")
    export.add_argument("--rebuild-chapter", action="store_true", help="Rebuild chapter workspace before export.")
    export.add_argument("--out-dir", default="", help="Output directory. Defaults to exports/{chapter_id}.")
    export.add_argument("--formats", default="md", help="Comma-separated output formats: md,docx. Defaults to md.")

    export_docx = sub.add_parser("export-docx", help="Export a Markdown/text artifact to an editable DOCX file.")
    export_docx.add_argument("source", help="Source Markdown or text file.")
    export_docx.add_argument("--out", default="", help="Output DOCX path. Defaults to source path with .docx suffix.")
    export_docx.add_argument("--title", default="", help="Document title override.")
    export_docx.add_argument("--kind", default="novel", choices=sorted(DOCX_KINDS), help="Document style preset.")
    export_docx.add_argument("--no-overwrite", action="store_true", help="Fail if the output DOCX already exists.")

    publish = sub.add_parser("publish-chapter", help="Publish a reviewed and approved chapter release.")
    publish.add_argument("project", help="Work project directory.")
    publish.add_argument("--chapter-id", default="chapter_0001")
    publish.add_argument("--release-id", default="", help="Release id. Defaults to a UTC timestamp.")
    publish.add_argument("--approval-run-id", default="", help="Require a matching approve record for this workflow run id.")
    publish.add_argument("--allow-unapproved", action="store_true", help="Maintainer/debug only; formal Skill hosts must not publish without approval.")
    publish.add_argument("--rebuild-chapter", action="store_true", help="Rebuild chapter workspace and reviews before publishing.")
    publish.add_argument("--rebuild-export", action="store_true", help="Rebuild export package before publishing.")
    publish.add_argument("--out-dir", default="", help="Output release directory. Defaults to releases/{chapter_id}/{release_id}.")
    publish.add_argument("--overwrite", action="store_true", help="Allow replacing an existing release directory.")
    publish.add_argument("--export-formats", default="md", help="Comma-separated export formats for release: md,docx.")

    workflow = sub.add_parser("run-workflow", help="Run a file-backed agent workflow and write state/log artifacts.")
    workflow.add_argument("project", help="Work project directory.")
    workflow.add_argument("--mode", default="full-cycle", choices=sorted(WORKFLOW_MODES))
    workflow.add_argument("--scene", default="scenes/scene_0001.yaml")
    workflow.add_argument("--chapter-id", default="chapter_0001")
    workflow.add_argument("--target-length", type=int, default=100000)
    workflow.add_argument("--include-blocked", action="store_true", help="Maintainer/debug only; formal Skill hosts must not export non-ready scenes.")
    workflow.add_argument("--overwrite-draft", action="store_true", help="Regenerate draft workspace even when one exists.")
    workflow.add_argument("--generate-candidate", action="store_true", help="Generate a scene candidate after scene composition.")
    workflow.add_argument("--promote-candidate", action="store_true", help="Promote the generated or latest candidate only after the formal candidate review gate passes.")
    workflow.add_argument("--agent-review", action="store_true", help="Run schema-gated agent scene/canon review nodes.")
    workflow.add_argument("--agent-tasks", action="store_true", help="Generate platform-agent task sidecars for creative workflow artifacts.")
    workflow.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal workflow writes platform-agent tasks.")
    workflow.add_argument("--run-id", default="", help="Use a stable workflow run id instead of an auto-generated one.")
    workflow.add_argument("--resume-run-id", default="", help="Create a new linked run that resumes/retries from a previous run id.")
    workflow.add_argument("--overwrite-run", action="store_true", help="Allow replacing an existing run directory with the same run id.")
    workflow.add_argument("--out-dir", default="", help="Workflow run directory. Defaults to workflow/runs/{run_id}.")

    approval = sub.add_parser("approval-summary", help="Summarize workflow approval records and follow-up tasks.")
    approval.add_argument("project", help="Work project directory.")
    approval.add_argument("--run-id", default="", help="Filter summary to one workflow run id.")
    approval.add_argument("--out", default="", help="Output markdown path. Defaults to workflow/approvals/approval_summary.md.")

    langgraph = sub.add_parser("run-langgraph", help="Run the literary workflow through a LangGraph StateGraph.")
    langgraph.add_argument("project", help="Work project directory.")
    langgraph.add_argument("--scene", default="scenes/scene_0001.yaml")
    langgraph.add_argument("--chapter-id", default="chapter_0001")
    langgraph.add_argument("--target-length", type=int, default=100000)
    langgraph.add_argument("--include-blocked", action="store_true", help="Maintainer/debug only; formal Skill hosts must not export non-ready scenes.")
    langgraph.add_argument("--overwrite-draft", action="store_true", help="Regenerate draft workspace even when one exists.")
    langgraph.add_argument("--generate-candidate", action="store_true", help="Generate a scene candidate after scene composition.")
    langgraph.add_argument("--promote-candidate", action="store_true", help="Promote the generated or latest candidate only after the formal candidate review gate passes.")
    langgraph.add_argument("--agent-review", action="store_true", help="Run schema-gated agent scene/canon review nodes.")
    langgraph.add_argument("--provider", default="platform-agent", help="Legacy compatibility only; formal workflow writes platform-agent tasks.")
    langgraph.add_argument("--thread-id", default="", help="External orchestration thread id for LangGraph config.")

    serve = sub.add_parser("serve-api", help="Start a FastAPI backend for Dify and workflow clients.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument(
        "--allowed-root",
        action="append",
        default=[],
        help="Allowed project root or parent directory. Can be passed more than once.",
    )
    serve.add_argument(
        "--api-token",
        default="",
        help="Require this API token for workflow endpoints. If omitted, LEW_API_TOKEN is used when set.",
    )

    dify = sub.add_parser("dify-dsl", help="Generate a Dify Workflow DSL starter for the workbench API.")
    dify.add_argument("--out", default=str(DEFAULT_DIFY_DSL_PATH), help="Output YAML path.")
    dify.add_argument("--app-name", default="文学工程审稿台", help="Dify app name.")
    dify.add_argument("--api-base", default="http://127.0.0.1:8765", help="Workbench API base URL.")
    dify.add_argument("--dsl-version", default="0.6.0", help="Dify DSL version to declare. Defaults to 0.6.0.")
    dify.add_argument("--default-mode", default="full-cycle", choices=sorted(WORKFLOW_MODES))
    dify.add_argument("--default-scene", default="scenes/scene_0001.yaml")
    dify.add_argument("--default-chapter-id", default="chapter_0001")

    config_show = sub.add_parser("config-show", help="Show the global workbench configuration with secrets redacted.")
    config_show.add_argument("--raw", action="store_true", help="Show the normalized raw config instead of the effective view.")

    config_init = sub.add_parser("config-init", help="Create or reset the global workbench configuration.")
    config_init.add_argument("--overwrite", action="store_true", help="Overwrite an existing config with defaults.")

    config_set = sub.add_parser("config-set-profile", help="Create or update one global model provider profile.")
    config_set.add_argument("--name", default="deepseek", help="Profile name.")
    config_set.add_argument("--api-base", default="", help="HTTP chat API base URL.")
    config_set.add_argument("--model", default="", help="Model name.")
    config_set.add_argument("--api-key-env", default="", help="Environment variable that contains the API key.")
    config_set.add_argument("--temperature", type=float, default=None)
    config_set.add_argument("--max-tokens", type=int, default=None)
    config_set.add_argument("--timeout", type=float, default=None)
    config_set.add_argument("--project-root", default="", help="Default work project root for API/front-end workflows.")
    config_set.add_argument("--activate", action="store_true", help="Make this profile active.")

    if not full_help:
        _harden_top_level_help(parser)
    return parser


def _harden_top_level_help(parser: argparse.ArgumentParser) -> None:
    """Keep bare `lew --help` focused on the formal operating loop."""

    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            action._choices_actions = [
                choice for choice in action._choices_actions if getattr(choice, "dest", "") in FORMAL_HELP_COMMANDS
            ]
