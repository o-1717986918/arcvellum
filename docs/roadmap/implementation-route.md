# Agent Runtime Implementation Route

## Baseline Delivered In This Initialization

- Separate Studio repository and package.
- Credential-free configuration and core discovery.
- Core CLI bridge and strict command grammar.
- Task-contract validation.
- Isolated workspace staging and expected-output-only writeback.
- Host Agent, Claude Code, and Codex CLI adapters.
- Persistent Worker jobs and SSE job status.
- Reused core dashboard, library, activity, human-choice, and style services.
- Copied and adapted frontend with an Agent Worker control panel.
- Architecture review and tests.

## Phase 1: Contract Hardening

Make a small compatibility release in the core repository:

1. Add `--json` output to formal CLI commands.
2. Add structured `command_argv` beside the legacy command string.
3. Add `execution_policy` with `agent`, `deterministic`, `human`, and `mixed` values.
4. Add explicit `human_gate` and `agent_role` fields.
5. Split expected outputs into preflight, Agent-authored, and core-completion groups.
6. Add resource origin for required reading.
7. Publish a `core-capabilities` command with versions and supported task schemas.

Studio should retain compatibility with `agent-task/v1` while preferring the new fields.

## Phase 2: Worker Durability

1. Replace in-process threads with a recoverable local queue and process supervisor.
2. Stream runtime stdout incrementally into normalized events.
3. Add stop, retry, resume, and runtime-switch operations.
4. Record process IDs and recover interrupted jobs after Studio restarts.
5. Add per-project concurrency limits and a global prose-generation limit.
6. Add idempotency keys so a repeated click cannot execute a task twice.
7. Lock one formal task while a Worker owns it.

## Phase 3: Runtime Quality

1. Probe runtime version, login state, supported flags, and write permissions.
2. Generate commands by detected CLI version instead of fixed assumptions.
3. Parse Claude and Codex JSON streams into a common event schema.
4. Distinguish reasoning, tool calls, file writes, warnings, cost metadata when available, and final status.
5. Add OpenHands/ACP as the first protocol-based adapter.
6. Add adapter conformance tests using fake executables.

The project should not add direct model APIs during this phase.

## Phase 4: Human Control Plane

1. Show exactly which task is active and which files it may read/write.
2. Present human gates as explicit choice cards before execution.
3. Support branch choice, style mount, canon approval, revision direction, expansion direction, and release approval.
4. Allow the user to stop or change runtime without changing the core task.
5. Show the core gate failure as a repair task, not as raw JSON.

## Phase 5: Full Frontend Execution Experience

1. Replace job-status polling fallback with normalized SSE events from the process supervisor.
2. Add a live Agent timeline: task received, files read, artifacts changed, core validation, completion.
3. Show workspace diff and expected-output previews before writeback.
4. Add project-level queues for multiple scenes while preserving per-scene route order.
5. Keep completed prose, character files, world rules, scene plans, branches, and review evidence in the existing project library.

## Phase 6: Packaging And Distribution

1. Publish the Studio as a separate public GitHub repository.
2. Add Windows-first installation checks for Claude Code and Codex CLI.
3. Provide an optional desktop shell only after the browser app is stable.
4. Keep the Skill/competition package free of Studio runtime dependencies.
5. Version the core/Studio compatibility matrix and provide migration diagnostics.

## Acceptance Criteria

The route is complete when a user can select a literature project and runtime, start one formal task, observe it live, pause at human decisions, inspect the exact file diff, allow writeback, and see the old core accept or reject the result without any model key being stored by Studio.

