# Workflow State Machine

This module defines the formal route state machine used by the project-type Skill. It exists to keep platform agents from treating CLI outputs, hand-written files, or partial sidecars as completed creative work.

## Core Principle

The CLI does not replace the platform agent. It chooses the next formal step, emits the task package, records the submitted artifacts, and validates deterministic gates. The platform agent still performs creative judgment, prose writing, review, branch decisions, style prompt writing, source extraction, and candidate acceptance.

For registered routes, use this loop:

```text
task-next -> task-open -> platform agent writes expected artifacts
-> task-submit -> task-complete -> workflow-state / workflow-validate
```

Do not skip from a produced filename to the next route step. A file can exist while its sidecar is still pending, its completion marker is missing, or an upstream state is blocked.

## Required Ledgers

- `workflow/route_state.json`: derived current state for routes and scenes.
- `workflow/tasks/*.task.json`: issued task records.
- `workflow/tasks/*.submission.json`: artifacts submitted by the platform agent.
- `*.agent_tasks.md`: executable task sidecars for the platform agent.
- `*.agent_completion.json`: completion markers created only after expected artifacts are inspected.
- `workflow/events/task_events.jsonl`: append-only event stream for issued, opened, submitted, blocked, and completed tasks.
- `workflow/workflow_contract.json` and `.md`: validation report produced by `workflow-validate`.

## Validation Commands

Use these dashboards together:

- `workflow-state <project> --route <route>` shows the current derived state.
- `agent-task-status <project>` shows pending sidecars and missing expected artifacts.
- `route-audit <project> --route <route>` checks route-specific gates.
- `workflow-validate <project> --route <route>` checks state schema, event schema, task schema, submitted artifacts, completion markers, and downstream-pass-before-upstream-pass inconsistencies.
- `workflow-dashboard <project>` writes a cross-route JSON/Markdown/HTML cockpit under `workflow/dashboard/` by aggregating overall state, pending sidecars, every formal route audit, and recent task events.

`workflow-validate` and `workflow-dashboard` are read-only. They must not advance the project. Treat any validation error or dashboard blocking row as a route repair task before bulk generation, promotion, export, or release.

## State Integrity Rules

- A downstream state must not be `pass` when an upstream non-order-neutral gate is still blocking.
- A route item must not be `ready` if any required step is not `pass`.
- Submitted tasks must record a submission JSON whose `task_id` matches the task file and whose artifacts exist.
- Completed tasks must record a completion JSON with `expected_artifacts_checked=true`.
- Event rows must use the workflow event schema and reference existing task ids.
- Manually created artifacts do not satisfy formal provenance unless a command was attempted, failed, and the workaround records explicit CLI-equivalent provenance for review.

## Longform Reader Gate

For longform-planning, the state machine must not stop after scene inventory. The formal route now includes:

```text
word-budget-file
-> budget-agent-task
-> budget-review
-> scene-inventory-agent-task
-> scene-inventory-review
-> chapter-obligation-agent-task
-> chapter-obligation-review
```

For scene-development on 100000+ Chinese-content-character or multi-volume projects, `reader-experience-contract` is an order-neutral gate after `scene-word-budget-contract` and before candidate generation. It passes only when the current chapter has a filled `plot/chapter_obligations/{chapter_id}.json` contract, the sidecar completion marker exists, and the current scene has complete reader-question/promise/payoff fields.

## Character Count Policy

Formal longform length targets are measured as cleaned Chinese-content characters: Han characters plus Chinese punctuation after workflow traces, scene ids, paths, Markdown scaffolding, review notes, state/writeback candidates, and `[AGENT_TASK: ...]` blocks are removed. Machine non-whitespace character counts are diagnostics only. If the two numbers disagree, the Chinese-content count controls pass/fail.

Mountable `style_prompt.md` files use the same Chinese-content idea for their 500-2500 detail-character quality gate, except code fences and Markdown scaffolding are stripped before counting.

## When To Run

Run `workflow-validate` when:

- an agent seems to have skipped RP, branch simulation, composition, AgentReview, promotion, or state evolution;
- a batch was generated concurrently and needs ledger verification;
- route state says `ready` but artifacts look suspicious;
- a release or export depends on many previous task submissions;
- you need a stable snapshot for a frontend dashboard or audit report.

Run `workflow-dashboard` when:

- the platform Agent needs one page showing which formal route is blocked next;
- the user wants to watch project maintenance progress without reading raw task files;
- a local frontend or external orchestrator needs a stable JSON source for route state, sidecar status, route audit summaries, and next actions.
