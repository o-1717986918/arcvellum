"""Route runbooks for platform-agent and CLI workflow discipline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True)
class ProtocolRoute:
    key: str
    title: str
    purpose: str
    read: tuple[str, ...]
    preflight: tuple[str, ...]
    cli_chain: tuple[str, ...]
    platform_agent_handoffs: tuple[str, ...]
    completion_gates: tuple[str, ...]
    forbidden_shortcuts: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


COMMON_PREFLIGHT = (
    "Classify workspace type: skill root, work project, or style library.",
    "Select this route in agentread.yaml and avoid starting from an arbitrary command.",
    "Read references/agent-run-protocol.md before changing project artifacts.",
    "Inspect project.yaml plus relevant canon, characters, plot, style, drafts, reviews, workflow, and approvals.",
    "Probe documented commands before declaring them unavailable: run --help, protocol <route>, or the smallest safe command attempt; record exact errors before choosing an emulation path.",
    "Run agent-task-status or route-audit when sidecar or route completion state is unclear.",
    "State intended artifacts, review gates, and approval boundary before generation or promotion.",
)

COMMON_FORBIDDEN = (
    "Do not accept CLI output as canon or final creative judgment.",
    "Do not accept generated JSON merely because it parses.",
    "Do not skip .agent_tasks.md handling when a command writes sidecars; the current platform agent must read the task and fill expected artifacts.",
    "Do not declare a documented CLI/tool step impossible without probing it or recording a real command failure.",
    "Do not promote candidates without clean review and approval.",
    "Do not use debug/bypass flags such as --allow-unreviewed, --allow-review-notes, --include-blocked, --allow-unapproved, --allow-unresolved, --allow-missing-composition, --allow-unselected-composition, --allow-recommended-branch, or --allow-missing-branch during formal Skill-host work.",
    "Do not delegate creative body-text drafting, rewriting, polishing, expansion, or finalization to subagents; the main platform agent must write正文.",
    "Do not bypass failed readiness/export gates with a custom script and present the result as final release output.",
    "Do not store API keys or provider secrets in work projects.",
)


PROTOCOL_ROUTES: dict[str, ProtocolRoute] = {
    "project-director": ProtocolRoute(
        key="project-director",
        title="Project Director",
        purpose="Handle broad user direction, project management, next-step selection, and creative decision routing.",
        read=(
            "references/agent-run-protocol.md",
            "references/project-director-playbook.md",
            "references/artifact-contracts.md",
            "project.yaml",
        ),
        preflight=COMMON_PREFLIGHT
        + (
            "Inspect latest reviews, workflow runs, approval records, and director notes if present.",
            "Decide whether to plan, create candidate assets, revise drafts, audit, learn style, or ask one high-level question.",
        ),
        cli_chain=(
            "python -m literary_engineering_studio_engine protocol project-director",
            "python -m literary_engineering_studio_engine director-status <project>",
        ),
        platform_agent_handoffs=(
            "All free-form project direction and second-level decisions.",
            "Any decision to create, revise, promote, export, or ask the user.",
        ),
        completion_gates=(
            "Project status inspected.",
            "Route decision or candidate plan recorded.",
            "User-facing answer hides raw schemas and command chatter unless requested.",
        ),
        forbidden_shortcuts=COMMON_FORBIDDEN
        + (
            "Do not treat local director-chat output as the primary project director.",
        ),
    ),
    "work-project-initialization": ProtocolRoute(
        key="work-project-initialization",
        title="Work Project Initialization",
        purpose="Create a new novel, screenplay, pseudo-record, short-drama, or long-video prompt project.",
        read=(
            "references/agent-run-protocol.md",
            "references/project-director-playbook.md",
            "references/artifact-contracts.md",
            "templates/work-project/project.yaml",
            "docs/architecture/data-model.md",
            "docs/implementation/phase1-initializer.md",
        ),
        preflight=COMMON_PREFLIGHT
        + (
            "Confirm target path and high-level creative premise.",
            "Record which early facts are confirmed versus candidate.",
        ),
        cli_chain=(
            "python -m literary_engineering_studio_engine protocol work-project-initialization",
            "python -m literary_engineering_studio_engine init <project> --title <title> --type novel",
        ),
        platform_agent_handoffs=(
            "Initial premise, project brief, canon candidates, and approval boundaries.",
            "Any user-facing creative framing beyond deterministic skeleton creation.",
        ),
        completion_gates=(
            "Project skeleton exists or target path is explicit.",
            "Initial creative brief remains candidate until reviewed.",
            "Approval boundaries recorded.",
        ),
        forbidden_shortcuts=COMMON_FORBIDDEN,
    ),
    "style-engineering": ProtocolRoute(
        key="style-engineering",
        title="Style Engineering",
        purpose="Learn an author/work style project, compile a style profile, produce an LLM-facing style prompt, and mount a Style Skill.",
        read=(
            "references/agent-run-protocol.md",
            "references/cli-run-protocol.md",
            "references/project-director-playbook.md",
            "references/artifact-contracts.md",
            "references/workflows.md",
            "docs/modules/style-compiler.md",
            "docs/implementation/phase58-author-style-projects.md",
            "docs/implementation/phase59-style-skill-package.md",
            "docs/implementation/phase60-style-skill-mount.md",
            "docs/implementation/phase61-style-priority-enforcement.md",
        ),
        preflight=COMMON_PREFLIGHT
        + (
            "Record corpus authorization or public-domain assumption.",
            "Identify whether the target is style analysis, prompt generation, effectiveness review, or mounting.",
        ),
        cli_chain=(
            "python -m literary_engineering_studio_engine protocol style-engineering",
            "python -m literary_engineering_studio_engine style-lab-author <style-library> <author-id>",
            "python -m literary_engineering_studio_engine style-lab-work <style-library> <author-id> <work-id>",
            "python -m literary_engineering_studio_engine style-lab-import <style-library> <author-id> <work-id> <source-text>",
            "python -m literary_engineering_studio_engine style-lab-compile <style-library> <author-id>",
            "python -m literary_engineering_studio_engine style-lab-build-skill <style-library> <author-id>",
            "python -m literary_engineering_studio_engine style-lab-mount <project> <style-skill>",
        ),
        platform_agent_handoffs=(
            "LLM-facing style prompt writing.",
            "Back-translation or expansion effectiveness judgments.",
            "Style risk, originality risk, and mount priority decisions.",
        ),
        completion_gates=(
            "Corpus authorization or public-domain assumption recorded.",
            "Style prompt created or sidecar handled, with 500-2500 Chinese-content characters, counting Han characters and Chinese punctuation, and all required high-quality prompt blocks for reliable mounting.",
            "Effectiveness/risk review completed before mounting.",
        ),
        forbidden_shortcuts=COMMON_FORBIDDEN
        + (
            "Do not treat style similarity as originality safety.",
            "Do not let style override canon, character facts, plot causality, or explicit user constraints.",
        ),
    ),
    "character-and-world-assets": ProtocolRoute(
        key="character-and-world-assets",
        title="Character And World Assets",
        purpose="Create or modify characters, hidden background stories, relationships, world rules, locations, organizations, and outlines.",
        read=(
            "references/agent-run-protocol.md",
            "references/project-director-playbook.md",
            "references/artifact-contracts.md",
            "docs/implementation/phase37-asset-candidate-schemas.md",
            "docs/implementation/phase38-agent-character-creation.md",
            "docs/implementation/phase39-agent-worldbuilding.md",
            "docs/implementation/phase40-agent-outline-creation.md",
            "docs/implementation/phase41-candidate-review-promotion.md",
        ),
        preflight=COMMON_PREFLIGHT
        + (
            "Identify asset type and target canonical file before writing.",
            "Check related canon, relationships, and existing candidate assets.",
        ),
        cli_chain=(
            "python -m literary_engineering_studio_engine protocol character-and-world-assets",
            "python -m literary_engineering_studio_engine agent-create-character <project> --brief <brief>",
            "python -m literary_engineering_studio_engine review-candidate-asset <project> <candidate>",
            "python -m literary_engineering_studio_engine promote-candidate-asset <project> <candidate> --approval-run-id <id>",
        ),
        platform_agent_handoffs=(
            "Candidate character/world/relationship/outline writing.",
            "Review of motive logic, canon fit, OOC risk, loopholes, and promotion recommendation.",
        ),
        completion_gates=(
            "Asset written as candidate first.",
            "Schema and canon risks reviewed.",
            "Explicit approval required before promotion.",
        ),
        forbidden_shortcuts=COMMON_FORBIDDEN
        + (
            "Do not expose hidden background_story as direct scene exposition by default.",
        ),
    ),
    "source-ingest": ProtocolRoute(
        key="source-ingest",
        title="Source Ingest",
        purpose="Import an existing text or complete work, then let the platform agent reverse-extract candidate project files for continuation, rewrite, adaptation, or analysis.",
        read=(
            "references/agent-run-protocol.md",
            "references/cli-run-protocol.md",
            "references/artifact-contracts.md",
            "references/workflows.md",
            "docs/modules/source-ingest-engine.md",
            "docs/implementation/phase64-existing-work-ingest.md",
        ),
        preflight=COMMON_PREFLIGHT
        + (
            "Confirm source authorization, user-provided material boundary, or public-domain status before exact continuation or style-sensitive reuse.",
            "Identify whether the target is continuation, rewrite, adaptation, or analysis.",
            "Inspect existing canon, characters, plot, and style files so extracted items do not overwrite confirmed project state.",
        ),
        cli_chain=(
            "python -m literary_engineering_studio_engine protocol source-ingest",
            "python -m literary_engineering_studio_engine source-ingest <project> --source <source-file-or-dir> --title <title> --mode continuation",
            "Read sources/imports/<work-id>/extract_project_files.agent_tasks.md and write the expected candidate artifacts.",
            "Review reviews/source_ingest/<work-id>_extraction_review.md before promoting any extracted candidate.",
        ),
        platform_agent_handoffs=(
            "All extraction of characters, hidden background stories, world rules, outline, timeline, foreshadowing, and style notes.",
            "Evidence/confidence judgment, contradiction handling, and promotion recommendation.",
        ),
        completion_gates=(
            "Source manifest, chunk files, and extraction task sidecar exist.",
            "Platform agent has written candidate outputs or they are explicitly listed as pending.",
            "Each extracted claim carries evidence references, confidence, and unknowns.",
            "No extracted item is promoted to canon/characters/plot/style without review and approval.",
        ),
        forbidden_shortcuts=COMMON_FORBIDDEN
        + (
            "Do not copy long passages into evidence notes; use concise references.",
            "Do not treat source-derived style notes as a mountable Style Skill until they become a reviewed 500-2500 Chinese-content-character prompt.",
        ),
    ),
    "longform-planning": ProtocolRoute(
        key="longform-planning",
        title="Longform Planning",
        purpose="Plan target length, volumes, chapters, scenes, narrative inventory, and budgeted outline expansion before long-form generation.",
        read=(
            "references/agent-run-protocol.md",
            "references/cli-run-protocol.md",
            "references/project-director-playbook.md",
            "references/artifact-contracts.md",
            "references/workflows.md",
            "docs/modules/longform-word-budget.md",
            "docs/modules/reader-experience-contract.md",
            "docs/implementation/phase65-longform-word-budget.md",
            "docs/implementation/phase88-reader-experience-contract.md",
        ),
        preflight=COMMON_PREFLIGHT
        + (
            "Confirm target length, volume count, genre, time span, and whether the current outline is accepted or only a seed.",
            "Inspect plot/outline.md, plot/word_budget/, scenes/, chapters, and latest longform reviews.",
            "Identify whether the task needs a new budget, a budget revision, or a platform-agent budgeted outline expansion.",
        ),
        cli_chain=(
            "python -m literary_engineering_studio_engine protocol longform-planning",
            "python -m literary_engineering_studio_engine word-budget <project> --target-words 500000 --volumes 5 --genre mystery",
            "Read plot/word_budget/word_budget.agent_tasks.md and write plot/candidates/outlines/word_budget_expansion.md plus reviews/word_budget/word_budget_review.md.",
            "Read plot/word_budget/scene_inventory_expansion.agent_tasks.md and write plot/candidates/scenes/word_budget_scene_inventory.md plus reviews/word_budget/scene_inventory_review.md.",
            "Read plot/chapter_obligations/chapter_obligations.agent_tasks.md and write reviews/word_budget/chapter_obligation_review.md plus the completion marker.",
            "For each chapter entering prose, run python -m literary_engineering_studio_engine chapter-obligation <project> --chapter-id <chapter_id>, then fill the per-chapter reader contract and completion marker.",
            "python -m literary_engineering_studio_engine route-audit <project> --route longform-planning",
            "python -m literary_engineering_studio_engine longform-audit <project> --target-length 500000",
        ),
        platform_agent_handoffs=(
            "Genre-to-length judgment, time-span/detail calibration, and narrative-load tradeoffs.",
            "Budgeted outline expansion, scene inventory design, chapter obligation design, subplot density, and pacing decisions.",
            "Review of whether the generated outline truly supports the target length without filler or compression.",
            "Reader question, promised reward, withheld information, payoff/delay, and anti-summary planning for each chapter/scene.",
        ),
        completion_gates=(
            "word_budget.md/json and word_budget.agent_tasks.md exist or the reason for skipping is recorded.",
            "Platform agent has written or explicitly deferred the budgeted outline candidate and word-budget review.",
            "Platform agent has handled scene inventory and chapter obligation sidecars with completion markers.",
            "Chapter-level and scene-level word targets, actual cleaned body counts, machine-count mappings, missing scenes, expansion tasks, and reader-experience obligations are reviewed.",
            "Scene/chapter inventory is sufficient for the target length before batch scene generation or the shortfall is listed as pending.",
            "Prompt manifest and generation flow will load the word-budget standard and reader-experience contract.",
        ),
        forbidden_shortcuts=COMMON_FORBIDDEN
        + (
            "Do not treat a target Chinese-content character count as satisfied by asking scenes to be longer without increasing narrative events.",
            "Do not overwrite plot/outline.md with a budgeted expansion until review and user approval.",
            "Do not start bulk prose generation when word_budget status is needs_expansion or chapter/reader contracts are incomplete.",
        ),
    ),
    "scene-development": ProtocolRoute(
        key="scene-development",
        title="Scene Development",
        purpose="Develop scene context, roleplay, branches, composition, prose candidate, review, and character state patch.",
        read=(
            "references/agent-run-protocol.md",
            "references/cli-run-protocol.md",
            "references/artifact-contracts.md",
            "references/punctuation-standard.md",
            "docs/modules/plot-scene-engine.md",
            "docs/modules/character-engine.md",
            "docs/implementation/phase20-branch-simulation.md",
            "docs/implementation/phase22-scene-composer.md",
            "docs/implementation/phase23-model-provider-prompt-pack.md",
            "docs/implementation/phase24-character-state-evolution.md",
            "docs/implementation/phase25-candidate-promotion-state-apply.md",
            "docs/modules/cli-mediated-agent-workflow.md",
        ),
        preflight=COMMON_PREFLIGHT
        + (
            "Inspect the scene file, participants, previous scene state, and mounted style.",
            "Identify whether this turn needs context, simulation, branch, composition, prose, review, or state patch.",
            "For a chapter or volume batch, list every scene first; this runbook must be repeated per scene, not sampled.",
            "For formal scene-development, prefer task-next/task-open/task-submit/task-complete as the controlling loop; the older route commands are executed when the task package instructs them.",
        ),
        cli_chain=(
            "python -m literary_engineering_studio_engine protocol scene-development",
            "python -m literary_engineering_studio_engine task-next <project> --route scene-development --scene scenes/scene_0001.yaml",
            "python -m literary_engineering_studio_engine task-open <project> --task-id <task-id>",
            "Run the command named in workflow/tasks/<task-id>.agent_tasks.md, or perform the platform-agent judgment/body-writing task it specifies.",
            "python -m literary_engineering_studio_engine task-submit <project> --task-id <task-id> --from <artifact>",
            "python -m literary_engineering_studio_engine task-complete <project> --task-id <task-id>",
            "python -m literary_engineering_studio_engine workflow-advance <project> --route scene-development",
            "Repeat task-next/open/submit/complete until the scene reaches ready, then run route-audit.",
            "Legacy underlying commands used by task packages include:",
            "python -m literary_engineering_studio_engine context <project> --scene scenes/scene_0001.yaml",
            "python -m literary_engineering_studio_engine simulate-scene <project> --scene scenes/scene_0001.yaml --agent",
            "python -m literary_engineering_studio_engine branch-simulate <project> --scene scenes/scene_0001.yaml --agent",
            "Fill branches/scene_0001/branch_selection.md with decision: selected and selected_branch.",
            "python -m literary_engineering_studio_engine compose-scene <project> --scene scenes/scene_0001.yaml --agent-tasks",
            "python -m literary_engineering_studio_engine generate-scene <project> --scene scenes/scene_0001.yaml",
            "Read drafts/candidates/scene_0001-platform-agent.agent_tasks.md and prompt manifest, then write the expected candidate Markdown/JSON as the main platform agent.",
            "python -m literary_engineering_studio_engine agent-review-scene <project> --scene scenes/scene_0001.yaml --draft drafts/candidates/scene_0001-platform-agent.md",
            "Read reviews/agent/scene_0001_scene_review.agent_tasks.md and write the expected scene_review.v1 JSON/Markdown as platform agent.",
            "python -m literary_engineering_studio_engine promote-candidate <project> --scene scenes/scene_0001.yaml",
            "python -m literary_engineering_studio_engine review-scene <project> --scene scenes/scene_0001.yaml",
            "python -m literary_engineering_studio_engine revise-scene <project> --scene scenes/scene_0001.yaml",
            "python -m literary_engineering_studio_engine state-evolve <project> --scene scenes/scene_0001.yaml --agent-tasks",
            "python -m literary_engineering_studio_engine route-audit <project> --route scene-development",
        ),
        platform_agent_handoffs=(
            "Roleplay answers, branch selection, consequence reasoning, and scene composition judgment.",
            "Main-agent prose drafting from generate-scene sidecar, AgentReview notes resolution, anti-evasion revision burden of proof, formal revision candidate generation, and scene review. agent-review-scene is a sidecar generator; the platform agent performs the review.",
            "Subagents may provide retrieval summaries, issue lists, schema checks, continuity tables, and word-count inventories only; they must not draft or revise body text.",
            "Character state patch interpretation and promotion recommendation.",
        ),
        completion_gates=(
            "When task-next issues a workflow/tasks/ package for formal scene-development, that package must be task-submitted and task-completed before the next formal state.",
            "task-submit records every platform-agent output used to satisfy the current task.",
            "task-complete succeeds before the platform agent moves to the next formal state.",
            "CLI-generated context packet plus valid context trace, or a recorded CLI-equivalent workaround for both artifacts, exists.",
            "simulate-scene --agent roleplay simulation exists, includes CLI provenance, includes a platform-agent reading receipt, and has no unresolved AGENT_TASK directives.",
            "branch-simulate --agent branch manifest exists with CLI provenance, and branch_selection.md records decision: selected plus selected_branch before composition or generation.",
            "compose-scene --agent-tasks composition exists with selection_source=selection, ready_for_generation=true, and formal_cli_provenance.created_by=compose-scene before generate-scene or state writeback.",
            "Prose candidate exists for each target scene, has generate-scene prompt/task/manifest provenance, and was written by the main platform agent, not a subagent.",
            "Prose candidate reviewed for canon, character, style, and punctuation.",
            "Any new character introduced by the scene is classified in new_character_register; persistent new characters have candidate asset review and approval/promotion before clean pass.",
            "agent-review-scene was run or an equivalent exact-candidate platform review was written with a concrete reason for any CLI skip.",
            "Exact candidate path is cited in a passing scene_review.v1 JSON before promote-candidate.",
            "promote-candidate wrote the promotion manifest and promoted draft for each formal scene.",
            "Static review-scene clean pass exists after promotion and before chapter/export readiness.",
            "Any pass_with_notes, warning, Style Lint, anti-evasion, or revise_required finding is resolved through revise-scene and re-review.",
            "state-evolve wrote a state patch for each formal scene; state-apply remains approval-gated.",
            "route-audit --route scene-development passes or lists every missing per-scene gate before chapter/export readiness.",
        ),
        forbidden_shortcuts=COMMON_FORBIDDEN
        + (
            "Do not let branch scores become final plot decisions without platform-agent review.",
            "Do not process one representative scene and bulk-write the rest without their own RP/branch/composition/generation/review/promotion/state gates.",
            "Do not hand-write same-named formal files to satisfy route gates unless a documented CLI failure and CLI-equivalent workaround are recorded.",
            "Do not skip Chinese punctuation review for Chinese prose.",
        ),
    ),
    "review-and-audit": ProtocolRoute(
        key="review-and-audit",
        title="Review And Audit",
        purpose="Review scene, canon, continuity, longform readiness, and release blockers.",
        read=(
            "references/agent-run-protocol.md",
            "references/artifact-contracts.md",
            "references/punctuation-standard.md",
            "docs/modules/review-ci.md",
            "docs/implementation/phase4-scene-review-loop.md",
            "docs/implementation/phase19-canon-lint.md",
            "docs/implementation/phase7-chapter-pipeline.md",
            "docs/implementation/phase8-longform-audit.md",
        ),
        preflight=COMMON_PREFLIGHT
        + (
            "Identify audit scope: scene, canon, character, style, chapter, longform, or release readiness.",
            "Collect source paths and previous findings before issuing new findings.",
        ),
        cli_chain=(
            "python -m literary_engineering_studio_engine protocol review-and-audit",
            "python -m literary_engineering_studio_engine canon-lint <project>",
            "python -m literary_engineering_studio_engine agent-canon-review <project>",
            "python -m literary_engineering_studio_engine agent-committee <project>",
            "python -m literary_engineering_studio_engine longform-audit <project>",
            "python -m literary_engineering_studio_engine agent-task-status <project>",
            "python -m literary_engineering_studio_engine route-audit <project> --route review-and-audit",
        ),
        platform_agent_handoffs=(
            "Finding severity judgment, revision planning, committee synthesis, sidecar backlog triage, and acceptance of residual risk.",
        ),
        completion_gates=(
            "Blocking findings separated from warnings.",
            "Revision plan maps findings to artifacts.",
            "Pending sidecars, missing expected artifacts, and incomplete route gates are listed or resolved.",
            "Readiness and approval limits stated.",
        ),
        forbidden_shortcuts=COMMON_FORBIDDEN
        + (
            "Do not treat a clean deterministic report as a substitute for creative review when prose changed.",
        ),
    ),
    "export-and-release": ProtocolRoute(
        key="export-and-release",
        title="Export And Release",
        purpose="Export final work artifacts, produce DOCX/package outputs, publish chapters, and record rollback notes.",
        read=(
            "references/agent-run-protocol.md",
            "references/cli-run-protocol.md",
            "references/artifact-contracts.md",
            "references/file-format-export.md",
            "references/punctuation-standard.md",
            "docs/implementation/phase9-export-package.md",
            "docs/implementation/phase21-publish-chain.md",
            "docs/implementation/phase15-approval-loop.md",
        ),
        preflight=COMMON_PREFLIGHT
        + (
            "Confirm requested delivery format and chapter/work scope.",
            "Inspect readiness, latest audits, and approval records before export.",
        ),
        cli_chain=(
            "python -m literary_engineering_studio_engine protocol export-and-release",
            "python -m literary_engineering_studio_engine chapter-workspace <project> --chapter-id chapter_0001 --agent-review",
            "python -m literary_engineering_studio_engine export-package <project> --chapter-id chapter_0001 --docx",
            "python -m literary_engineering_studio_engine publish-chapter <project> --chapter-id chapter_0001 --approval-run-id <id>",
        ),
        platform_agent_handoffs=(
            "Release readiness judgment, unresolved-risk acceptance, and user-facing release summary.",
        ),
        completion_gates=(
            "Chapter/work readiness checked.",
            "Approval record verified or pending approval stated.",
            "Requested file formats generated and inspected; DOCX exports include layout and inspection companion files.",
            "Release notes and rollback notes prepared.",
            "If official export was blocked, do not use debug flags or custom scripts as a workaround; resolve missing gates first.",
        ),
        forbidden_shortcuts=COMMON_FORBIDDEN
        + (
            "Do not export as final when approval or blocking review is missing.",
        ),
    ),
    "optional-cli": ProtocolRoute(
        key="optional-cli",
        title="Formal Route CLI",
        purpose="Use deterministic helper commands, formal sidecar/provenance generators, local regression tests, Dify/LangGraph adapters, or frontend/API utilities.",
        read=(
            "references/agent-run-protocol.md",
            "references/cli-run-protocol.md",
            "references/workflows.md",
            "references/orchestration.md",
        ),
        preflight=COMMON_PREFLIGHT
        + (
            "Set PYTHONPATH for development src/ or installed scripts/ layout.",
            "Run --help for unfamiliar commands.",
        ),
        cli_chain=(
            "python -m literary_engineering_studio_engine protocol optional-cli",
            "python -m literary_engineering_studio_engine --help",
            "python -m literary_engineering_studio_engine agent-task-status <project>",
            "python -m literary_engineering_studio_engine route-audit <project> --route <route>",
        ),
        platform_agent_handoffs=(
            "Any interpretation, creative judgment, review, promotion, or release decision after deterministic CLI output.",
        ),
        completion_gates=(
            "CLI command selected from route needs, not convenience.",
            "stdout paths inspected.",
            "Generated sidecars handled or listed as pending.",
        ),
        forbidden_shortcuts=COMMON_FORBIDDEN,
    ),
}


ALIASES = {
    key.replace("-", "_"): key for key in PROTOCOL_ROUTES
}
ALIASES.update(
    {
        "project_director": "project-director",
        "work_project_initialization": "work-project-initialization",
        "style_engineering": "style-engineering",
        "source_ingest": "source-ingest",
        "longform_planning": "longform-planning",
        "character_and_world_assets": "character-and-world-assets",
        "scene_development": "scene-development",
        "review_and_audit": "review-and-audit",
        "export_and_release": "export-and-release",
        "optional_cli": "optional-cli",
    }
)


def list_protocol_routes() -> list[ProtocolRoute]:
    return [PROTOCOL_ROUTES[key] for key in sorted(PROTOCOL_ROUTES)]


def resolve_protocol_route(route: str) -> ProtocolRoute:
    normalized = route.strip().lower().replace("_", "-")
    key = normalized if normalized in PROTOCOL_ROUTES else ALIASES.get(route.strip().lower())
    if not key or key not in PROTOCOL_ROUTES:
        valid = ", ".join(sorted(PROTOCOL_ROUTES))
        raise KeyError(f"unknown protocol route: {route}. valid routes: {valid}")
    return PROTOCOL_ROUTES[key]


def render_protocol(route: ProtocolRoute) -> str:
    sections = [
        f"# {route.title} Protocol",
        "",
        f"route: `{route.key}`",
        "",
        route.purpose,
        "",
        _render_list("Read First", route.read),
        _render_list("Preflight", route.preflight),
        _render_list("Suggested CLI Chain", route.cli_chain),
        _render_list("Platform Agent Handoffs", route.platform_agent_handoffs),
        _render_list("Completion Gates", route.completion_gates),
        _render_list("Forbidden Shortcuts", route.forbidden_shortcuts),
    ]
    return "\n".join(sections).rstrip() + "\n"


def render_protocol_list() -> str:
    lines = ["# Available Protocol Routes", ""]
    for route in list_protocol_routes():
        lines.append(f"- `{route.key}`: {route.purpose}")
    return "\n".join(lines) + "\n"


def protocol_to_json(route: ProtocolRoute | None = None) -> str:
    payload: object
    if route is None:
        payload = [item.to_dict() for item in list_protocol_routes()]
    else:
        payload = route.to_dict()
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _render_list(title: str, items: tuple[str, ...]) -> str:
    lines = [f"## {title}", ""]
    lines.extend(f"- {item}" for item in items)
    lines.append("")
    return "\n".join(lines)
