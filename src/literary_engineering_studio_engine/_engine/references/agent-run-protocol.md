# Agent Run Protocol

Use this protocol whenever a tool-layer agent runs a literary engineering task through this skill. It is the non-optional operating loop that prevents skipped context, skipped review, and accidental promotion of generated material.

## Mandatory Loop

1. Classify the workspace.
   - Skill root: contains `SKILL.md`, `AGENTS.md`, `agentread.yaml`, `references/`, `templates/`, `schemas/`, and `src/` or `scripts/`.
   - Work project: contains `project.yaml`, `canon/`, `characters/`, `plot/`, `style/`, `sources/`, `scenes/`, `drafts/`, `reviews/`, `memory/`.
   - Style library: contains `authors/`, `works/`, `profiles/`, or `style_skills/`.
2. Select exactly one primary route from `agentread.yaml`. Add a secondary route only when the task truly crosses boundaries, such as style learning plus scene drafting.
3. Read the route references before changing artifacts. Do not read the whole repository by default.
4. Record a reading receipt in the working report or produced task artifact: selected route, references read, project-state files inspected, missing context, and whether any `.agent_tasks.md` remains pending.
5. Inspect current project state before planning: `project.yaml`, relevant canon/character/plot/style files, latest reviews, workflow runs, and approval records.
6. State a short plan to yourself or in the working trace: objective, route, artifacts to inspect, artifacts to create, review gates, and user approval boundary.
7. Probe documented tools before declaring them unavailable. Use `--help`, `protocol <route>`, or the smallest safe command attempt; if a command fails, record the exact command, error, and next workaround instead of guessing.
8. For formal `scene-development`, ask the CLI for the next formal operation with `task-next`, open the package with `task-open`, complete the work, submit artifacts with `task-submit`, then finalize with `task-complete`. Do not decide the next formal scene step from memory when the task registry is available.
9. Execute deterministic preparation with CLI whenever the selected formal route declares sidecars, manifests, or provenance gates: initialize, import/chunk sources, index, search, build context, lint, compose, export, or generate platform-agent task sidecars. Exploratory notes may skip CLI, but formal artifacts may not silently replace CLI outputs with hand-written files.
10. Perform every non-deterministic creative or judgment step as the supervising platform agent. This includes prose, JSON drafting, schema repair, roleplay, branch choice, review findings, style prompts, and promotion recommendations.
11. When a command writes `.agent_tasks.md`, read it, fill the expected Markdown/JSON/prose artifact yourself, inspect the produced artifact, then create the adjacent `.agent_completion.json` marker. Do not report the task file as completed work by itself.
12. For scene batches, maintain per-scene coverage. Each scene needs its own context, RP, branch selection, composition, prose candidate, exact-candidate review, promotion, promoted draft, and state patch; one completed scene does not cover the rest.
13. If sidecar completion, expected outputs, or route gates are unclear, run or emulate `agent-task-status` and route-specific `route-audit`; resolve the missing items or list them as pending.
14. Validate produced artifacts before acceptance:
   - JSON: schema validation or explicit schema review.
   - Canon and continuity: canon lint or platform-agent canon review.
   - Character logic: BDI, hidden `background_story`, relationship pressure, and OOC risk.
   - Style: mounted Style Skill and style prompt priority.
   - Chinese prose: `references/punctuation-standard.md`.
   - Release/export: readiness, approval, and target format checks.
15. If a prose review returns `pass_with_notes`, warnings, Style Lint findings, anti-evasion risks, or local fixes, run or emulate `revise-scene` and review the revision candidate before promotion, chapter readiness, export, or writeback. Do not replace a banned contrast with another explicit contrast; retained transitions require a burden-of-proof note.
16. Decide the artifact status: revise, keep as candidate, ask user, or promote after explicit user approval and clean review.
17. Finish with an audit summary: files changed, candidate-only files, promoted files, checks run, blocked items, reading receipt, and next high-level creative choices.

## Platform Agent Responsibilities

- Maintain conversation-level creative intent and project memory.
- Choose the route and avoid operational questions when the next action is clear.
- Keep generated work separate from canon until reviewed and approved.
- Use subagents only for bounded support passes when useful: character logic checks, world constraints, plot alternatives, style-risk lists, canon audit, retrieval summaries, schema checks, word-count inventories, or issue tables.
- The main platform agent must personally write creative body text. Subagents must not draft, rewrite, polish, expand, or finalize prose, screenplay, pseudo-record entries, or final deliverable text.
- Resolve disagreements between CLI reports, simulations, and generated candidates through project constraints and user intent.

## Non-Deterministic Work Gate

The following must never be delegated to local dry-run, HTTP helper, or CLI output as final authority:

- New prose, revision, synopsis, outline, scene, or script text.
- Character profiles, hidden background stories, relationship graphs, world rules, locations, and organizations.
- Existing-work reverse extraction into project brief, character, world, outline, timeline, foreshadowing, or style candidates.
- Longform word-budget interpretation, budgeted outline expansion, narrative-inventory sufficiency, and target-length tradeoffs.
- Style prompts, style effectiveness judgments, back-translation judgments, and mount decisions.
- JSON creation or repair when the JSON encodes creative judgment.
- Roleplay, branch simulation, consequence simulation, character-state evolution, and scene composition decisions.
- Scene review, canon review, committee review, candidate promotion recommendation, chapter readiness, and release choice.

Local tools may prepare inputs and task files for those actions, but the supervising platform agent must make the judgment and write or approve the artifact.

## Formal Vs Exploratory Outputs

Exploratory discussion, throwaway snippets, and analysis notes may be written without CLI provenance. They must stay outside formal candidate, promotion, chapter, export, and writeback lanes.

Formal artifacts are different. If an artifact may be promoted, counted toward word budget, exported, published, or written back to canon/characters/state, the agent must use the route's deterministic CLI sidecars and manifests where available. A hand-written file with the same path as a CLI output is exploratory/debug-only unless the agent first attempted the documented command, recorded the exact failure, and marked the replacement as a CLI-equivalent workaround for route audit and human review.

For `scene-development`, formal prose generation requires CLI-generated context, `simulate-scene --agent` roleplay, `branch-simulate --agent` branch manifest, formal `branch_selection.md`, `compose-scene --agent-tasks` composition, `generate-scene` prompt/task provenance, and exact-candidate review before promotion.

When `task-next` is available, the platform Agent should let the CLI-mediated task registry choose the next formal scene step. The correct loop is: `task-next`, `task-open`, perform the named command or platform-agent judgment, `task-submit`, `task-complete`, then `workflow-advance` or `route-audit`. The user can still discuss creative direction naturally; the task registry only controls formal artifacts.

## Command Attempt Rule

If a route names a command, the supervising agent should assume it can try that command with the local shell/tooling unless a real error proves otherwise. In particular, do not skip `agent-review-scene`, `agent-canon-review`, `agent-task-status`, `route-audit`, `promote-candidate`, `chapter-workspace`, or `export-package` because they sound model-backed or environment-dependent. Run `--help` first if uncertain. Many `agent-*` commands only generate sidecars, deterministic evidence such as `Style Lint (auto-detected)`, and expected output paths; the platform agent then performs the judgment and writes the artifacts.

If the command errors, the correct response is not “the skill cannot do it”; the correct response is: record the command, stderr/exception, whether `PYTHONPATH` or path arguments were wrong, and the next safe workaround. Only after an actual failure should the agent choose an emulation path.

## Completion Gate

Before final response, check:

- Route selected from `agentread.yaml`.
- Required references read for that route.
- Project state inspected.
- Documented commands needed for the route were attempted or deliberately skipped with a concrete reason based on project state.
- All `.agent_tasks.md` outputs handled with `.agent_completion.json` markers, or explicitly listed as pending.
- `agent-task-status` or route-specific `route-audit` used when route completion state was ambiguous.
- Reading receipt recorded or summarized.
- Review notes and anti-evasion risks resolved through revision and re-review before readiness/export/writeback.
- Generated JSON/prose/reviews are marked candidate, reviewed, approved, or pending.
- Canon, character, style, punctuation, and release/export gates applied when relevant.
- User approval requirement is recorded for promotions or final release.
- For scene batches, route-audit or an equivalent ledger accounts for every scene instead of sampling one scene.
- Final response separates completed work from pending decisions.

## Forbidden Shortcuts

- Do not accept generated JSON because it parses.
- Do not accept branch scores, simulation scores, local director choices, or model ratings as final decisions.
- Do not promote candidates without clean review and approval.
- Do not use debug/bypass flags such as `--allow-unreviewed`, `--allow-review-notes`, `--include-blocked`, `--allow-unapproved`, `--allow-unresolved`, `--allow-missing-composition`, `--allow-unselected-composition`, `--allow-recommended-branch`, or `--allow-missing-branch` during formal Skill-host work.
- Do not batch-write scenes while skipping RP, branch simulation, composition, exact-candidate review, promotion, or state patch for most scenes.
- Do not satisfy formal route gates by hand-writing files that merely imitate CLI outputs. Manual equivalents require a real attempted-command failure, recorded workaround provenance, and route-audit visibility.
- Do not declare a documented CLI/tool step impossible without probing it or recording a real command failure.
- Do not bypass failed readiness/export gates with a custom script and present the result as final release output.
- Do not skip punctuation review for Chinese prose because a Style Skill is mounted.
- Do not expose raw schemas, internal command chatter, or file paths to the user unless useful for the task or requested.
- Do not write API keys or provider secrets into work projects.
