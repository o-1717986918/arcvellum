# Studio Implementation Route

## Delivered Roadmap: ArcVellum v0.5.1-v0.7

The post-v0.5 roadmap in `docs/roadmap/arcvellum-v0.5.1-v0.7-reader-advisor-observatory-plan.md` is implemented in ArcVellum v0.7.0. Its release evidence is recorded in `docs/releases/v0.7.0-verification.md`.

It is grounded in the current v0.5.0 implementation and covers only observed gaps: desktop directory-dialog reliability, hidden process execution, lazy provider loading, single-document startup, a default project library, a complete Reader Manifest and long-form reader, modular advisor personas, deterministic proactive advisor messages, a real narrative projection behind the StoryTrace, controlled visual assets, repository identity migration, and release hardening.

Delivery followed the intended dependency order: desktop stability and application paths, Reader Manifest and incremental reading, advisor personas and deterministic proactive messages, then Narrative Projection and controlled visual assets.

## Delivered Roadmap: ArcVellum v0.4-v0.5

The post-v0.3 product plan in `docs/roadmap/arcvellum-v0.4-v0.5-product-experience-and-autonomy-plan.md` is implemented in the v0.5.0 release candidate. The detailed verification record is `docs/releases/v0.5.0-verification.md`.

It delivered the product baseline in this order:

1. complete Prompt Asset transport and explicit task execution contracts;
2. migrate the client to Vue 3, TypeScript, and Vite without replacing the FastAPI local-service boundary;
3. make native directory selection, application bootstrap, model warmup, and user-facing language reliable;
4. add a visible startup scene, application information, signed updates, and diagnostic export;
5. replace the report-like advisor with a streaming, natural, read-only floating advisor and safe action proposals;
6. add a deterministic AutopilotController and a no-filesystem CreativeSteward for delegated decisions;
7. validate deterministic three-chapter whole-book delivery while retaining clean-VM and long-running live-project evidence as `v1.0.0` entry criteria.

The working English product name is `ArcVellum`, subject to trademark and naming review. Preserve the existing Tauri identifier and application-data migration identity during any display-name change.

## v0.3.0 Productization Complete

- Versioned Runner, Model Connection, task execution, output, human-gate and normalized-event contracts.
- SQLite WAL durable jobs, leases, route locks, idempotency, restart recovery and bounded event replay.
- Bundled OpenCode 1.18.3 with checksum verification, isolated worker/advisor profiles and real inference probe.
- Exact high-risk Prompt assets plus deterministic prompt regression evaluation.
- Read-only advisor snapshots, cited answers and persistent sessions.
- Writeback diff preview, approval/rejection, stale-target detection, rollback, stop, retry and runtime switching.
- Tauri 2 Windows client with native folder dialogs, per-launch local authentication, frozen Python sidecar and crash-safe parent monitoring.
- Reproducible NSIS build containing the embedded engine and OpenCode license notices.

The remaining items below are post-v0.3 enhancements, not blockers for the current single-user desktop release.

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

## v0.2.1 Client Trust Pass

- Unified editorial workspace palette and local Lucide control/navigation icons.
- Editorial illustrations moved from tiny icon roles into project, task, archive, style, prose, and delivery contexts.
- Responsive mobile layout revalidated at 390px without horizontal overflow.
- Delivery center for formal route gates, export history, and restricted artifact download.
- Function-completeness review recorded in `docs/architecture/studio-function-completeness-review-v0.2.1.md`.

## Next 1: Contract and Client Baseline

1. Separate `AgentRunner` from `ModelConnection` in contracts, readiness, configuration, and frontend language.
2. Replace inferred human gates and execution behavior with explicit task execution, role, capability, output-kind, and writeback policies.
3. Add native folder selection for desktop packaging while retaining text-path fallback in the browser build.
4. Add project rename, archive, duplicate, backup, and safe relocation flows.
5. Add richer editable forms for project brief, target scale, volume structure, key characters, and world constraints.
6. Show all pending human gates in one inbox with choice history and impact previews.
7. Add export history, output preview, and one-click open/download actions.

## Next 2: Application Runtime Foundation

1. Add one application lifecycle manager for Studio API, Runner sidecars, health checks, restart, shutdown, and migrations.
2. Replace daemon-thread authority with durable jobs, leases, heartbeats, idempotency, and restart recovery.
3. Add a persistent normalized run-event store with cursor replay, redaction, bounded retention, and SSE projection.
4. Give formal projects, task sandboxes, Agent sessions, and run workspaces distinct identities and lifecycle rules.
5. Validate the foundation with a fake Runner before embedding OpenCode or starting Tauri packaging.

## Next 3: Worker Durability and Writeback

1. Build the formal Worker supervisor on the shared lifecycle and durable-job foundation.
2. Add stop, retry, resume, Agent Runner switch, and interrupted-job recovery.
3. Add per-project task locks, idempotency keys, and concurrency limits.
4. Normalize all selected Agent Runner streams into task, tool, file, validation, warning, and completion events.
5. Add writeback diff preview and explicit confirmation for high-impact changes.

## Next 4: Literary Project Experience

1. Upgrade the prose reader with chapters, reading position, search, typography controls, and export linkage.
2. Add character relationship views, canon change timelines, scene bridges, rhythm curves, and promise/payoff ledgers.
3. Add project-wide search, filters, deduplication, and “影响创作的关键点” summaries.
4. Present word-budget debt and expansion candidates as user decisions instead of raw audit rows.
5. Add visual comparisons for branch candidates and revisions.

## Next 5: Agent Runner Ecosystem

1. Probe Agent Runner versions, authentication state, supported flags, model selection, minimal inference, and write permissions.
2. Generate commands from detected CLI capabilities rather than fixed assumptions.
3. Add ACP/OpenHands behind the same adapter contract.
4. Add adapter conformance tests with fake executables.
5. Add a bundled OpenCode Runner without allowing it to own workflow state or formal writeback.
6. Manage provider/model connections through the selected Runner while keeping direct model APIs out of the literary engine.

## Approved Productization Round: Embedded OpenCode and Desktop Client

The next approved product direction replaces the ordinary-user dependency on a separately installed Agent platform with a bundled OpenCode Agent Runner while preserving the embedded literary engine as the only workflow and writeback authority.

The detailed contracts, application-lifecycle foundation, persistent event design, security boundaries, prompt-engineering work, read-only advisor design, durable Worker requirements, Tauri packaging route, and release acceptance criteria are defined in `docs/roadmap/embedded-opencode-desktop-productization-plan.md`.

Key boundary: `AgentRunner` is responsible for planning and execution; `ModelConnection` identifies the model service it uses; the literary engine remains responsible for workflow policy and formal writeback. Studio may manage OpenCode provider connections through a safe local application flow, but it must not restore the old literary-engine direct-provider implementation or store credentials in work projects and ordinary Studio configuration.

## Acceptance Target

The next stable milestone is reached when a user can create a project, state a high-level direction, start and observe a formal Agent task, make every required human decision, inspect the exact writeback, read the resulting work, and export a clean manuscript without leaving the frontend or editing project files directly.
