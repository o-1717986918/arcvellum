# Project Agent D2-D3 Architecture Review

> Date: 2026-09-13
>
> Decision: D2 complete; D3 conditionally passed for D4 read-only backend work

## Implemented evidence

- Added a transport-neutral Python contract and a dedicated subprocess runtime.
- Added a Pi Agent Core project-agent mode with one proxied read tool.
- Added a versioned JSONL request/result protocol with frame and result limits.
- Verified a scripted model tool roundtrip in process.
- Verified one real DeepSeek/Pi provider roundtrip: one tool call, two provider turns, natural Chinese answer, exit code 0.
- Verified malformed frames, unknown tools, timeout, cancellation, and process cleanup.
- Kept task, repair, and role-conversation execution paths intact.

## Gate review

| Gate | Result | Evidence or remaining condition |
|---|---|---|
| No second workflow state machine | Pass | Bridge owns one disposable turn and no literary state. |
| No duplicated domain behavior | Pass | Python dispatcher delegates to injected read models; Node has no project implementation. |
| Advisor and Worker semantics remain distinct | Pass | Existing Advisor and formal Worker files are unchanged; project-agent has a new mode and runtime. |
| Tool surface remains narrow | Pass | D2 exposes only `project_overview`. |
| Literary gates cannot be bypassed | Pass for D2 | The bridge is read-only and has no file or shell tool. |
| Cancellation and process cleanup | Pass | Pending calls reject; Python sends cancel, waits one second, then terminates and reaps. |
| Event volume is bounded | Pass after correction | Character deltas are coalesced before JSONL transport. |
| Existing runtime regression | Pass | Pi Worker: 97 tests. Advisor/persistence/container characterization: 18 tests. |
| Durable conversation reuse | Conditional | Existing Advisor tables persist sessions, but repository methods only accept `user/advisor`. D4 must add a backward-compatible generic session API or additive `session_kind`; no second database. |
| Durable event cursor | Conditional | D4 must store turn events in existing JobStore/run events. Bridge events alone remain transient. |
| Idempotent write calls | Deferred | D2 has no writes. D5 must use existing mutation receipts and domain revisions. |

## Cost and performance observation

The real smoke test completed in about three seconds and made one read-tool call across two provider turns. Prompt/tool token usage is now projected as content-free `model.usage` events. D4 must persist and aggregate those events before a product latency or token budget is claimed.

The first bridge implementation emitted one JSONL frame per provider text fragment. That was rejected during D3. The corrected implementation coalesces text at 96 characters and reasoning at 160 characters, flushing at message/tool/turn boundaries.

## Architecture decision

D4 may begin with these restrictions:

1. Add generic session persistence by extending the existing session repository; keep Advisor compatibility methods.
2. Persist every turn through existing jobs and run events. SSE is a projection over durable events.
3. Keep the visible tool set at `project_overview`, `project_search`, and `creation_observe`.
4. Do not add write tools, approval state, a second event store, WebSocket, or production UI mutations in the same batch.
5. Keep real-provider smoke tests opt-in and content-free.

## Stop conditions

Stop D4 and retain the current Advisor with action cards if generic session migration breaks Advisor compatibility, durable cursor replay cannot be made deterministic, or read-tool selection remains unreliable after tool names and schemas are tightened.

