# CLI Run Protocol

Use this protocol whenever a formal route uses the `literary_engineering_studio_engine` CLI for sidecars, manifests, deterministic evidence, or provenance gates. The CLI is not the creative authority, but it is the formal route provenance layer where this skill provides commands.

Exploratory notes can be created without CLI. Formal artifacts that may be promoted, counted, exported, published, or written back must use the documented CLI chain when available, or record an attempted command failure plus a CLI-equivalent workaround artifact.

## Environment Setup

Development workspace:

```powershell
$env:PYTHONPATH = "<skill-root>\\src"
python -m literary_engineering_studio_engine --help
```

Installed packaged skill:

```powershell
$env:PYTHONPATH = "<skill-root>\\scripts"
python -m literary_engineering_studio_engine --help
```

Before running task commands, use:

```powershell
python -m literary_engineering_studio_engine protocol <route>
```

The `protocol` command prints the required references, suggested CLI chain, platform-agent handoff points, completion gates, and forbidden shortcuts for that route.

## Command Attempt Rule

Do not decide in advance that a documented command is unusable because it sounds like it needs a model, an external agent, or a special environment. First run `--help`, print `protocol <route>`, or attempt the smallest safe command with the current project path. If it fails, record the exact command, error, and next workaround. Many `agent-*` commands, including `agent-review-scene`, generate task sidecars; the platform agent then performs the review or creative judgment itself.

## CLI Usage Loop

1. Choose the route first. Do not start with a command just because it exists.
2. Run `protocol <route>` and read the printed preflight and completion gates.
3. Confirm whether the target is a skill root, work project, or style library.
4. Record or prepare a reading receipt: route, references read, project files inspected, command runbook printed, and missing context.
5. Set `PYTHONPATH` for the current repository layout.
6. Run `--help` for unfamiliar commands before use.
7. For formal `scene-development`, start with `task-next` and `task-open` unless the task is explicitly exploratory. The task package decides which underlying command or platform-agent judgment is next.
8. Run the smallest deterministic command that prepares the next artifact; do not skip it without a concrete project-state reason.
9. Capture and inspect output paths printed by the command.
10. If the command writes `.agent_tasks.md`, read the task file immediately when feasible and have the platform agent fill the expected artifact paths. The CLI has not completed the creative/review step by writing a task file.
11. After filling sidecars, inspect the produced Markdown/JSON/prose and record whether it is candidate, pass, pass_with_notes, revise_required, or pending.
12. Submit formal outputs with `task-submit` when the route is CLI-mediated.
13. Complete the task with `task-complete`; if it blocks, treat the blocking message as the next work item.
14. When sidecar or gate status is unclear, run `agent-task-status <project>` or `route-audit <project> --route <route>` and resolve or list pending items.
15. Validate artifacts:
   - `agent-validate` for agent run outputs.
   - schema-specific review for JSON candidates.
   - `canon-lint` for canon and character consistency.
   - `review-scene`, `agent-review-scene`, or platform review for prose.
   - `word-budget`, `longform-audit`, `chapter-workspace`, and approval summaries for longform/release.
16. Record whether each output remains a candidate, was revised, was promoted, or needs user approval.

## Common CLI Chains

### Project Initialization

```powershell
python -m literary_engineering_studio_engine protocol work-project-initialization
python -m literary_engineering_studio_engine init <project>
```

After scaffolding, the platform agent creates or revises the project brief, initial canon candidates, and approval boundaries.

### Source Ingest

```powershell
python -m literary_engineering_studio_engine protocol source-ingest
python -m literary_engineering_studio_engine source-ingest <project> --source <source-file-or-dir> --title "<title>" --work-id <work-id>
python -m literary_engineering_studio_engine task-next <project> --route source-ingest
python -m literary_engineering_studio_engine task-open <project> --task-id <task-id>
# Execute extraction sidecar, submit extracted candidates and review, then complete the task.
python -m literary_engineering_studio_engine task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_studio_engine task-complete <project> --task-id <task-id>
```

The CLI writes raw text, chunks, `source_manifest.json`, `source_ingest.md`, and `extract_project_files.agent_tasks.md`. The platform agent must read the sidecar and write extracted project brief, characters, world, outline, timeline, foreshadowing, style notes, and source-ingest review files as candidates. Under `task-next --route source-ingest`, these extracted candidates, `extract_project_files.agent_completion.json`, and a clean `pass` extraction review are formal route gates. Do not promote source-derived material without evidence, review, and approval.

### Longform Planning

```powershell
python -m literary_engineering_studio_engine protocol longform-planning
python -m literary_engineering_studio_engine task-next <project> --route longform-planning
python -m literary_engineering_studio_engine task-open <project> --task-id <task-id>
# Execute the task package, submit artifacts, then complete the task.
python -m literary_engineering_studio_engine task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_studio_engine task-complete <project> --task-id <task-id>
```

Preferred formal control now uses the task registry above. The underlying deterministic command for the first task is:

```powershell
python -m literary_engineering_studio_engine word-budget <project> --target-words 500000 --volumes 5 --genre mystery
```

The CLI writes `plot/word_budget/word_budget.md`, `plot/word_budget/word_budget.json`, and `plot/word_budget/word_budget.agent_tasks.md`. The platform agent must read the sidecar, create `plot/candidates/outlines/word_budget_expansion.md`, write `reviews/word_budget/word_budget_review.md`, and decide whether the project has enough narrative inventory before bulk generation. Under `task-next --route longform-planning`, these outputs and the sidecar completion marker are formal task expected outputs, not optional notes.

The same command also binds the budget to chapter and scene inventory. It writes `plot/word_budget/scene_inventory_expansion.agent_tasks.md` and `plot/chapter_obligations/chapter_obligations.agent_tasks.md`; the platform agent must use them to create `plot/candidates/scenes/word_budget_scene_inventory.md`, `reviews/word_budget/scene_inventory_review.md`, a chapter-obligation planning pass, and `reviews/word_budget/chapter_obligation_review.md`. Under the task registry, the route is not ready until `word_budget.agent_completion.json`, `scene_inventory_expansion.agent_completion.json`, and `chapter_obligations.agent_completion.json` exist, the required candidate/review artifacts exist, and all reviews have clean `pass` conclusions. The scene inventory candidate should list per-chapter target Chinese-content characters, existing cleaned body characters, missing scenes, and expansion tasks instead of merely asking current scenes to grow longer.

Use `longform-budget` as an alias. Do not treat `word_budget.json` as final plot; it is a numerical scaffold and readiness signal.

For 100000+ word or multi-volume work, formal scene generation is blocked unless the word-budget sidecar has a completion marker and the budget review exists. Each scene should declare a budgeted `chapter_id`; optional `word_count_target`, `word_count_min`, and `word_count_max` in `scene.yaml` become hard generation and review properties. Before prose for a chapter, run `chapter-obligation <project> --chapter-id <chapter_id>`, then have the platform agent fill the generated chapter contract and completion marker. `context`, `compose-scene`, `generate-scene`, `agent-review-scene`, `promote-candidate`, `route-audit`, `chapter-workspace`, and export readiness all use cleaned deliverable prose when checking the budget, and use `reader_experience_contract` / `reader_experience_adherence` to block summary-like scenes that do not satisfy reader questions, promised rewards, payoff/delay, tension source, anti-summary requirements, and aftertaste. Workflow/canon/status notes must not be counted as body length.

Formal target length and style-prompt length use Chinese-content characters, including Han characters and Chinese punctuation. Machine non-whitespace counts are diagnostic mappings only; if they disagree, use the Chinese-content count for pass/fail and inspect whether English paths, JSON keys, Markdown, or workbench traces leaked into the body. A machine mapping can explain front-end or platform counters, but it must never promote an under-target scene.

Check route readiness before bulk scene generation:

```powershell
python -m literary_engineering_studio_engine route-audit <project> --route longform-planning
```

### Style Engineering

```powershell
python -m literary_engineering_studio_engine protocol style-engineering
python -m literary_engineering_studio_engine task-next <project> --route style-engineering
python -m literary_engineering_studio_engine task-open <project> --task-id <task-id>
# Execute style prompt / evaluation task, submit artifacts, then complete.
python -m literary_engineering_studio_engine task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_studio_engine task-complete <project> --task-id <task-id>
```

The preferred formal control for project-local style profiles is the task registry above. Underlying commands include:

```powershell
python -m literary_engineering_studio_engine protocol style-engineering
python -m literary_engineering_studio_engine style-lab-author <style-library> <author-id>
python -m literary_engineering_studio_engine style-lab-work <style-library> <author-id> <work-id>
python -m literary_engineering_studio_engine style-lab-import <style-library> <author-id> <work-id> <source-text>
python -m literary_engineering_studio_engine style-lab-compile <style-library> <author-id>
python -m literary_engineering_studio_engine style-lab-build-skill <style-library> <author-id>
python -m literary_engineering_studio_engine style-lab-mount <project> <style-skill>
```

The platform agent must write or approve the LLM-facing style prompt and judge its effectiveness. Exact imitation is limited to public-domain or authorized corpora.

`style-lab-compile`, `style-prompt`, and `style-prompt-eval` write `.agent_tasks.md` sidecars; they do not finish the creative/evaluative step by themselves. Before `style-lab-build-skill`, the platform agent must create `style_prompt.md` and `style_prompt.agent.json`; the prompt must be detailed but executable, 500-2500 Chinese-content characters after Markdown scaffolding is stripped, and include the required high-quality prompt blocks. Before default `style-lab-mount`, at least one `style_eval_*.json` effectiveness/risk review must exist and pass the mount readiness gate. Under `task-next --route style-engineering`, style prompt sidecar completion, prompt quality, and accepted style evaluation are formal route gates. Formal Skill hosts must not use `--allow-unreviewed` to bypass style readiness.

### Character And World Assets

Preferred formal control loop:

```powershell
python -m literary_engineering_studio_engine protocol character-and-world-assets
python -m literary_engineering_studio_engine task-next <project> --route character-and-world-assets
python -m literary_engineering_studio_engine task-open <project> --task-id <task-id>
# Run asset-create / agent-create-* when the intake task asks for it, or complete the current asset sidecar/review/approval/promotion task.
python -m literary_engineering_studio_engine task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_studio_engine task-complete <project> --task-id <task-id>
```

Underlying commands:

```powershell
python -m literary_engineering_studio_engine protocol character-and-world-assets
python -m literary_engineering_studio_engine agent-create-character <project> --brief "<brief>"
python -m literary_engineering_studio_engine review-candidate-asset <project> <candidate>
python -m literary_engineering_studio_engine promote-candidate-asset <project> <candidate> --approval-run-id <id>
```

The platform agent writes candidate content, reviews motive/canon/style risks, and asks for approval before promotion. Under `task-next --route character-and-world-assets`, the formal route gates are: asset creation sidecar completion, candidate JSON/report, review sidecar completion, clean `pass` review, matching approve record, promotion manifest, no `allow_unapproved`, and promoted outputs. Review is not approval.

### Scene Development

The following chain is for one scene. In a chapter or volume batch, repeat it for every `scenes/{scene_id}.yaml`; never use one completed scene as a proxy for the remaining scenes.

Preferred formal control loop:

```powershell
python -m literary_engineering_studio_engine protocol scene-development
python -m literary_engineering_studio_engine task-next <project> --route scene-development --scene scenes/scene_0001.yaml
python -m literary_engineering_studio_engine task-open <project> --task-id <task-id>
# Read workflow/tasks/<task-id>.agent_tasks.md.
# Run the named underlying command or perform the platform-agent judgment/body-writing task.
python -m literary_engineering_studio_engine task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_studio_engine task-complete <project> --task-id <task-id>
python -m literary_engineering_studio_engine workflow-advance <project> --route scene-development
```

Repeat the `task-next` / `task-open` / `task-submit` / `task-complete` loop until the scene reaches ready. `workflow-advance` only refreshes artifact-derived state; it does not allow manual state jumps.

Underlying commands used by task packages:

```powershell
python -m literary_engineering_studio_engine protocol scene-development
python -m literary_engineering_studio_engine context <project> --scene scenes/scene_0001.yaml
python -m literary_engineering_studio_engine simulate-scene <project> --scene scenes/scene_0001.yaml --agent
python -m literary_engineering_studio_engine branch-simulate <project> --scene scenes/scene_0001.yaml --agent
# Platform agent fills branches/scene_0001/branch_selection.md with decision: selected and selected_branch.
python -m literary_engineering_studio_engine compose-scene <project> --scene scenes/scene_0001.yaml --agent-tasks
python -m literary_engineering_studio_engine route-audit <project> --route scene-development
python -m literary_engineering_studio_engine generate-scene <project> --scene scenes/scene_0001.yaml
python -m literary_engineering_studio_engine agent-review-scene <project> --scene scenes/scene_0001.yaml --draft drafts/candidates/scene_0001-platform-agent.md
# Read reviews/agent/scene_0001_scene_review.agent_tasks.md, including Style Lint evidence, then write the expected scene_review.v1 JSON and Markdown report yourself as platform agent.
python -m literary_engineering_studio_engine promote-candidate <project> --scene scenes/scene_0001.yaml
python -m literary_engineering_studio_engine review-scene <project> --scene scenes/scene_0001.yaml
python -m literary_engineering_studio_engine revise-scene <project> --scene scenes/scene_0001.yaml
python -m literary_engineering_studio_engine state-evolve <project> --scene scenes/scene_0001.yaml --agent-tasks
```

`context` must print and produce two formal artifacts: `memory/context_packets/{scene_id}.md` and `memory/context_packets/{scene_id}.trace.json`. The Markdown packet is the compact working memory; the trace is the machine-readable proof of which scene, canon, character, style, word-budget and retrieval sources were loaded. If the trace is missing, invalid, points to the wrong scene/context packet, or reports missing required context, stop and rerun/fix `context` before RP, branch, composition, generation, review, revision, promotion, chapter readiness, or export.

The main platform agent must handle every task sidecar, formally record branch selection before composition/generation, personally draft the prose candidate, review the exact candidate before promotion, then review promoted draft character causality, mounted style adherence, punctuation, deterministic Style Lint evidence, anti-evasion revision integrity, and state-patch consequences. Subagents may provide only bounded mechanical support such as evidence summaries, issue lists, schema checks, continuity tables, and word-count inventories; they must not draft, rewrite, polish, expand, or finalize body text.

If drafting or revising introduces a person not already in `characters/*.yaml` or the scene participant/reference lists, fill `new_character_register` in the candidate manifest and AgentReview JSON. Ephemeral walk-ons require a waiver reason. Persistent new characters require `characters/candidates/` asset creation, candidate asset review, user approval or promotion before AgentReview can clean pass; otherwise keep the scene blocked as `needs_candidate`, `needs_review`, or `needs_approval`.

Formal scene generation is CLI-provenance-gated: context must come from `context` or a recorded CLI-equivalent workaround; RP must come from `simulate-scene --agent`; branch manifest must come from `branch-simulate --agent`; composition must come from `compose-scene --agent-tasks` and include `formal_cli_provenance.created_by=compose-scene`; candidate generation must come from `generate-scene`, with prompt manifest, `.agent_tasks.md`, and platform-agent candidate manifest. Manual file creation before generation is exploratory/debug-only and cannot satisfy formal route gates merely because the filenames match.

`agent-review-scene` must be tried, not guessed about: it generates the review task, `Style Lint (auto-detected)` evidence, anti-evasion protocol, and expected report paths; the supervising platform agent performs the review and writes `scene_review.v1`, explicitly handling medium-or-higher lint findings and disguised contrast replacements. `promote-candidate` blocks unless the candidate has formal generation provenance, `reviews/agent/{scene_id}_scene_review.json` cites the exact candidate path and has a clean `conclusion=pass`, and the candidate passes Style Lint Gate: mechanical contrast frames, evasive contrast frames, and medium+ AI trace findings block, low findings stay notes-only. Formal Skill hosts must not use `--allow-unreviewed` or `--allow-review-notes`. `route-audit --route scene-development` is the per-scene ledger and must show that each scene has context packet, valid context trace, RP CLI provenance, branch CLI provenance, formal branch selection, composition CLI provenance, prose candidate generation provenance, exact-candidate review, Style Lint clean/notes-only, promotion manifest, promoted draft, static `review-scene` clean pass, and state patch before chapter/export readiness. If a revision candidate is used, route-audit also requires a clean anti-evasion revision manifest. When `style/active_style_skill.json` exists, formal chapter readiness and export require `style_adherence.status=pass`; `pass_with_notes`, `not_applicable`, missing, or `revise_required` blocks readiness/export until revised and re-reviewed. Use `revise-scene` when `agent-review-scene`, `review-scene`, Style Lint Gate, style adherence, or human notes identify local fixes; it writes a revision prompt manifest and `.agent_tasks.md` that asks the main platform agent to produce a revision candidate and report without overwriting the formal draft.

### Review And Audit

```powershell
python -m literary_engineering_studio_engine protocol review-and-audit
python -m literary_engineering_studio_engine task-next <project> --route review-and-audit
python -m literary_engineering_studio_engine task-open <project> --task-id <task-id>
python -m literary_engineering_studio_engine canon-lint <project>
python -m literary_engineering_studio_engine agent-canon-review <project>
python -m literary_engineering_studio_engine agent-committee <project>
python -m literary_engineering_studio_engine longform-audit <project>
python -m literary_engineering_studio_engine task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_studio_engine task-complete <project> --task-id <task-id>
python -m literary_engineering_studio_engine agent-task-status <project>
python -m literary_engineering_studio_engine route-audit <project> --route review-and-audit
```

Use `task-next --route review-and-audit` as the formal controller when available. The route starts with deterministic `canon-lint`, then requires the platform agent to complete `agent-canon-review`, write clean canon review JSON/Markdown, run `longform-audit`, and complete final committee review. A deterministic report is evidence, not creative review; `pass_with_notes`, warnings, unresolved facts, timeline risks, committee action items, or disagreements all remain blocking until resolved.

### Task And Route Dashboard

```powershell
python -m literary_engineering_studio_engine agent-task-status <project>
python -m literary_engineering_studio_engine route-audit <project> --route scene-development
python -m literary_engineering_studio_engine workflow-dashboard <project>
```

`agent-task-status` scans project `.agent_tasks.md` files, checks whether their expected artifact paths exist, and writes `workflow/agent_task_status.md` / `.json`. `route-audit` writes `workflow/route_audit.md` / `.json` and adds route-specific gates such as word-budget expansion, scene sidecar completion, promotion candidate review, mounted-style adherence review, chapter readiness, and export readiness. These commands are diagnostic; the platform agent must still complete creative tasks or record why they remain pending.

`workflow-state` writes `workflow/route_state.md` / `.json` as a persistent route ledger. It records the current step per scene, planning item, source import, style profile, asset candidate, review route, or chapter release target and the next action, including missing sidecar completion markers, missing budget contracts, missing review outputs, missing approvals, missing export artifacts, and missing state patches.

`workflow-dashboard` writes `workflow/dashboard/workflow_dashboard.md` / `.json` / `.html`. It refreshes overall route state, sidecar status, seven route-audit snapshots, and recent task events into a read-only cockpit. Use it when a platform Agent, user, or frontend needs one current view of blockers and next actions. It does not submit artifacts, complete sidecars, approve releases, or advance workflow state.

`task-next` reads that state ledger and writes a CLI-mediated task package under `workflow/tasks/`. `task-open` marks the package as opened. `task-submit` records the artifacts produced by the platform Agent. `task-complete` checks expected outputs and writes the task completion marker. `workflow-events` renders `workflow/events/task_events.jsonl` as a readable event report.

`task-open` also resolves the task `prompt_asset_id` through the file-backed Prompt Registry under `templates/prompt_assets/` and injects the matched Prompt Asset into the task Markdown. Use these registry commands when a task prompt looks incomplete or when adding new routes:

```powershell
python -m literary_engineering_studio_engine prompt-registry-list
python -m literary_engineering_studio_engine prompt-registry-validate
python -m literary_engineering_studio_engine prompt-preview route.scene-development.prose.generate.v1
```

### Export And Release

```powershell
python -m literary_engineering_studio_engine protocol export-and-release
python -m literary_engineering_studio_engine task-next <project> --route export-and-release
python -m literary_engineering_studio_engine task-open <project> --task-id <task-id>
python -m literary_engineering_studio_engine chapter-workspace <project> --chapter-id chapter_0001 --agent-review
python -m literary_engineering_studio_engine export-package <project> --chapter-id chapter_0001 --docx
python -m literary_engineering_studio_engine publish-chapter <project> --chapter-id chapter_0001 --approval-run-id <id>
python -m literary_engineering_studio_engine task-submit <project> --task-id <task-id> --from <artifact>
python -m literary_engineering_studio_engine task-complete <project> --task-id <task-id>
```

Use `task-next --route export-and-release` as the formal controller when available. Before delivery, confirm readiness, approvals, canon audit, punctuation, target format, and rollback notes. `export-package` rebuilds or verifies the chapter workspace before packaging and blocks non-ready scenes by default; formal Skill hosts must not use `--include-blocked`.

If `export-package` blocks, do not write a custom export script, use debug flags, or call the output final. Run `chapter-workspace` / `route-audit`, resolve missing scene reviews or sidecars, then export through the formal path. Final reader-facing files must not contain scene IDs, canon/workflow notes, review state, writeback candidates, internal paths, or `[AGENT_TASK: ...]`; provenance belongs in manifests and workbench files.

## Completion Gate

Do not finish a CLI-backed task until:

- The route protocol was read or printed.
- Documented commands needed by the route were tried or skipped only with a concrete project-state reason.
- Formal artifacts carry CLI sidecar/manifest provenance or a recorded attempted-command failure plus CLI-equivalent workaround marker.
- Reading receipt was recorded or summarized.
- Command output paths were inspected.
- `.agent_tasks.md` files were handled by the platform agent or listed as pending.
- `agent-task-status` or route-specific `route-audit` ran when completion state was ambiguous.
- Generated artifacts have explicit status.
- Relevant validation/review commands ran or were deliberately skipped with a reason.
- Final response reports commands run, important artifacts, checks, and pending approvals.
