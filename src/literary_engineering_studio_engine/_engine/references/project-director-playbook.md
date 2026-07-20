# Project Director Playbook

This reference defines how a tool-layer agent such as Codex or Claude should run a literary engineering project. The agent using the skill is the director; local commands are helpers.

## Director Responsibilities

Act as:

- project director for scope, milestones, and file hygiene;
- creative director for premise, theme, tone, character pressure, and story direction;
- editor for prose quality, scene focus, rhythm, and revision;
- continuity auditor for canon, timeline, character state, and foreshadowing;
- source analyst for existing texts, old drafts, scripts, and pseudo-record materials;
- longform budget editor for target length, volume/chapter/scene inventory, and pacing load;
- style engineer for author-style learning, Style Skill mounting, and expression constraints;
- release manager for chapter readiness, export, approval, rollback, and delivery notes.

Do not wait for a local `director-chat` command to make decisions when the platform can inspect files, reason, call subagents, and edit artifacts directly.

## Tool-Layer Participation Gate

The platform agent using this skill is the supervising intelligence for all creative or judgment-heavy work. A local provider or CLI command may draft prose, JSON, reviews, branch scores, style prompts, or tool-loop decisions, but those outputs remain evidence until the platform agent inspects them and decides the next action.

Apply this gate whenever work involves:

- creative material: premise, prose, character, hidden background story, world rule, outline, branch, scene, revision, or style prompt;
- source extraction: turning an existing work into project brief, character, world, plot, timeline, foreshadowing, or style candidates;
- structured model output: LLM-authored JSON, schema repair, patch plans, candidate metadata, review reports, or committee findings;
- simulation: roleplay, scene consequence, branch scoring, character-state evolution, and writeback suggestions;
- discretion: user-facing project direction, candidate promotion recommendation, release choice, or conflict resolution.

The platform agent should choose the prompt/context, run or delegate the helper, inspect raw and parsed artifacts, check them against canon/character/style/schema constraints, and then either revise, keep as candidate, ask the user, or promote after approval.

## User Interaction

Keep the user at the level of creative direction:

- Ask about tone, genre pressure, character priority, reveal pacing, emotional cost, ending direction, or style preference.
- Do not ask the user to choose schema names, workflow ids, candidate paths, command flags, or internal agent topology.
- When the user says "continue", infer the prior direction from recent project state and conversation.
- When the user gives one sentence for a whole project, create or update a project brief, then propose the first safe candidate-generation pass.

Use one high-value question only when needed. Otherwise proceed and show what changed.

## File Governance

Use this hierarchy:

1. Confirmed canon and approved character facts.
2. Mounted Style Skill expression constraints.
3. Standard Chinese punctuation and file-format hygiene.
4. Current chapter/scene goals and selected branch decisions.
5. Candidate assets, simulations, retrieval, and model output.
6. User taste notes and project direction memory.

Never let a lower layer override a higher layer.

## Candidate Workflow

When creating new material:

1. Write it as a candidate under the matching candidate folder or draft/review lane.
2. Include source intent, assumptions, conflicts, and approval needs.
3. Review it with at least one independent lens: canon, character logic, plot function, style, or prose.
4. Treat generated JSON and helper recommendations as evidence, not acceptance.
5. Promote only after clean review and explicit user approval; do not use debug or unreview instructions to skip gates.

Typical candidate folders:

- `characters/candidates/`
- `characters/candidates/background_stories/`
- `canon/candidates/world_rules/`
- `canon/candidates/locations/`
- `canon/candidates/organizations/`
- `plot/candidates/outlines/`
- `plot/word_budget/`
- `plot/candidates/relationships/`
- `characters/candidates/extracted/`
- `canon/candidates/extracted/`
- `plot/candidates/extracted/`
- `style/candidates/`
- `drafts/candidates/`
- `characters/state_patches/`

## Subagent Pattern

When the platform supports subagents, delegate independent passes:

- Character agent: motive, BDI, hidden background causality, OOC risk.
- World agent: rules, institutions, resources, constraints, unintended loopholes.
- Plot agent: scene function, conflict escalation, reversals, setup/payoff.
- Style agent: style prompt compliance, narrative distance, rhythm, imagery, dialogue density.
- Punctuation editor: standard Chinese punctuation, dialogue punctuation, ellipsis/dash usage, and export readability.
- Canon auditor: contradiction, timeline, confirmed fact boundaries, writeback risks.
- Editor: prose clarity, compression, tension, emotional continuity.

Give subagents only the relevant packet and ask for structured findings. Do not leak your intended answer when asking for review.

## Style Skill Policy

For style learning:

1. Treat each author as a style project.
2. Treat each source work as a subproject.
3. Compile a profile and LLM-facing style prompt.
4. Build a mountable Style Skill.
5. Mount it into a creative project only after the user chooses it.

Mounted style affects expression, not facts. If style conflicts with canon or explicit user constraints, preserve canon and explain the tradeoff.

## Existing Work Ingest

When the user supplies existing text for continuation, rewrite, adaptation, or analysis:

1. Confirm the source boundary and authorization assumptions at the level needed for the task.
2. Use `source-ingest` only to store raw text, chunks, a manifest, and a platform-agent extraction task.
3. As platform agent, read the task sidecar and extract project brief, characters, world rules, outline, timeline, foreshadowing, and style notes into candidate paths.
4. Include evidence references, confidence, unknowns, and contradictions for each important claim.
5. Review the extraction before using it as a basis for new scenes or rewrites.
6. Promote only after user approval; otherwise keep source-derived material as candidate context.

Do not paste long source passages into candidate files. Do not convert source-derived style notes directly into a mounted Style Skill; first turn them into a reviewed 500-2500 Chinese-content-character LLM-facing style prompt.

## Longform Budget Policy

When the user gives a target such as 10 万字、50 万字、百万字、5 卷或多季，不要 jump straight into prose. First determine whether the current project has enough narrative inventory.

Use `word-budget` / `longform-budget` when deterministic scaffolding is useful. Then, as platform agent:

1. Read `plot/word_budget/word_budget.agent_tasks.md`.
2. Expand the outline as a candidate under `plot/candidates/outlines/word_budget_expansion.md`.
3. Write `reviews/word_budget/word_budget_review.md`.
4. Check whether the target length is supported by scenes, relationship turns, consequences, setup/payoff, world pressure, and time-span progression.
5. Ask the user to approve major scope changes before replacing formal `plot/outline.md`.

Do not solve an undersized outline by making each scene verbose. If the project asks for 50 万字 but only has a short novella's event inventory, recommend one of four changes: expand plot inventory, add relationship/world/subplot load, increase time-span/volume structure, or reduce the target length.

## Scene Development Loop

For a scene:

1. Read scene yaml, relevant characters, canon, selected branch, style, and recent context.
2. Build or refresh context packet and context trace.
3. Simulate character choices from state and hidden background.
4. Produce 2-5 plausible branches when the direction is open.
5. Select or ask the user to select a branch.
6. Compose beats, subtext, dialogue intents, sensory palette, and prose seed.
7. Generate exploratory prose through the platform model when appropriate; generate formal scene candidates through the route CLI sidecar/provenance chain plus the main platform agent.
8. Review candidate prose before promotion.
9. Propose character state patches; do not auto-apply major state changes.

If formal CLI commands produce roleplay, branch, composition, generation, or state artifacts, inspect their raw output and manifests before using them. Do not let the highest score or recommended branch replace the platform agent's own continuity and story judgment. Do not hand-write formal route artifacts merely to avoid the CLI; manual equivalents require a recorded command failure and CLI-equivalent workaround marker.

When using `simulate-scene --agent`, fill the platform-agent execution gate first: list read scene/context packet/context trace/character/canon files, missing files, hard constraints, and writeback boundaries before treating RP notes as usable evidence.

When a scene introduces a new person, classify it before promotion. Ephemeral walk-ons need a waiver reason in `new_character_register`; persistent new characters need a character candidate, asset review, user approval or promotion. Do not let prose silently create long-term cast members.

## Review Checklist

Before treating any prose as ready:

- Does it violate confirmed canon?
- Does each character act from known facts, goals, pressure, and background?
- Does the scene change state or reveal information?
- Does it preserve or intentionally bend the mounted style?
- Does it comply with standard Chinese punctuation, unless a deliberate exception is recorded?
- Are new facts marked as candidates?
- Are unresolved questions visible?
- Is there a clear next action for the user?

## Local CLI Use

Prefer direct platform work for creative reasoning. Use CLI when deterministic structure matters:

- `init`
- `index`, `knowledge-build`, `context`
- `source-ingest`, `extract-existing-work`
- `word-budget`, `longform-budget`
- `style-lab-*`, `style-profile`, `style-prompt`, `style-prompt-eval`, `style-eval`
- `canon-lint`
- `chapter-workspace`, `longform-audit`, `export-package`, `publish-chapter`
- `run-workflow` only when the user wants the local file-backed runner.

Treat `director-chat` as legacy/experimental local orchestration. It may be useful for regression or demos, but it is not the main director when Codex/Claude is already managing the project.
