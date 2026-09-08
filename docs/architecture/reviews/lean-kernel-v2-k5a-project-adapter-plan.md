# K5A: Project Adapter And Atomic Scene Commit

## Purpose

Connect the lean scene transaction to a real ArcVellum work project without
changing the strict-v1 route or the Autopilot default.

## Input Contract

- One formal `scenes/<scene_id>.yaml` file.
- Existing character, Canon, rhythm, word-budget, chapter-obligation, and
  active-style files when present.
- One `SceneCommitPlan` produced by the K2 application service.

## Output Contract

- A bounded `SceneBrief` whose `source_refs` all resolve inside the project.
- A source digest used as the optimistic base revision.
- One atomic commit containing:
  - `drafts/scenes/<scene_id>.md`;
  - `workflow/scene_deltas/<scene_id>.json`;
  - `workflow/scene_commits/<scene_id>.json`.
- Repeating the same transaction returns the original receipt without another
  write. A different transaction or changed source revision fails closed.

## Dependency Boundary

- Studio infrastructure may depend on Engine scene facts, style snapshots,
  risk projection, and atomic I/O.
- The Engine remains unaware of Studio persistence and runtimes.
- Semantic changes remain committed events; this batch does not mutate the
  legacy character or Canon files and does not create compatibility sidecars.

## Rollback

No existing route calls this adapter. Removing the new adapter restores the
previous production behavior. `strict-v1` remains the only default route.

## Verification

- Brief projection uses only project-local sources and carries style/rhythm/
  word-budget/chapter obligations.
- Risk aliases preserve the existing compact/standard/deep calculation.
- Atomic commit, idempotent replay, stale revision, and existing-draft conflict
  are covered with temporary-project tests.
- Draft mode avoids a standard-risk critic call; high-risk protection remains.

