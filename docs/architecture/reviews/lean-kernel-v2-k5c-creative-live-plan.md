# Lean Kernel v2 K5C: Creative Live integration

## Scope

Expose the existing lean scene transaction through ArcVellum's current
Creative Live read model and SSE channel. Do not introduce another event bus,
frontend store, or workflow status vocabulary.

## Change packet

1. Add a project-scoped transaction query to the SQLite repository.
2. Project transaction objects into compact, user-facing summaries. The
   projection may expose literary status, risk, word count, review outcome,
   revision count, and whether input is required; it must not expose absolute
   paths or raw protocol payloads.
3. Hydrate every Creative Live snapshot from SQLite so restart and reconnect
   preserve the current scene state.
4. Publish candidate, revision, review, and commit events through the existing
   project live channel. Candidate prose remains ephemeral; committed prose is
   hydrated from the formal project file.
5. Extend the existing Creative Live Pinia projection and dock with one compact
   scene-transaction pulse. No separate page is added.

## Invariants

- `strict-v1` events and snapshots keep their current behavior.
- A transaction event changes only the matching transaction summary.
- Candidate and committed revisions retain one artifact identity per scene
  transaction.
- API snapshots remain valid when no lean transaction exists.
- Event payloads contain no provider secret, absolute path, or complete
  `SceneBrief`.

## Verification

- Repository query and snapshot restart recovery.
- SSE transaction event and artifact identity continuity.
- Frontend reducer status transition and compact component rendering.
- Existing Creative Live API and projection tests remain green.
