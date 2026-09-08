# Lean Kernel v2 K4 Chapter Checkpoint Change Packet

Status: implemented

## Objective

Move cross-scene quality control to one chapter checkpoint and represent longform planning as one validated bundle over existing structured facts. Avoid adding chapter task graphs or per-ledger Agent lifecycles.

## Reused capabilities

- `ChapterPlanningFacts` remains the scene inventory, chapter length, obligation, and risk projection.
- `analyze_narrative_rhythm_sequence` remains the deterministic rhythm analyzer.
- Committed K2 `SceneTransaction` values provide prose counts and `SceneDelta` changes.

## Inputs and outputs

- `ProjectPlanBundle`: existing chapter facts plus references to the story spine, word budget, inventory, and obligation source.
- `ChapterSceneOutcome`: one committed scene's body count, rhythm, handoff input, style score, and semantic delta.
- `ChapterCheckpointEvaluation`: status, count reconciliation, issues, and one compact revision plan.

## Severity policy

- `pass`: no issue found.
- `needs-attention`: warnings may be deferred or folded into later chapter work.
- `revision-required`: missing scenes, invalid planning facts, missing rhythm contracts, or severe chapter-length deficits.

Individual scene soft-length misses do not block the chapter when the chapter total remains healthy. Promise, handoff, continuity-evidence, repeated rhythm, and style-drift findings are chapter-level warnings unless evidence proves a hard contradiction.

## Explicit exclusions

- No new planner framework or DAG.
- No project file reads or writes.
- No automatic prose rewrite.
- No changes to strict-v1 chapter routes.
- No model call; a later adapter may attach one chapter critic without changing this contract.

## Verification

- A three-scene chapter can pass with one aggregated checkpoint.
- Missing scenes and severe word deficits require revision.
- Rhythm, handoff, promise, continuity evidence, and style drift produce localized issues.
- Repeated evaluation is deterministic and does not mutate transactions.
