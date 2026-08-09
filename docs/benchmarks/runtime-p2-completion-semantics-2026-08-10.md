# ArcVellum P2 Completion Semantics Evidence

- Date: `2026-08-10`
- Scope: deterministic contract and repair-loop evidence; no live model was invoked.
- Baseline: `TASK_CONTEXT v0.1`, at most two same-session repair turns, no task-local no-progress identity.
- Candidate: `TASK_CONTEXT v0.2`, explicit completion contract, task-local progress digest.

## Contract Evidence

`TASK_CONTEXT v0.2` preserves every v0.1 field and declares v0.1 compatibility. It adds:

- the resolved execution-profile projection;
- Agent-owned outputs separated from CLI-protected and Studio-managed completion evidence;
- exact deterministic pass checks, including existing clean review conclusions;
- an explicit stop condition that rejects chat-only completion.

The Worker Program presents required reading, allowed outputs, semantic evidence, pass conditions, and stop conditions before the detailed context and literary constraints.

## Repair Evidence

The deterministic `test_repair_no_progress` fixture uses an unchanged output set, unchanged preflight issue identity, unchanged context-access summary, and a configured budget of two repairs.

| policy | repair prompts sent before stop | terminal evidence |
|---|---:|---|
| previous bounded loop | 2 maximum | final `preflight_failed` after budget exhaustion |
| P2 progress-aware loop | 1 | `repair.no_progress` plus stable progress digest |

This is a structural upper-bound reduction, not a claim about average live-model quality. Live token and tool-call effects remain for later controlled canaries; P2 proves that an identical repair cannot be sent a second time.

## Validation

- Focused completion, sandbox, preflight, repair, Worker, and role tests: `83 passed`.
- Architecture audit: `ok=true`, no new budget or dependency violations.
- Full suite: `955 passed`, `1 skipped` by design.
