# Lean Kernel v2 K2 Transaction Service Change Packet

Status: implemented

## Objective

Implement one recoverable scene application transaction over the K1 domain contracts, using explicit ports and the existing SQLite unit-of-work policy. Prove the lifecycle with deterministic fake adapters before any real Worker is connected.

## Inputs and outputs

- Input: `PreparedScene` from a brief provider, one `CreativeResult` from a creative runtime, an optional semantic `ReviewResult`, and a project base revision.
- Output: a durable `SceneTransaction`, deterministic verification, an atomic `SceneCommitPlan`, and an idempotent `SceneCommitReceipt`.

## Allowed dependencies

- K1 transaction contracts and pure functions.
- Studio application protocols.
- Existing `SqliteUnitOfWork`.
- Python standard library and SQLite.

## Production semantics

- No existing route is changed or activated.
- The new SQLite table is additive and unused by strict-v1.
- Runtime and project writes remain behind ports.
- A failed stage is persisted as `blocked` with `blocked_from`; `resume` restores the nearest safe stage.
- A completed creative result or verification report is reused rather than recomputed.
- Project commit adapters must be idempotent by transaction ID.

## Explicit exclusions

- No Pi Worker or model calls.
- No Autopilot, CLI, API, SSE, or frontend wiring.
- No strict-v1 route edits.
- No second workflow or task registry.

## Rollback point

Remove the K2 application and repository modules and the additive scene-transaction schema fragment. Existing route data and behavior remain unchanged.

## Verification

- Low-risk happy path commits with one creative invocation and no critic invocation.
- Standard risk requires a critic pass.
- High risk requires a decision trace and Steward approval.
- Runtime failure persists a resumable state.
- Repeated create/verify/commit calls reuse successful work.
- SQLite round-trip preserves nested domain objects and optimistic versions.
- Injected commit failure retries through an idempotent port without duplicate project mutation.
