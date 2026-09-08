# Lean Kernel v2 K5 A/B gate

## Structural result

The reproducible report is
`docs/benchmarks/lean-kernel-v2-structural-ab-2026-09-08.json`.

- Standard scene model calls: 8 to 2, a 75% reduction.
- Recoverable workflow states: 31 to 5, an 83.87% reduction.
- Project Agent task files: 8 to 0 for the scene transaction path.
- The structural gate passes.

These values describe the ideal route contracts. They do not claim observed
provider latency, token savings, or literary quality.

## Live literary gate

On 2026-09-08 the configured Pi Worker was probed through the same
`RoleConversationGateway` used by scene transactions. The provider returned
HTTP 402 `Insufficient Balance` before producing model output. No secret,
prompt body, or endpoint was retained in this report.

Consequences:

- same-model strict-v1 versus lean-v2 prose could not be generated;
- blind literary scoring is unavailable;
- `ready_for_default` remains false;
- strict-v1 remains the default until a later successful evidence run.

This is an external provider gate, not a transaction, persistence, SSE, or
project-writeback failure.
