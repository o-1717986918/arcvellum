# W6-5B Active Plan Production Closure

## Scope

This batch activates the existing AO-4 scene strategy through the existing
Engine task lifecycle. It does not add a scheduler, execution bundle,
concurrency, chapter rolling horizon, or a second task/review/promotion/state
pipeline.

## Invariants

1. A shadow revision remains non-executable even when its independent review
   passes.
2. Assisted authorization is an explicit, durable, machine-audited transition.
3. Activation verifies immutable audit artifacts, the SQLite revision, the
   authorization, the active projection, and the current project fingerprint.
4. `AgentWorker` receives an already compiled and verified plan. It does not
   interpret, compile, repair, or approve creative plans.
5. The existing Engine issues and completes every formal task.
6. A bound task is frozen into a run-scoped snapshot before deterministic
   command execution or Agent context materialization.
7. Recovery, preflight, approval, and writeback reload the same snapshot and
   verify its digest. They never reload a mutable project task package.
8. Context Ledger and Mutation Receipt identities include the same
   plan/revision/node binding.
9. Fixed and shadow modes retain the existing route behavior.
10. Missing or rejected plans fall back to the fixed route with an observable
    reason. Tampered active projections never execute.

## Module Changes

### Orchestration

- `orchestration/codec.py`
  - Strictly reconstructs immutable orchestration contracts from verified JSON.
  - Rejects unknown fields and invalid primitive types.
- `orchestration/active_plan.py`
  - Loads and validates the active projection and its durable revision.
  - Returns one immutable `ActiveScenePlan` value for Worker binding.
- `orchestration/persistence.py`
  - Adds explicit assisted authorization before activation.
  - Keeps shadow review artifacts immutable.

### Persistence

- `persistence/creative_plans.py`
  - Records assisted authorization in revision control metadata.
  - Does not alter the immutable plan/review audit files or revision digest.
- `persistence/context_ledgers.py`
  - Persists plan revision and node identity.

### Runtime

- `runtime/task_snapshot.py`
  - Writes and verifies the bound task JSON and task Markdown inside the run.
- `runtime/sandbox.py`
  - Creates the snapshot before workspace materialization.
  - Exposes the snapshot, not the mutable project task, to the Agent.
- `runtime/worker.py`
  - Loads an active plan only in assisted/adaptive modes.
  - Binds the task after formal `task-open` and before sandbox staging.
  - Emits explicit bound/fallback observability events.
- `runtime/worker_writeback.py`
  - Reloads the immutable run snapshot for approval and writeback.

## Verification

1. Shadow revision cannot activate without assisted authorization.
2. Authorization requires a passing independent review and verified artifacts.
3. Active loader rejects stale fingerprint, mismatched SQLite state, altered
   projection, altered audit files, and shadow-only revisions.
4. Fixed and shadow modes do not bind active plans.
5. Assisted mode binds RP depth, branch count, prose strategy, and revision
   policy to the existing scene tasks.
6. Project task mutation after staging cannot change recovery or writeback.
7. Task snapshot mutation is detected.
8. Context Ledger and Mutation Receipt carry identical plan/revision/node
   identity.
9. One real scene follows the existing route through prose, review, revision,
   promotion, and state evolution, with fixed fallback unchanged.

## Rollback

The production rollout remains config-gated:

```json
{
  "orchestration": {
    "enabled": false,
    "mode": "fixed"
  }
}
```

Disabling orchestration makes Worker use the unchanged fixed route. Active plan
artifacts and authorization evidence remain auditable but inert.
