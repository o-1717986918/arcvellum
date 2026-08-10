# ReasoningBudget P6 Contract Canary

- Date: `2026-08-10`
- Mode: deterministic fixture and contract verification
- Live model invoked: `false`
- Product default changed: `false`

## Verified

- Studio projects a complete reasoning budget only when the execution-profile canary selectors match.
- Pi Worker accepts initial/maximum level, per-request target, total target, provider-request cap, and escalation cap.
- Pi Worker stops at a turn boundary rather than interrupting an in-flight response.
- At a budget boundary, complete locally valid outputs continue to Studio preflight; incomplete outputs stop with a non-retryable no-progress classification.
- Worker receipts contain requested budget, provider support, actual reported tokens or `null`, reasoning characters, provider requests, escalations, and stop reason.
- Receipt identity is compared with the Studio contract. Missing or mismatched receipts are not presented as applied provider control.
- Mechanical repair issues retain the current reasoning level; repair context carries the policy decision without replaying the full initial prompt.
- OpenCode receives no reasoning-budget arguments and remains supported through the legacy profile path.

## Current Support Result

- Pi Worker adapter contract: supported.
- Provider support before a live request: unknown.
- Exact per-request token support: provider-dependent and reported as `supported`, `partial`, `unsupported`, or `unknown` by the Worker receipt.
- Local configured Pi Worker: disabled; entrypoint, model, and auth path are absent.

## Verification

- Pi Worker: `19` tests passed; TypeScript build passed; built CLI returned `arcvellum-pi-worker 0.1.0`.
- Studio focused suite: `39` tests passed.
- Studio full regression (2026-08-11): `1001` tests passed; `1` skipped.
- Architecture audit: passed with no new file/function debt and no import cycle.

## Not Yet Proven

- Same-model structured/review token reduction.
- Live Provider acceptance of the requested per-request target.
- Live latency, cost, preflight pass rate, repair count, or literary blind-review quality.
- Semantic escalation across a Studio authoritative preflight retry.

P6 therefore remains a canary implementation, not a product-default promotion.
