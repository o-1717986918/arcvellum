# AO-3B Context Ledger Runtime Architecture Review

## Scope

This review covers only the runtime and durable metadata path for Context Ledger:

- source selection shared by prompt and Agent sandbox;
- exact post-materialization ledger generation;
- metadata-only SQLite persistence;
- Agent session binding;
- retry and same-run rematerialization identity;
- API Worker and Autopilot event integration.

It does not activate adaptive plans, schedule Planner work, create Mutation Receipts, or alter
formal Engine gates.

## Decisions

1. `runtime/context_selection.py` is the single source-selection contract. The prompt never names
   a source or reference that was not actually copied into the Agent workspace.
2. `runtime/context_materialization.py` materializes prompt, task context, capability/resource
   controls and ledger as one operation. This prevents three independently drifting projections.
3. `assembled_sha256` remains the exact hash of `AGENT_TASK.md`. Ledger identity additionally
   binds every selected metadata entry, so unchanged prompt wording cannot hide changed source
   content.
4. The ledger records source/reference paths, existing output baselines, CLI-protected outputs,
   project direction and machine task controls. Missing requested inputs remain explicit excluded
   entries.
5. SQLite schema 13 stores only paths, purpose, truth partition, sizes, hashes, inclusion and
   truncation flags, and a redacted 320-character preview. Full project source text remains in the
   isolated run workspace.
6. `sandbox.context_ready` is the persistence boundary. A pre-command temporary workspace does not
   claim to be the context a model actually received.
7. Provider session rows retain the exact Context Ledger ID and digest across later lifecycle
   events. Ledger records do not become gate evidence and cannot satisfy Canon, promotion or
   completion requirements.

## Failure Properties

- Missing source: omitted from prompt, absent from workspace, recorded as excluded.
- Core command changes context: workspace is rematerialized and receives a new ledger digest and
  identity before the runner starts.
- Repeated persistence: idempotent for the same project and digest.
- Cross-project replay: rejected.
- Ledger path outside run root: rejected before reading.
- Credential-like content: redacted before file and database preview persistence.
- Legacy database: migration backup is created before schema 12 to 13 upgrade.

## Architecture Result

- Runtime materialization, observability contracts, persistence and session projection remain
  separate modules.
- Engine does not import Studio.
- Context Ledger adds no task lifecycle, scheduler or formal writeback path.
- Architecture Audit: 36 existing file debts, 225 existing function debts, 0 cycles; no new debt.

## Verification

- AO-3B focused suites cover actual source selection, prompt hash, missing input, machine controls,
  same-run rematerialization, redaction, SQLite idempotency, migration and session binding.
- Worker, recovery, sandbox, API event projection and Autopilot regression suites pass.
- Full Python suite: 611 passed, 1 skipped.
- `python -m compileall -q src tests`, Architecture Audit and `git diff --check` pass.

## Remaining AO-3 Work

- AO-3C: machine-owned Mutation Receipt and typed plan events.
- AO-3D: isolated Planner/Reviewer shadow service, fallback evidence and independent exit review.
