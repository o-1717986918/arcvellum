# Lean Kernel v2 K6: compatibility and controlled adoption

## Scope

Finish the migration surface around the lean scene kernel without claiming a
literary-quality result that has not been measured. K6 makes kernel selection,
project migration, rollback, diagnostics, and retirement policy explicit. It
does not remove `strict-v1`, add another workflow registry, or bypass the blind
literary A/B gate.

## Inputs

- The K5D structural A/B result and its `ready_for_default` decision.
- Existing Autopilot delegation-policy persistence.
- Existing strict-v1 routes and lean-v2 scene transaction service.
- Existing Studio application container and scene transaction repository.

## Outputs

- A machine-readable compatibility manifest owned by the Studio package.
- A pure selector that distinguishes new-project recommendation from legacy
  fallback and records the reason for the result.
- Explicit migration and rollback through the Autopilot policy service/API.
- Scene transaction `status`, `prepare`, `run`, and `resume` CLI diagnostics
  that reuse the production application service.
- A compact frontend selector marked experimental while literary evidence is
  pending.
- A zero-consumer retirement inventory with a two-release hold. No historical
  route is deleted in this batch.

## Contracts

### Kernel selection

- Existing projects without a persisted policy resolve to `strict-v1`.
- Explicit user selection is preserved after normalization and restart.
- New projects use the manifest recommendation. The recommendation remains
  `strict-v1` until K5D reports `ready_for_default=true`.
- Scene execution mode remains `standard` unless the user changes it.

### Migration

- Migration changes only the persisted delegation policy.
- A running Autopilot run must be paused before migration.
- Migrating to `lean-v2` validates runtime availability before the next run;
  rollback to `strict-v1` remains available without rewriting project files.
- Every migration response includes previous kernel, selected kernel, source,
  compatibility status, and rollback target.

### Diagnostics

- CLI commands use the same repository, project adapter, verifier, writer, and
  runtime as Autopilot.
- `status` is read-only.
- `prepare` creates at most one recoverable transaction for a scene.
- `run` and `resume` advance one existing transaction through the official
  coordinator and never manufacture strict-v1 sidecars.

## Allowed dependencies

- Compatibility code may depend on immutable package resources and pure policy
  normalization.
- Application services may depend on persistence and runtime ports.
- API and CLI may depend on application services.
- Frontend may depend only on the API read/write contract.

The Engine remains independent of Studio, SQLite, HTTP, and frontend code.

## Rollback

- Set a project's policy back to `strict-v1`.
- Revert the packaged manifest recommendation.
- Remove the K6 API/CLI presentation without changing strict-v1 project files.

## Verification

- Selector tests cover pending, passing, malformed, new-project, and legacy
  policy cases.
- Policy migration tests prove persistence and rollback.
- CLI tests cover status and transaction preparation with fake runtime ports;
  one existing fake-runtime scene E2E remains green.
- API and frontend tests prove the selector survives a save/reload cycle.
- Final K0-K6 verification includes targeted Python tests, frontend typecheck,
  the lean fake E2E, strict-v1 characterization, and one full regression run.

## Retirement hold

K6 records compatibility consumers and release milestones. Deletion is allowed
only after two released versions have observed zero production consumers and a
separate change packet names every removed import, command, fixture, and user
migration. This batch performs no compatibility deletion.
