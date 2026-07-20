# Workflows

These commands are deterministic helpers and formal-route provenance generators for a tool-layer director. In normal Codex/Claude use, the platform agent remains the creative authority, but formal routes use the CLI sidecar/manifest chain where available. Exploratory notes may skip CLI; formal artifacts that may be promoted, counted, exported, published, or written back must preserve CLI provenance or a recorded attempted-command failure plus CLI-equivalent workaround.

Use the CLI when repeatability matters: scaffolding, indexing, context packets, style compilation, schema/lint checks, audits, exports, and regression tests.

## Mandatory CLI Protocol

Before any route-specific command chain:

1. Select the primary route from `agentread.yaml`.
2. Read `references/agent-run-protocol.md`.
3. Read `references/cli-run-protocol.md` when a CLI command will be used.
4. Print the route runbook:

```powershell
$env:PYTHONPATH = "<skill-root>\\src"       # development copy
# or: $env:PYTHONPATH = "<skill-root>\\scripts"  # installed package
python -m literary_engineering_studio_engine protocol <route>
```

Use route keys such as `project-director`, `work-project-initialization`, `style-engineering`, `source-ingest`, `longform-planning`, `character-and-world-assets`, `scene-development`, `review-and-audit`, `export-and-release`, and `optional-cli`.

The task is not complete until the route completion gates in the runbook are accounted for.

## Tool-Layer Supervision Rule

Any command that writes creative material, drafts JSON, repairs schema output, simulates characters, scores branches, composes scenes, or chooses workflow steps is supervised by the tool-layer agent that loaded this skill. Formal commands write `.agent_tasks.md` sidecars and expected artifact paths; the platform agent fills those artifacts. The command must not become the project director by itself.

Before running such a command, the platform agent should choose the task, prompt/context packet, constraints, and approval boundary. After running it, the platform agent must read the task sidecar, write or inspect the expected artifacts, validate schema where relevant, check canon/character/style constraints, and decide whether to revise, keep as candidate, ask the user, or promote after approval.

This rule covers `source-ingest`, `extract-existing-work`, `word-budget`, `longform-budget`, `agent-task-status`, `route-audit`, `prompt-registry-list`, `prompt-registry-validate`, `prompt-preview`, `agent-create-*`, `asset-create`, `agent-build-json`, `agent-review-scene`, `agent-canon-review`, `review-candidate-asset`, `agent-plan-patch`, `agent-style-prompt`, `agent-committee`, `style-prompt`, `style-prompt-eval`, `style-lab-compile`, `simulate-scene`, `branch-simulate`, `compose-scene`, `generate-scene`, `revise-scene`, `state-evolve`, and `run-workflow`.

Use `agent-task-status` and `route-audit` as diagnostic gates when the workflow state is no longer obvious. They scan sidecars, missing expected outputs, and route gates; they do not replace platform-agent judgment or complete the pending creative work.

Use `prompt-registry-validate` after adding or renaming formal task prompt ids. Use `prompt-preview <prompt_asset_id>` to inspect the route prompt that `task-open` will inject into a task package.

`agent-run`, `agent-repair`, provider-backed Python functions, `/director/chat`, and `director-chat` are legacy/debug paths. Use them only when the user explicitly asks to test local provider behavior.

Use the bundled CLI through:

```powershell
$env:PYTHONPATH = "<skill-root>\\scripts"
python -m literary_engineering_studio_engine <command>
```

## Configure Global Provider Settings

Long-lived model and console defaults live in `%USERPROFILE%\.lew\config.json` by default. Use `LEW_CONFIG_PATH` only when you want a separate config file.

```powershell
python -m literary_engineering_studio_engine config-init
python -m literary_engineering_studio_engine config-show
```

For DeepSeek official API:

```powershell
$env:DEEPSEEK_API_KEY = "your-api-key"
python -m literary_engineering_studio_engine config-set-profile `
  --name deepseek `
  --api-base "https://api.deepseek.com" `
  --model "deepseek-v4-flash" `
  --api-key-env "DEEPSEEK_API_KEY" `
  --temperature 0.4 `
  --max-tokens 4000 `
  --timeout 120 `
  --activate
```

The config file can store provider settings and, for local use, a saved profile `api_key`. Config endpoints and previews redact the key. `LEW_MODEL_*` variables still work as temporary overrides.

Formal creative/review commands ignore provider routing and target the platform agent through task sidecars. Global provider settings remain only for legacy/debug commands and local API experiments.

## Initialize A Work Project

```powershell
python -m literary_engineering_studio_engine init "<work-dir>" --title "作品名" --premise "一句话故事前提" --genre "类型"
```

Creates:

- `project.yaml`
- `AGENTS.md`
- `agentread.yaml`
- `canon/`
- `characters/`
- `plot/`
- `style/`
- `sources/`
- `scenes/`
- `drafts/`
- `reviews/`
- `memory/`
- `branches/`
- `exports/`
- `releases/`

Character files include `background_story`. Use it as an internal cause of behavior, not as direct exposition in final prose.

For long projects, keep each character in a separate `characters/{character_id}.yaml` file and set `importance`. Major characters are loaded into most scene context packets; secondary/cameo characters are loaded only when the scene includes them in `participants`, `referenced_characters`, or `character_refs`. Scene files should therefore list every on-page participant and any off-page character whose memory, threat, relationship, or background pressure materially affects the scene.

When a scene introduces a person who is not in `characters/*.yaml` or the scene participant/reference lists, treat it as a New Character Register event. Ephemeral walk-ons may remain local to the scene only if AgentReview records `new_character_register.status=ephemeral_only` with a waiver reason. Named, recurring, clue-bearing, relationship-changing, plot-facing, or state-changing figures are persistent new characters: create a candidate with `agent-create-character` or `asset-create --asset-type character`, review it with `review-candidate-asset`, obtain user approval, and promote it before AgentReview can clean pass. Do not add persistent new characters directly to `characters/*.yaml`, and do not hide them as vague extras if they carry future story function.

## Import Existing Works For Continuation Or Rewrite

Use this when the user provides an existing text, old draft, complete work, script, or pseudo-record source and wants the project to continue, rewrite, adapt, or analyze it.

```powershell
python -m literary_engineering_studio_engine protocol source-ingest
python -m literary_engineering_studio_engine source-ingest "<work-dir>" `
  --source "<source-file-or-dir>" `
  --title "源作品标题" `
  --work-id "source-work" `
  --mode continuation
```

`--source` accepts `.txt`, `.md`, or `.markdown` files and directories. `--text` can be used for short pasted material:

```powershell
python -m literary_engineering_studio_engine source-ingest "<work-dir>" --text "源文本片段" --title "旧稿" --work-id old-draft
```

The command writes:

- `sources/imports/{work_id}/raw/*.txt`
- `sources/imports/{work_id}/chunks/chunk_0001.md`
- `sources/imports/{work_id}/source_manifest.json`
- `sources/imports/{work_id}/source_ingest.md`
- `sources/imports/{work_id}/extract_project_files.agent_tasks.md`

The platform agent must then read `extract_project_files.agent_tasks.md` and write the expected candidate outputs:

- `sources/imports/{work_id}/extracted/project_brief.md`
- `characters/candidates/extracted/{work_id}_characters.md`
- `canon/candidates/extracted/{work_id}_world.md`
- `plot/candidates/extracted/{work_id}_outline.md`
- `plot/candidates/extracted/{work_id}_timeline.md`
- `plot/candidates/extracted/{work_id}_foreshadowing.md`
- `style/candidates/{work_id}_style_generation_notes.md`
- `reviews/source_ingest/{work_id}_extraction_review.md`

Every extracted claim should include evidence references, confidence, unknowns, and contradiction notes. Do not copy long source passages into project files. Do not promote extracted settings into formal canon, character files, plot files, or mounted style without review and user approval.

## Plan Longform Word Budget

Use this before generating or expanding a work with a large target length. A 50 万字 / 5 卷 project needs enough scene inventory; it cannot be solved by asking a small outline to produce longer prose.

```powershell
python -m literary_engineering_studio_engine protocol longform-planning
python -m literary_engineering_studio_engine word-budget "<work-dir>" `
  --target-words 500000 `
  --volumes 5 `
  --genre mystery `
  --time-span "三年"
```

`word-budget` writes:

- `plot/word_budget/word_budget.md`
- `plot/word_budget/word_budget.json`
- `plot/word_budget/word_budget.agent_tasks.md`
- `plot/word_budget/scene_inventory_expansion.agent_tasks.md`
- `plot/chapter_obligations/chapter_obligations.agent_tasks.md`

The platform agent must read the task sidecar and write:

- `plot/candidates/outlines/word_budget_expansion.md`
- `reviews/word_budget/word_budget_review.md`
- `plot/candidates/scenes/word_budget_scene_inventory.md`
- `reviews/word_budget/scene_inventory_review.md`
- `reviews/word_budget/chapter_obligation_review.md`

The budgeted outline candidate should map Chinese-content target length to narrative inventory: volumes, chapters, scenes, relationship turns, world-pressure events, consequences, setup/payoff, and pacing relief. The scene-inventory candidate should bind each chapter to target Chinese-content characters, actual cleaned-body Chinese-content characters, machine count diagnostics, missing scene counts, and expansion tasks. The chapter-obligation review should confirm every chapter has reader questions, promised rewards, withheld information, payoff/delay strategy, and anti-summary requirements. Do not overwrite `plot/outline.md` or formal `scenes/*.yaml` until the candidate passes review and the user approves it.

Before prose for a specific chapter, create the per-chapter reader contract:

```powershell
python -m literary_engineering_studio_engine chapter-obligation "<work-dir>" --chapter-id chapter_0001
```

The platform agent must fill `plot/chapter_obligations/chapter_0001.json`, update the readable Markdown companion, and create `chapter_0001.agent_completion.json`. This is where scene-level `reader_question`, `promised_reward`, `withheld_information`, `payoff_or_delay`, `tension_source`, `anti_summary_requirement`, and `reader_aftertaste` become generation constraints.

Then audit:

```powershell
python -m literary_engineering_studio_engine longform-audit "<work-dir>" --target-length 500000
```

If the budget status is `needs_expansion`, resolve the outline, scene inventory, and chapter obligation before bulk scene generation. Later `generate-scene` prompt manifests automatically include the word-budget standard when `plot/word_budget/word_budget.json` exists. For formal longform work, each `scenes/*.yaml` should carry a real `chapter_id` that maps to the budget row, and may carry `word_count_target`, `word_count_min`, and `word_count_max` overrides. These are Chinese-content-character targets, counting Han characters and Chinese punctuation. The scene word-budget and reader-experience contracts are injected into context packets, `compose-scene` output, prompt manifests, and generation sidecars; AgentReview, `promote-candidate`, `route-audit`, `chapter-workspace`, and export readiness recompute cleaned-body Chinese-content length and reader promise/payoff adherence before passing the scene, while machine nonspace counts remain diagnostics.

## Cross-route dashboard

Use the dashboard when a platform Agent, user, or local frontend needs one read-only view of pending formal work:

```powershell
python -m literary_engineering_studio_engine workflow-dashboard <project>
```

It writes:

```text
workflow/dashboard/workflow_dashboard.json
workflow/dashboard/workflow_dashboard.md
workflow/dashboard/workflow_dashboard.html
```

The command refreshes overall workflow state, agent task status, every formal route audit, and recent task events. It does not complete tasks, submit artifacts, approve releases, or advance workflow state. Treat blocking rows as repair tasks, then return to `task-next` / `task-open` / `task-submit` / `task-complete`.

Before bulk scene generation, check:

```powershell
python -m literary_engineering_studio_engine route-audit "<work-dir>" --route longform-planning
```

## Build A Demo Project

```powershell
python -m literary_engineering_studio_engine demo-project "<demo-work-dir>" --title "文学工程 Demo"
```

The demo uses original sample text and writes platform-agent task sidecars for asset creation, scene/canon review, committee review, and workflow continuation. It does not call local dry-run or HTTP providers for formal artifacts.

## Build Memory And Context

```powershell
python -m literary_engineering_studio_engine index "<work-dir>"
python -m literary_engineering_studio_engine search "<work-dir>" "人物 地点 线索"
python -m literary_engineering_studio_engine knowledge-build "<work-dir>"
python -m literary_engineering_studio_engine knowledge-search "<work-dir>" "人物 地点 线索" --canon-status confirmed
python -m literary_engineering_studio_engine context "<work-dir>" --scene scenes/scene_0001.yaml --rebuild-index
```

Use `context` before scene drafting or roleplay simulation. The command writes both:

- `memory/context_packets/{scene_id}.md`
- `memory/context_packets/{scene_id}.trace.json`

The Markdown packet is the compact working memory. The trace JSON is the source proof: it records required context groups, loaded files, summarized retrieval sources, excluded files, mounted style sources, word-budget source, character files, canon files, and missing required context. Inspect both paths printed by stdout. If a project has only the context packet without the trace, `workflow-state` / `task-next` will issue a `context-trace` repair task and formal generation/review/readiness should remain blocked until `context` is rerun.

Use `knowledge-build` when a workflow needs metadata-rich retrieval with canon status, source kind, scene id, chapter id, or character id.

## Compile A Style Profile

```powershell
python -m literary_engineering_studio_engine style-profile "<corpus-dir>" --out-dir "<work-dir>\\style\\demo-author" --name "示例文风" --author "示例作者" --source-note "公版或授权语料"
```

Use exact imitation only for public-domain or authorized corpora. For other authors, abstract high-level craft features. The final style-learning asset is an LLM-facing prompt, not the metrics report:

```powershell
python -m literary_engineering_studio_engine style-prompt "<work-dir>\\style\\demo-author"
```

This writes `style_prompt.agent_tasks.md` plus expected `style_prompt.md` and `style_prompt.agent.json` paths. The platform agent reads the task and writes the actual LLM-facing style constraint prompt.

Evaluate a back-translated or outline-expanded candidate:

```powershell
python -m literary_engineering_studio_engine style-eval "<work-dir>\\style\\demo-author" --reference "<reference.txt>" --candidate "<candidate.txt>" --mode back-translation
```

Outputs JSON metrics and a markdown report under `evaluation_results/{mode}/`, including style similarity and copy-risk indicators.

Ask the platform agent to generate a back-translation / outline-expansion candidate through `style_prompt.md`, then evaluate prompt effectiveness:

```powershell
python -m literary_engineering_studio_engine style-prompt-eval "<work-dir>\\style\\demo-author" --reference "<reference.txt>" --input "<english-or-outline.txt>" --mode back-translation
```

## Style Lab

The local frontend exposes this as `文风学习`. Treat each author as a style project, each source work as a subproject, and the generated Style Skill as the mountable artifact for creative projects.

```powershell
python -m literary_engineering_studio_engine style-lab-author --name "作者名" --source-note "公版或授权语料"
python -m literary_engineering_studio_engine style-lab-work --author-id "<author-id>" --title "作品名"
python -m literary_engineering_studio_engine style-lab-import --author-id "<author-id>" --work-id "<work-id>" --file "<source.txt>"
python -m literary_engineering_studio_engine style-lab-compile --author-id "<author-id>"
python -m literary_engineering_studio_engine style-lab-build-skill --author-id "<author-id>"
python -m literary_engineering_studio_engine style-lab-mount "<work-dir>" --style-id "<style-id>"
```

`style-lab-compile` and the front-end `/style-lab/compile` endpoint compile deterministic profile/metrics, then write a platform-agent task sidecar for `style_prompt.md` and `style_prompt.agent.json`. They do not call a local provider for the LLM-facing prompt. The platform agent must read the task, write both expected artifacts, and inspect them before building a Style Skill. A release-grade prompt must be 500-2500 Chinese-content characters, counting Han characters and Chinese punctuation after Markdown scaffolding is stripped: under 500 is too thin to constrain style, while over 2500 is too diffuse for stable mounting. It must also satisfy high-quality prompt structure: identity/boundary, priority, core mechanism, narrative distance, syntax/rhythm, punctuation, imagery/sensory, psychology/behavior, dialogue/tone, forbidden tendencies, and output self-check.

`style-prompt-eval` and `/style-lab/evaluate` likewise write a platform-agent task for the back-translation / outline-expansion candidate. After the platform agent writes the expected candidate and manifest, run deterministic `style-eval` or provide an equivalent `style_eval_*.json` review before mounting.

`style-lab-mount` requires readiness evidence by default: `prompt.md`, a prompt detail length of 500-2500 Chinese-content characters, required style-prompt content blocks, `style_prompt.agent.json`, and at least one accepted `evaluation_results/*/style_eval_*.json`. Formal Skill hosts must not use `--allow-unreviewed`; complete style readiness instead.

Mounted style skills are stored in the creative project under `style/mounted/{style_id}/` with `style/active_style_skill.json` as the active pointer. During generation, the mounted `prompt.md` is the highest-priority expression constraint, while canon, character facts, plot causality, safety boundaries, and explicit user constraints still take precedence.

`references/punctuation-standard.md` is the baseline expression hygiene layer below every Style Skill. A style prompt may specify punctuation rhythm, density, and pauses, but it should not cause English punctuation to leak into Chinese prose, replace `……` with `...`, or use nonstandard dashes unless the project records a deliberate exception.

## Generic Agent Run

Use `agent-run` only for legacy/debug local provider regression. For formal JSON, patch, style, asset, scene, canon, or committee work, use the specialized platform-task commands.

```powershell
python -m literary_engineering_studio_engine agent-run "<work-dir>" `
  --agent-id scene-reviewer `
  --task review-scene `
  --system-text "You are a literary engineering review agent." `
  --user-text "Review scene_0001 for character logic, canon risk, and revision actions."
```

It writes:

- `agents/runs/{run_id}/input.prompt.json`
- `agents/runs/{run_id}/raw_output.md`
- `agents/runs/{run_id}/parsed_output.json`
- `agents/runs/{run_id}/validation_report.md`

For an explicit real HTTP model endpoint:

```powershell
$env:DEEPSEEK_API_KEY = "your-api-key"
python -m literary_engineering_studio_engine config-show
python -m literary_engineering_studio_engine agent-run "<work-dir>" --agent-id canon-reviewer --task review-canon --system "<system-prompt.md>" --user "<user-prompt.md>"
```

Agent output is not canon. Even parsed JSON should be treated as evidence until a schema gate, review command, and platform-agent review accept it as candidate material; human approval is still required before promotion when the change affects canon, character state, plot direction, style policy, release status, or user-facing decisions.

## Creative Director

The tool-layer platform agent is the preferred Creative Director. Use normal Codex/Claude conversation, file inspection, edits, and subagents first.

Use the local `director-chat` command only for legacy regression, local demos, or when the user explicitly asks to exercise the built-in director implementation:

```powershell
python -m literary_engineering_studio_engine director-chat "<work-dir>" --message "把项目推进成双主角悬疑长篇，先补强角色压力和世界观限制"
python -m literary_engineering_studio_engine director-status "<work-dir>"
```

The local director chooses the internal workflow, runs schema-gated specialist agents, and writes:

- `director/runs/{run_id}/director_decision.json`
- `director/runs/{run_id}/director_report.md`
- `director/runs/{run_id}/agent_decision/`
- `director/runs/{run_id}/tool_loop.json`
- `director/runs/{run_id}/agent_observe_{step}/`
- optional delegated `workflow/runs/{run_id}-wf/`

`director_tools` is a bounded local tool loop: the local director decides the next safe tool, executes it, observes artifacts/status, and then decides whether another tool is needed.

For the project-type skill route, prefer the platform agent's own planning and subagents. If the local director is exercised, treat its `director_decision.json`, `tool_loop.json`, delegated agent runs, and report as evidence for the platform agent to review, not as the final project decision.

## Agent Asset Workshop

Write platform-agent tasks for project-seeding candidates:

```powershell
python -m literary_engineering_studio_engine agent-create-character "<work-dir>" --brief "谨慎的调查者" --target-id linzhou
python -m literary_engineering_studio_engine agent-create-world "<work-dir>" --brief "档案被垄断的城市"
python -m literary_engineering_studio_engine agent-create-outline "<work-dir>" --brief "调查旧档案的三幕结构"
python -m literary_engineering_studio_engine list-candidate-assets "<work-dir>"
```

Write platform-agent review tasks and then promote only after the expected candidate/review artifacts exist and approval has been recorded:

```powershell
python -m literary_engineering_studio_engine review-candidate-asset "<work-dir>" "<candidate-id-or-path>"
python -m literary_engineering_studio_engine promote-character-candidate "<work-dir>" "<candidate-id-or-path>" --approval-run-id "<candidate-id>"
```

Candidate assets are written under `characters/candidates/`, `canon/candidates/`, and `plot/candidates/`; they are not canon until promoted. The platform agent should inspect every generated candidate and review report before asking for approval or using it in later planning. Formal Skill hosts must not use `--allow-unapproved`.

Validate or repair an agent run:

```powershell
python -m literary_engineering_studio_engine agent-validate "<work-dir>" --run-id "<run-id>" --schema generic_agent_output.v1
python -m literary_engineering_studio_engine agent-repair "<work-dir>" --run-id "<run-id>" --schema scene_review.v1
```

Run specialized agent review commands:

```powershell
python -m literary_engineering_studio_engine agent-review-scene "<work-dir>" --scene scenes/scene_0001.yaml
python -m literary_engineering_studio_engine agent-canon-review "<work-dir>"
python -m literary_engineering_studio_engine agent-plan-patch "<work-dir>" --target characters/linzhou.yaml --source drafts/scenes/scene_0001.md
python -m literary_engineering_studio_engine agent-style-prompt "<work-dir>\\style\\demo-author"
python -m literary_engineering_studio_engine agent-committee "<work-dir>" --subject scene-0001 --source drafts/scenes/scene_0001.md
```

## Canon / Plot Lint

```powershell
python -m literary_engineering_studio_engine canon-lint "<work-dir>"
```

Use this before chapter readiness checks, exports, publication, or large-scale expansion. It writes:

- `reviews/canon_lint.md`
- `reviews/canon_lint.json`

The lint only reports project-state issues. It does not edit canon, approve candidates, or modify drafts.

## Scene Loop

The command chain below develops one scene. For a chapter, volume, or longform batch, enumerate all target `scenes/*.yaml` first and repeat the chain for each scene. A completed loop for one scene is never evidence that the remaining scenes have passed RP, branch, composition, review, promotion, or state-patch gates.

```powershell
python -m literary_engineering_studio_engine context "<work-dir>" --scene scenes/scene_0001.yaml --rebuild-index
python -m literary_engineering_studio_engine simulate-scene "<work-dir>" --scene scenes/scene_0001.yaml --agent
python -m literary_engineering_studio_engine branch-simulate "<work-dir>" --scene scenes/scene_0001.yaml --agent
# Platform agent fills branches/scene_0001/branch_selection.md with decision: selected and selected_branch.
python -m literary_engineering_studio_engine compose-scene "<work-dir>" --scene scenes/scene_0001.yaml --agent-tasks
python -m literary_engineering_studio_engine route-audit "<work-dir>" --route scene-development
python -m literary_engineering_studio_engine generate-scene "<work-dir>" --scene scenes/scene_0001.yaml --rebuild-context
python -m literary_engineering_studio_engine agent-review-scene "<work-dir>" --scene scenes/scene_0001.yaml --draft drafts/candidates/scene_0001-platform-agent.md
# Platform agent reads reviews/agent/scene_0001_scene_review.agent_tasks.md, then writes scene_review.v1 JSON/Markdown with source_paths citing that exact candidate and conclusion=pass.
python -m literary_engineering_studio_engine promote-candidate "<work-dir>" --scene scenes/scene_0001.yaml
python -m literary_engineering_studio_engine review-scene "<work-dir>" drafts/scenes/scene_0001.md
python -m literary_engineering_studio_engine revise-scene "<work-dir>" --scene scenes/scene_0001.yaml
python -m literary_engineering_studio_engine state-evolve "<work-dir>" --scene scenes/scene_0001.yaml
```

`branch-simulate` writes scored branch candidates under `branches/{scene_id}/`:

- `branch_simulation.md`
- `branch_manifest.json`
- `branch_selection.md`

Branches are not canon. The recommended branch is only a scoring hint; the platform agent should evaluate it against story direction, canon, character pressure, and user intent before recording the actual human or tool-layer decision in `branch_selection.md`.

Use `branch-simulate --agent` / `--agent-tasks` to write `branch_manifest.agent_tasks.md`. This sidecar tells the platform agent how to review branch scores and choose or revise a branch without polluting `branch_manifest.json`.

`compose-scene` turns the formally selected branch into a creation packet under `drafts/compositions/{scene_id}_composition.md` and `.json`, including scene beats, subtext, dialogue intents, sensory palette, prose seed, revision targets, and writeback candidates. Formal composition now requires `branch_manifest.json` plus `branch_selection.md` with `decision: selected` and `selected_branch`; missing branch simulation is blocked instead of silently using fallback. The recommended branch is never used by default; formal Skill hosts must not use `--allow-recommended-branch` or `--allow-missing-branch`.

Use `compose-scene --agent-tasks` to write `drafts/compositions/{scene_id}_composition.agent_tasks.md`. Keep `[AGENT_TASK: ...]` out of the composition Markdown because it may be read into `generate-scene` prompt packs.

Each sidecar in this chain must be completed with the adjacent `.agent_completion.json` marker before the next formal step. `branch-simulate --agent` checks the RP marker, `compose-scene --agent-tasks` checks the branch marker, and `generate-scene` checks RP, branch, and composition markers. `workflow-state` and `agent-task-status` expose any missing marker.

When character `background_story` is present, scene and branch work should convert it into choices, hesitation, avoidance, misreadings, tone, and relationship pressure. Do not turn it into an explanatory background paragraph unless the selected scene explicitly reveals the past.

`generate-scene` writes a prompt manifest and `drafts/candidates/{scene_id}-platform-agent.agent_tasks.md`. It does not call a local provider, does not overwrite `drafts/scenes/`, and does not write canon. Formal generation requires a `compose-scene` composition packet with `selection_source: selection`, `ready_for_generation=true`, and `formal_cli_provenance.created_by=compose-scene`; missing, hand-written, unselected, fallback, or recommended-only composition packets are blocked. Formal Skill hosts must not use `--allow-missing-composition` or `--allow-unselected-composition`. The main platform agent reads the prompt manifest, writes the expected candidate Markdown and manifest JSON, then reviews the exact candidate before promotion.

Formal generation also requires `memory/context_packets/{scene_id}.trace.json`. `generate-scene` rebuilds context if the trace is missing; `build_scene_prompt_pack` blocks if a supplied context packet lacks its trace. The platform agent must read the trace before drafting to verify that the context actually loaded the intended project, scene, canon, characters, mounted style, word budget, and retrieval sources.

The prompt manifest includes `generation_standards.style`, `generation_standards.word_budget`, `generation_standards.review_notes`, `generation_standards.anti_evasion`, and `generation_standards.hard_constraints`. These are generation-time contracts, not merely review checklists: before drafting, the platform agent should translate the mounted Style Skill / style profile into concrete scene tactics, apply any `pass_with_notes` revision actions, honor longform budget load, follow the anti-evasion protocol, and apply the hard-constraint priority order. The candidate manifest must record `generated_by=platform-agent`, `prompt_manifest`, `style_generation_standard_applied`, `hard_constraints_applied`, `anti_evasion_protocol_applied`, `word_budget_standard_applied`, and `pass_with_notes_actions_applied`. Do not output that plan in the candidate; use it to reduce review failures before they happen.

Generated candidates and promoted drafts should pass the standard Chinese punctuation gate. `review-scene` reports punctuation issues under `Punctuation Standard Test`; fix those before chapter readiness or export unless the user explicitly approves a recorded exception. Before `promote-candidate`, run `agent-review-scene --draft <candidate>` or perform an equivalent platform Agent review of the exact candidate, and ensure the resulting `scene_review.v1` JSON cites that candidate in `source_paths` with `conclusion=pass`. Do not skip `agent-review-scene` because it sounds model-backed: it writes a task sidecar and expected report paths; the supervising platform agent performs the review and writes the JSON/Markdown. When a Style Skill is mounted, formal platform scene review must also write `style_adherence` into `reviews/agent/{scene_id}_scene_review.json`, and `route-audit --route scene-development` treats missing or failed style adherence as blocking.

After a batch, run `route-audit --route scene-development`. The audit is the per-scene ledger: each scene must show context packet, context trace, roleplay, branch manifest, formal branch selection, ready composition, prose candidate, exact-candidate review, Style Lint clean/notes-only, promotion manifest, promoted draft, static `review-scene` clean pass, and state patch. If a revision candidate is used, it must also show a clean anti-evasion revision manifest. Missing rows are unfinished work, not optional warnings. For 100000+ word or multi-volume targets, the same audit also checks that `word-budget` was run before bulk scene work.

Generated candidates and promoted drafts must pass the Style Lint Gate. `review-scene` reports mechanical “不是……而是……” frames, dash variants such as “不是……——是……”, same-function evasive contrast frames such as “并不是……只是……” and “看似……其实……”, organ-rotation, generic placeholders, simile dependency, abstract summary language, explanatory psychology labels, template transitions, scenery syncing, symmetric slogan rhythm, omniscient theme explanation, and aphoristic endings under `AI Trace Reduction Test`. Mechanical and evasive contrast frames are core banned frames and must not be judged as reasonable rhetoric; they are always blocking. Other medium-or-higher AI trace findings are also blocking; low findings stay notes-only and require platform Agent review or a retention reason. `promote-candidate`, `route-audit`, and chapter/export readiness rerun Style Lint Gate on the candidate or cleaned body, so a clean-looking `scene_review.v1` cannot hide unresolved blocking lint. Do not run regex cleanup that deletes negation or rewrites contrast frames; the platform agent must decide sentence by sentence how to preserve meaning while removing model habits.

`revise-scene` reads the scene file, draft, context packet, context trace, AgentReview notes, mounted style, canon, punctuation standard, Style Lint evidence, anti-evasion protocol, and word budget, then writes a revision prompt manifest plus `drafts/revisions/{scene_id}_revision.agent_tasks.md`. The main platform agent fills the expected revision candidate and revision report; subagents may only provide issue lists and evidence. This is the formal path for resolving `pass_with_notes`, warnings, local prose defects, or under-length scene bodies without silently overwriting `drafts/scenes/{scene_id}.md`. The revision report must include an anti-evasion table and burden-of-proof section whenever a transition/contrast risk is touched; weak explanations such as “增强节奏” or “体现复杂心理” do not pass.

`promote-candidate` turns a selected, reviewed model candidate into `drafts/scenes/{scene_id}.md` and writes `drafts/promotions/{scene_id}_promotion.md` / `.json`. By default it blocks missing, stale, or unresolved candidate reviews. It does not confirm canon and does not write characters. Formal Skill hosts must not use `--allow-unreviewed` or `--allow-review-notes`; if these appear in a manifest, route-audit blocks formal readiness.

If any official command blocks a scene, chapter, or export because review gates are missing, do not bypass the gate with a custom script, debug flag, or unreview instruction and label the result final. Run `agent-task-status`, `route-audit`, `agent-review-scene`, `revise-scene`, or `chapter-workspace` as appropriate.

The prompt manifest records system/user messages and source files for the platform agent. It must remain pure audit data and must not contain `[AGENT_TASK: ...]`.

Review conclusions:

- `pass`: ready for chapter workspace.
- `pass_with_notes`: usable only after local notes are applied by the writing agent and the result is re-reviewed to clean `pass`.
- `revise_required`: not exportable.
- `reject`: not exportable.

`state-evolve` builds a reviewable character-state patch under `characters/state_patches/` from a scene draft, generated candidate, or composition artifact. If the source is a composition packet, it must have passed the same formal branch-selection gate as `generate-scene`; unselected or recommended-only composition packets are blocked. It does not modify `characters/*.yaml`; the platform agent must inspect the patch for hidden-background causality, canon risk, and unintended relationship drift. Major character state changes still require human confirmation before any later writeback.

Use `state-evolve --agent-tasks` to write `characters/state_patches/{scene_id}_state_patch.agent_tasks.md` for platform-agent review while keeping the JSON patch clean.

After a workflow run is approved, apply a character state patch with:

```powershell
python -m literary_engineering_studio_engine state-apply "<work-dir>" --patch characters/state_patches/scene_0001_state_patch.json --approval-run-id "<approved-run-id>"
```

`state-apply` writes only approved character state, arc, relationship, and memory reference fields. It does not write canon.

## Chapter Workspace

```powershell
python -m literary_engineering_studio_engine chapter-workspace "<work-dir>" --chapter-id chapter_0001 --build-missing --review-drafts
```

Scene states:

- `ready`: draft exists, context/RP/branch/selection/composition flow gates are complete, static review is clean `pass`, platform Agent scene review JSON exists, schema passes, the review cites the current draft path, conclusion is clean `pass`, no warnings/revision/style notes remain, and mounted Style Skill adherence is clean `pass`.
- `needs_flow_gates`: prose may exist, but context, roleplay reading receipt, branch manifest, formal `branch_selection.md`, or ready composition is missing.
- `needs_revision`: `pass_with_notes`, warnings, revision actions, style notes, or style adherence deviations still need `revise-scene` and re-review before readiness/export.
- `needs_draft`: no usable body.
- `needs_review`: body exists but review missing.
- `needs_agent_review`: static review exists but formal platform Agent scene review JSON is missing.
- `blocked`: review failed.

## Longform Audit

```powershell
python -m literary_engineering_studio_engine longform-audit "<work-dir>" --target-length 100000
```

Audits:

- scene schema completeness;
- character inventory gaps;
- draft and review readiness;
- context packet presence;
- chapter workspace presence;
- foreshadowing debt;
- lightweight graph structure.

## Export Package

```powershell
python -m literary_engineering_studio_engine export-package "<work-dir>" --chapter-id chapter_0001
python -m literary_engineering_studio_engine export-package "<work-dir>" --chapter-id chapter_0001 --formats md,docx
python -m literary_engineering_studio_engine export-docx "<work-dir>\\exports\\chapter_0001\\chapter_0001_novel.md" --kind novel
```

Outputs:

- novel chapter draft;
- screenplay working draft;
- long-video prompt pack;
- optional editable DOCX files for the same artifacts;
- optional DOCX layout plan JSON files;
- optional DOCX inspection JSON files;
- `export_manifest.json`.

By default only `ready` scenes are exported, and the command blocks when any chapter scene is non-ready or the chapter workspace is stale. Formal Skill hosts must not use `--include-blocked`.

Final exported prose and screenplay files are cleaned delivery artifacts. They should not expose scene workbench sections, scene IDs such as `scene_0001`, chapter IDs such as `chapter_0001`, scene file paths, context packet paths, writeback candidates, canon notes, prompt manifests, review status, workflow IDs, or “导出规则” text. Audit and provenance remain in `export_manifest.json`, release manifests, review files, and workflow logs.

DOCX delivery follows the migrated Office file-handling subset: editable WordprocessingML, structured headings, real lists, native simple tables, Chinese-capable fonts, companion layout plan, and companion inspection report. It does not include academic PPT workflows, tracked changes, comments, citations, formula layout, or full OOXML schema validation.

`draft_chars` in chapter, longform, and export manifests means cleaned deliverable body characters with whitespace removed. Do not treat raw draft file length as prose length.

## Publish Chapter

```powershell
python -m literary_engineering_studio_engine publish-chapter "<work-dir>" --chapter-id chapter_0001 --approval-run-id "<approved-run-id>"
python -m literary_engineering_studio_engine publish-chapter "<work-dir>" --chapter-id chapter_0001 --approval-run-id "<approved-run-id>" --export-formats md,docx
```

Default gates:

- `canon-lint` has no blocking issues.
- `chapter-workspace` has no non-ready scenes.
- `export-package` exports every scene without skips.
- `workflow/approvals/index.jsonl` contains an `approve` record.

Outputs:

- `releases/{chapter_id}/{release_id}/publish_manifest.json`
- `releases/{chapter_id}/{release_id}/release_notes.md`
- `releases/{chapter_id}/{release_id}/rollback.md`
- optional published `.docx` delivery files when `--export-formats md,docx` is used
- `releases/{chapter_id}/latest.json`

Formal Skill hosts must not use `--allow-unapproved`; publish only after approval.

## Workflow Runner

```powershell
python -m literary_engineering_studio_engine run-workflow "<work-dir>" --mode full-cycle --scene scenes/scene_0001.yaml --chapter-id chapter_0001
```

Modes:

- `scene-loop`: index, context, roleplay simulation, branch simulation, scene composition, optional generation, optional promotion, draft workspace, review, character state patch.
- `chapter-publish`: chapter workspace, longform audit, export package.
- `full-cycle`: scene loop followed by chapter publish.
- `project-seeding`: world, character, and outline candidate creation plus review.
- `character-lab`: character, background-story, and relationship candidates plus review.
- `worldbuilding-lab`: world, location, and organization candidates plus review.
- `outline-lab`: outline, chapter-plan, and scene-list candidates plus review.

Outputs:

- `workflow/runs/{run_id}/workflow_state.json`
- `workflow/runs/{run_id}/workflow_log.md`
- `workflow/runs/index.jsonl`

The runner preserves existing drafts by default. Use `--overwrite-draft` only when the user wants to regenerate the draft workspace.

Add candidate generation to the scene loop:

```powershell
python -m literary_engineering_studio_engine run-workflow "<work-dir>" --mode scene-loop --generate-candidate
```

This writes `candidate_task`, `expected_candidate`, `expected_candidate_manifest`, and `prompt_manifest` in workflow state. The platform agent must write the expected candidate before promotion can proceed.

Add schema-gated agent review nodes:

```powershell
python -m literary_engineering_studio_engine run-workflow "<work-dir>" --mode scene-loop --agent-review
```

Generate platform-agent task sidecars throughout the scene loop:

```powershell
python -m literary_engineering_studio_engine run-workflow "<work-dir>" --mode scene-loop --agent-tasks --generate-candidate
```

This records `simulation_agent_tasks`, `branch_agent_tasks`, `scene_composition_agent_tasks`, `candidate_task`, and `state_patch_agent_tasks` in `workflow_state.json` when the corresponding artifacts exist. In formal `agent_tasks` mode, the workflow runner behaves as a handoff state machine: after it writes a sidecar, it blocks at that handoff until the platform agent reads the sidecar, writes the expected artifacts, and creates the adjacent `.agent_completion.json` marker. It should not continue to branch, compose, generate, review, promote, or state-evolve merely because the preceding CLI command wrote a Markdown/JSON artifact.

Promote the generated or latest candidate into the review lane:

```powershell
python -m literary_engineering_studio_engine run-workflow "<work-dir>" --mode scene-loop --generate-candidate --promote-candidate
```

If the platform-agent candidate has not been written yet, promotion is deferred instead of invoking a local provider. If the candidate exists but has not passed a candidate-specific platform scene review, promotion is blocked.

Stable run id and linked retry:

```powershell
python -m literary_engineering_studio_engine run-workflow "<work-dir>" --mode scene-loop --run-id scene-0001-pass-1
python -m literary_engineering_studio_engine run-workflow "<work-dir>" --mode scene-loop --run-id scene-0001-pass-2 --resume-run-id scene-0001-pass-1
```

## Approval Summary

```powershell
python -m literary_engineering_studio_engine approval-summary "<work-dir>"
```

Reads `workflow/approvals/index.jsonl` and writes `workflow/approvals/approval_summary.md`. `revise` and `reject` decisions create follow-up tasks under `workflow/tasks/`.

## LangGraph Adapter

Install optional orchestration dependencies before using LangGraph:

```powershell
python -m pip install fastapi uvicorn pydantic langgraph
```

For the development repo:

```powershell
$env:PYTHONPATH = "<repo-root>\\src"
python -m literary_engineering_studio_engine run-langgraph "<work-dir>" --scene scenes/scene_0001.yaml --chapter-id chapter_0001 --thread-id demo-thread-001
```

For an installed skill copy:

```powershell
$env:PYTHONPATH = "<skill-root>\\scripts"
python -m literary_engineering_studio_engine run-langgraph "<work-dir>" --scene scenes/scene_0001.yaml --chapter-id chapter_0001 --thread-id demo-thread-001
```

The LangGraph adapter wraps the same file-backed runner. Current graph:

- `scene-loop`
- `chapter-publish`

Status is merged by severity: `failed > blocked > completed_with_skips > completed`.

## Dify / HTTP Backend

Install optional runtime packages, then start the local API:

```powershell
python -m pip install fastapi uvicorn pydantic langgraph
$env:PYTHONPATH = "<skill-root>\\scripts"
python -m literary_engineering_studio_engine serve-api --host 127.0.0.1 --port 8765 --allowed-root "<parent-workspace>" --api-token "your-token"
```

Primary endpoints:

- `GET /health`
- `GET /`
- `GET /config`
- `POST /config`
- `POST /assistant/chat`
- `POST /director/chat`
- `POST /workflow/run`
- `GET /workflow/runs/{run_id}?project_root=<work-dir>`
- `GET /workflow/artifact?project_root=<work-dir>&path=<relative-artifact-path>`
- `POST /workflow/approve`

For a platform-agent or creative-director UX, call `/director/chat` with `project_root`, `message`, `provider`, `auto_execute`, and optional `agent_tasks`. The director can run delegated workflows and, when `agent_tasks=true`, those workflows write platform-agent task sidecars for later Codex/Claude inspection.

For specialist/debug workflows, call `/workflow/run` directly. Its request body accepts `agent_review=true` for schema-gated model reviews and `agent_tasks=true` for sidecar task directives. Display the returned log or state, collect `approve / revise / reject` with Human Input, then call `/workflow/approve`. Do not let Dify edit canon files directly.

The same service hosts a local front-end console at:

```text
http://127.0.0.1:8765/
```

Use it for global config, explicit local API key setup, project summary, workflow execution, and creative-director chat.

If `--api-token` is enabled, send either:

```text
Authorization: Bearer your-token
```

or:

```text
X-LEW-API-Token: your-token
```

## Dify Workflow DSL Starter

Generate an import-safe workflow YAML starter:

```powershell
$env:PYTHONPATH = "<skill-root>\\scripts"
python -m literary_engineering_studio_engine dify-dsl --api-base "http://127.0.0.1:8765"
```

This writes:

```text
docs/integrations/dify/literary-workbench-reviewer.workflow.yml
```

If generating inside an installed skill directory is not desired, pass `--out` to write into a project folder:

```powershell
python -m literary_engineering_studio_engine dify-dsl --out "<work-dir>\\prompts\\dify\\literary-workbench-reviewer.workflow.yml"
```

The DSL starter uses the workbench HTTP contract:

- `POST /director/chat`
- `GET /workflow/artifact`

The default DSL declares version `0.6.0` and intentionally keeps only Start, HTTP Request, and End nodes because Dify Human Input / classifier node fields vary by version. It exposes `auto_execute` and `agent_tasks` as Start variables; set `agent_tasks=true` when you want delegated workflows to produce platform-agent sidecars. If your Dify instance requires a newer declared DSL version, add:

```powershell
python -m literary_engineering_studio_engine dify-dsl --dsl-version "0.7.0"
```

After import, add Human Input and a final HTTP Request node in Dify UI to call `POST /workflow/approve`.

If the target Dify version rejects an internal node field, first import a reduced Start -> Run workflow -> End version, then rebuild the remaining HTTP Request and Human Input nodes in Dify UI.

## Orchestration Blueprint

```powershell
python -m literary_engineering_studio_engine orchestration-plan "<work-dir>"
```

Use this before implementing LangGraph nodes, Dify workflows, or knowledge-base adapters.
