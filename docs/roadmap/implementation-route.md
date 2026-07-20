# Studio Implementation Route

## v0.2 Baseline

- Standalone repository and Python package.
- Embedded literary workflow engine and package resources.
- Project create/open/switch and user-direction persistence.
- Credential-free Studio configuration.
- Strict embedded-engine bridge with provider routes disabled.
- Task-contract validation and expected-output-only writeback.
- Host Agent, Claude Code, and Codex CLI adapters.
- Persistent Worker job records and SSE status.
- Project dashboard, completed prose reader, library, human choices, and style management.
- Chinese, user-facing project center and Agent workplace.

## Next 1: Full Client Operations

1. Add native folder selection for desktop packaging while retaining text-path fallback in the browser build.
2. Add project rename, archive, duplicate, backup, and safe relocation flows.
3. Add richer editable forms for project brief, target scale, volume structure, key characters, and world constraints.
4. Show all pending human gates in one inbox with choice history and impact previews.
5. Add export history, output preview, and one-click open/download actions.

## Next 2: Worker Durability

1. Replace in-process threads with a recoverable local queue and process supervisor.
2. Add stop, retry, resume, runtime switch, and interrupted-job recovery.
3. Add per-project task locks, idempotency keys, and concurrency limits.
4. Normalize Claude and Codex event streams into task, tool, file, validation, warning, and completion events.
5. Add writeback diff preview and explicit confirmation for high-impact changes.

## Next 3: Literary Project Experience

1. Upgrade the prose reader with chapters, reading position, search, typography controls, and export linkage.
2. Add character relationship views, canon change timelines, scene bridges, rhythm curves, and promise/payoff ledgers.
3. Add project-wide search, filters, deduplication, and “影响创作的关键点” summaries.
4. Present word-budget debt and expansion candidates as user decisions instead of raw audit rows.
5. Add visual comparisons for branch candidates and revisions.

## Next 4: Runtime Ecosystem

1. Probe runtime versions, login state, supported flags, and write permissions.
2. Generate commands from detected CLI capabilities rather than fixed assumptions.
3. Add ACP/OpenHands behind the same adapter contract.
4. Add adapter conformance tests with fake executables.
5. Keep direct model APIs outside the product unless a future, separately approved product line explicitly introduces them.

## Acceptance Target

The next stable milestone is reached when a user can create a project, state a high-level direction, start and observe a formal Agent task, make every required human decision, inspect the exact writeback, read the resulting work, and export a clean manuscript without leaving the frontend or editing project files directly.
