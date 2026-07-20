# Phase 83: Sidecar State Machine And Word-Budget Chain

## Goal

Fix two failure modes seen in real Skill-host use:

- The host agent treated CLI outputs as completed work and skipped hidden or process-looking `.agent_tasks.md` sidecars.
- Longform `word_budget` existed as a planning artifact but did not reliably reach scene YAML, composition, generation, review, promotion, and export gates.

## Implemented Changes

- Added explicit `.agent_completion.json` markers for platform-agent task sidecars.
- Made `agent-task-status`, `route-audit`, and `workflow-state` surface pending sidecars, missing markers, and missing expected artifacts.
- Moved roleplay agent tasks out of `roleplay_simulation.md` into `roleplay_simulation.agent_tasks.md`.
- Added pre-step checks so `branch-simulate --agent` requires completed RP tasks, `compose-scene --agent-tasks` requires completed branch tasks, and `generate-scene` requires completed RP, branch, and composition tasks.
- Changed `run-workflow --agent-tasks` into a handoff state machine: when it writes a sidecar, it blocks until the platform agent completes the sidecar and marker before continuing.
- Added scene-level `word_count_target`, `word_count_min`, and `word_count_max` fields to `templates/scene.yaml`.
- Added `scene_word_budget_contract()` and generation/review helpers so context packets, composition packets, prompt manifests, generation sidecars, AgentReview, promotion, route-audit, chapter readiness, and export readiness use the same budget contract.
- Required longform generation to have completed word-budget sidecar work and a budget review before formal scene generation.
- Changed deterministic Style Lint injection to lint cleaned deliverable body text instead of the whole workbench Markdown.

## Result

The old path:

```text
word-budget generated -> word_budget.json sits in plot/word_budget -> writer never reads it
```

is replaced by:

```text
word-budget
-> platform agent completes word_budget.agent_tasks.md
-> scene.yaml carries chapter_id and optional word_count_target/min/max
-> context packet includes scene budget contract
-> compose-scene includes scene budget contract
-> generate-scene prompt manifest and sidecar include scene budget contract
-> AgentReview writes word_budget_adherence from cleaned body text
-> promote-candidate, route-audit, chapter-workspace, longform-audit, and export recheck the same contract
```

This does not guarantee that a model will always produce the requested length in one pass. It makes under-length output visible and blocking, and forces the platform agent to either expand scene inventory or revise the scene with a concrete target instead of silently compressing a longform project.

## Verification

```powershell
$env:PYTHONPATH = "src;tests"
python -m unittest discover -s tests -v
```

Result: 201 tests passed.
