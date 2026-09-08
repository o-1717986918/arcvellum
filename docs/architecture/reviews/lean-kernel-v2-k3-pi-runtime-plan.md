# Lean Kernel v2 K3 Pi Runtime Change Packet

Status: implemented

## Objective

Connect the K2 scene transaction to the embedded Pi Worker through one bounded creative call and one conditional critic call. Keep prompts compact, cache structured answers by transaction ID, and avoid extending the legacy file-task protocol.

## Architecture decision

The existing Pi tool-free conversation transport already provides model selection, authentication, streaming events, timeout, cancellation, and bounded reasoning. K3 reuses that transport. It does not add a Worker mode, tool set, subprocess implementation, or task lifecycle.

The adapter may inline only the `SceneBrief` plus small project-local `source_refs`. Paths are resolved below the configured project root and bounded by the recipe limit. K4/K5 may replace this with a persistent chapter context provider without changing the application port.

## Input and output

- Creative input: `SceneBrief` and bounded source evidence.
- Creative output: JSON object containing prose, a brief decision summary, `SceneDelta`, optional decision trace, and escalation reasons.
- Critic output: `pass`, `revise`, or `escalate`, with concise evidence and revision instructions.
- Machine metadata, paths, hashes, receipts, and task lifecycle fields are rejected from model output and remain Studio-owned.

## Failure and retry policy

- Successful parsed output is atomically cached under the Studio transaction data root before returning.
- Repeated transaction calls reuse the cache and do not call the provider again.
- Invalid JSON or invalid contract fails before K2 verification and remains resumable.
- No legacy v2 Prompt fallback is used.

## Explicit exclusions

- No change to the existing Pi file-task tools or dirty Worker worktree files.
- No default Autopilot switch.
- No chapter-level persistent session yet.
- No direct project write from the model.

## Verification

- Prompt recipe limits and absence of Skill/CLI lifecycle text.
- Creative and review response parsing.
- source-ref path confinement and evidence budget.
- transaction cache idempotency.
- K2 standard-risk lifecycle using the Pi adapter with a fake conversation transport.
- Optional real-provider smoke when the configured Pi model and credentials are available.
