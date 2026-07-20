# Agent Task Map

Use this map after reading `SKILL.md`, `AGENTS.md`, and `agentread.yaml`.

Supervision rule: any creative generation, LLM-authored JSON, schema repair, style prompt, simulation, review, branch choice, candidate promotion recommendation, release choice, or free-form project decision is led by the tool-layer agent that loaded this skill. Local CLI/API outputs are draft artifacts or evidence until the platform agent validates schema, checks canon/character/style constraints, and decides whether to revise, keep as candidate, ask the user, or promote after approval.

## Project Director

Read: `references/project-director-playbook.md`, `references/artifact-contracts.md`.

Use when the user gives broad direction, says continue, changes taste, asks what to do next, or wants Codex/Claude to manage the project.

Output: creative summary, candidate plan, changed files, review notes, and one high-level next choice.

## Work Project Initialization

Read: `templates/work-project/project.yaml`, `docs/architecture/data-model.md`, `docs/implementation/phase1-initializer.md`.

Output: work project skeleton, premise, project brief, first candidate pass, approval boundaries.

## Style Engineering

Read: `docs/modules/style-compiler.md`, `docs/implementation/phase58-author-style-projects.md`, `docs/implementation/phase59-style-skill-package.md`, `docs/implementation/phase60-style-skill-mount.md`, `docs/implementation/phase61-style-priority-enforcement.md`.

Output: author style project, work subproject, style profile, LLM-facing prompt, mountable Style Skill, style risk report.

## Source Ingest

Read: `docs/modules/source-ingest-engine.md`, `docs/implementation/phase64-existing-work-ingest.md`, `references/artifact-contracts.md`, `references/workflows.md`.

Use when the user provides an existing text, complete work, old draft, script, or pseudo-record material for continuation, rewrite, adaptation, or analysis.

Output: source manifest, chunks, extraction task sidecar, extracted project brief candidate, extracted character/world/outline/timeline/foreshadowing/style candidates, and source-ingest review report.

Do not promote extracted material without evidence, review, and approval.

## Longform Planning

Read: `docs/modules/longform-word-budget.md`, `docs/implementation/phase65-longform-word-budget.md`, `references/artifact-contracts.md`, `references/workflows.md`.

Use when the user asks for 100000+ words, multiple volumes,百万字级 projects, or when generated chapters are far shorter than the target.

Output: word budget markdown/JSON, platform-agent expansion sidecar, budgeted outline candidate, word-budget review, and generation readiness decision.

Do not satisfy a long target by asking every scene to be longer. Increase narrative inventory: chapters, scenes, relationship turns, consequences, setups, payoffs, and world-pressure events.

## Character / World / Outline Assets

Read: `docs/implementation/phase37-asset-candidate-schemas.md` through `docs/implementation/phase41-candidate-review-promotion.md`.

Output: candidate JSON/Markdown, review report, promotion recommendation, user approval question.

Do not write directly to confirmed canon or final character files unless the user explicitly approves.

## Scene Development

Read: `docs/modules/plot-scene-engine.md`, `docs/modules/character-engine.md`, `docs/implementation/phase20-branch-simulation.md`, `docs/implementation/phase22-scene-composer.md`, `docs/implementation/phase23-model-provider-prompt-pack.md`, `docs/implementation/phase24-character-state-evolution.md`, `docs/implementation/phase25-candidate-promotion-state-apply.md`.

Output: context packet, context trace, branch candidates, scene composition packet, draft candidate, review report, state patch.

## Review And Audit

Read: `docs/modules/review-ci.md`, `docs/implementation/phase4-scene-review-loop.md`, `docs/implementation/phase19-canon-lint.md`, `docs/implementation/phase7-chapter-pipeline.md`, `docs/implementation/phase8-longform-audit.md`.

Output: findings ordered by severity, revision plan, readiness status, approval gates.

## Export And Release

Read: `docs/implementation/phase9-export-package.md`, `docs/implementation/phase21-publish-chain.md`, `docs/implementation/phase15-approval-loop.md`.

Output: export package, release manifest, release notes, rollback notes.

## Formal Route CLI And Integration

Read: `references/workflows.md` for commands and `references/orchestration.md` for LangGraph/Dify/FastAPI.

Output: exact command, result summary, generated artifact paths.

Reminder: the local CLI is deterministic support infrastructure. The platform agent remains the project director and creative provider.
