# Embedded OpenCode and Desktop Productization Plan

## 1. Plan Status

- Baseline: `literary-engineering-studio v0.2.1`
- Scope: the next productization round after the client trust pass
- Primary outcome: Studio becomes a self-contained literary engineering application with a bundled Agent Runner, a controlled Model Connection experience, a read-only project advisor, and a native desktop client.
- Architecture review input: AstrBot confirms that model completion, Agent execution, event dispatch, application lifecycle, and desktop packaging should be separate product subsystems. Studio adopts those boundaries without adopting a chatbot-first pipeline or weakening the literary workflow state machine.
- Agent Runner direction: OpenCode is the default embedded Agent Runner. Claude Code remains an optional compatibility Runner. Host Agent handoff remains an advanced interoperability path.
- Model Connection direction: this plan embeds an Agent Runner, not an LLM. A user must still connect a supported cloud provider, sign in through OAuth, or deliberately install a local model pack. Model connections are consumed through an Agent Runner and never restore direct model calls inside the literary engine.

## 2. Target User Experience

A non-developer should be able to:

1. Install Studio without separately installing Python, Node.js, OpenCode, Claude Code, or a browser extension.
2. Launch a native application and create or open a literary project through system file dialogs.
3. Complete a one-time model connection wizard in the frontend.
4. State only high-level creative directions and start the next formal workflow task.
5. Observe Agent progress as readable task, tool, file, validation, warning, and completion events.
6. Pause at branch, style, canon, revision, scale, and release decisions.
7. Preview formal writeback differences before high-impact changes are imported.
8. Ask a read-only project advisor about characters, canon, scenes, branches, reviews, budgets, and workflow state.
9. Read completed prose and export a clean manuscript without editing project files manually.

The product may be free of development-environment configuration. It cannot truthfully be free of model-source configuration unless a later product line bundles a local model or operates a hosted model service.

## 3. Non-Goals

This round does not:

- restore the old direct HTTP model-provider layer inside the literary engine;
- build a new Agent loop from scratch;
- fork or embed the OpenCode user interface;
- allow OpenCode, Claude Code, or any other runtime to write directly into the formal project root;
- make a read-only advisor part of the formal creation route;
- bundle a large local LLM by default;
- introduce multi-user cloud collaboration, accounts, billing, or remote project storage;
- make Codex CLI a primary product dependency.

### 3.1 External architecture lessons adopted

- Separate single-model completion from Agent planning and execution.
- Normalize Runner events before projecting them to the client.
- Centralize process startup, readiness, restart, shutdown, migration, and updater behavior.
- Treat sandbox identity, execution session, persistent run workspace, and formal project as different resources.
- Generate ordinary settings from typed schemas while keeping secrets and destructive actions on dedicated flows.
- Keep desktop-shell orchestration separate from Python business logic.

These are architectural lessons, not a dependency decision. AstrBot and AstrBot Desktop are AGPL-3.0 projects; Studio must not copy or embed their implementation unless a separate license review explicitly approves that obligation. OpenCode remains the planned embeddable Runner because its licensing and headless runtime model better fit this product.

## 4. Architectural Constitution

### 4.1 Authority boundaries

The embedded literary engine remains the only authority for:

- route and workflow-state derivation;
- task package issuance and completion;
- prompt assets and output contracts;
- deterministic lint, schemas, provenance, review, promotion, canon, state, export, and release gates;
- formal project writeback acceptance.

The Agent Runner is only an executor. It may read a staged task workspace and write declared `expected_outputs`. It may not advance workflow state, import files, relax a gate, or modify the formal project directly.

### 4.2 Target process model

```text
Native Studio Client
  -> application lifecycle manager
     -> Studio application service
        -> embedded literary engine
        -> durable worker supervisor
        -> persistent run event store
        -> task sandbox / Agent session / run workspace
        -> Agent Runner registry
           -> bundled OpenCode Runner
           -> optional Claude Code Runner
           -> advanced Host Agent handoff
        -> Model Connection registry
           -> user-selected cloud or local model
        -> writeback diff and formal project gate
```

The four execution resources are intentionally different:

- `FormalProject` is the authoritative literary project and is never mounted as a writable Agent workspace.
- `TaskSandbox` is the capability and filesystem boundary for one formal task.
- `AgentSession` is a Runner-owned conversation or execution session that may be stopped and recreated.
- `RunWorkspace` contains staged sources, declared outputs, event records, and recovery metadata for one run.

### 4.3 Required isolation

- OpenCode runs on `127.0.0.1` with a random port and per-launch random server password.
- OpenCode receives an application-owned config path and config directory. It must not silently inherit project or global Agent instructions.
- Default plugins, auto-sharing, unapproved network tools, LSP downloads, shell access, subagents, and external-directory access are disabled for formal work.
- The literary worker receives only the staged task workspace.
- The project advisor receives a read-only project snapshot or read-model index.
- The renderer never receives provider secrets, server passwords, or unrestricted filesystem paths.
- Studio imports only validated `expected_outputs`, with backups and optional human diff approval.

## 5. Product Contracts to Add

The product layer should move from implicit strings to versioned structured contracts.

### 5.1 Agent Runner capability contract

Add an `AgentRunnerCapabilities` record with at least:

- runtime id and version;
- availability and authentication state;
- supported execution modes;
- structured-output support;
- streaming-event support;
- model-selection support;
- read, edit, shell, subagent, web, and external-directory controls;
- stop, retry, and resume support;
- detected command flags and compatibility notes.

Availability must not mean only that `--version` succeeds. A runtime is ready only after executable, authentication, model selection, minimal inference, and sandbox write checks pass.

### 5.2 Model Connection contract

Add a `ModelConnection` record that remains separate from the Agent Runner:

- connection id, provider family, and connection method;
- authentication state without secret values;
- available and selected model ids;
- context window and structured/tool-call capabilities when known;
- cloud/local classification, endpoint health, and privacy label;
- last successful probe, failure category, and compatibility notes;
- the Agent Runner through which the connection is used.

The literary engine must never receive provider credentials or call this contract directly. OpenCode or another approved Runner owns provider protocol behavior; Studio owns safe configuration, status projection, and policy.

### 5.3 Task execution policy

Extend the Studio-consumed task contract with explicit fields:

- `execution_policy`;
- `agent_role`;
- `human_gate` and gate reasons;
- `runtime_capabilities_required`;
- `output_kinds` separating deterministic, Agent-authored, and completion artifacts;
- `writeback_policy` such as automatic, preview-required, or approval-required;
- `context_origin` distinguishing project and package resources.

Temporary compatibility parsing may derive these fields from existing tasks, but newly issued tasks should not rely on substring matching for human approval.

### 5.4 Persistent normalized runtime events

All Agent Runners should emit a shared event schema:

- `run.queued`, `run.started`, `run.stopped`, `run.failed`, `run.completed`;
- `agent.message.delta`, `agent.message.completed`;
- `tool.started`, `tool.completed`, `tool.denied`;
- `file.read`, `file.changed`, `file.rejected`;
- `validation.started`, `validation.blocked`, `validation.passed`;
- `human.required`;
- `usage.updated` with provider, model, tokens, duration, and cost when available.

Events are appended to an application-owned durable store before they are projected to SSE. Clients reconnect by cursor and can replay bounded history. Raw provider reasoning or hidden chain-of-thought must not be stored or exposed.

### 5.5 Application lifecycle contract

Define an application-owned lifecycle contract for Studio API, Agent Runner sidecars, and active jobs:

- process identity, version, start mode, and health state;
- readiness and liveness probes;
- startup timeout, graceful stop, force-stop fallback, and restart policy;
- crash detection, heartbeat, lease, and interrupted-run recovery;
- application data paths, schema version, migration status, and backup status;
- localhost endpoint and per-launch authentication metadata without exposing secrets to the renderer.

The Tauri shell will eventually own desktop process orchestration, but the same lifecycle contract must first work in the headless Python application service so packaging does not hide runtime defects.

## 6. Milestone A: Baseline and Contract Hardening

### Objective

Freeze a trustworthy pre-runtime baseline and make the engine/runtime boundary explicit before adding OpenCode.

### Work

1. Preserve the current `v0.2.1` frontend and delivery-center changes in a clean baseline commit.
2. Add runtime capability, execution policy, normalized event, provider metadata, and advisor citation schemas.
3. Replace human-gate substring detection with explicit fields while retaining a compatibility adapter for existing task packages.
4. Separate deterministic, Agent-authored, completion, and approval outputs in the consumer contract.
5. Change engine command transport from shell-like strings toward structured argv or a strict typed command object.
6. Add tests for capability negotiation, human-gate classification, path origin, output kind, and writeback policy.
7. Record an engine snapshot version and synchronization procedure so future engine imports are reviewed rather than copied ad hoc.

### Acceptance

- Existing 17 Studio tests remain green.
- Prompt Registry still validates all task IDs.
- Existing projects can open and issue tasks without migration.
- Every newly opened task exposes explicit execution, Agent role, human gate, output kind, and writeback policy information.

## 7. Milestone B: Application Lifecycle and Persistent Event Foundation

### Objective

Build the process, session, recovery, and observation foundation before adding a bundled Agent Runner. A successful subprocess invocation is not yet a reliable application runtime.

### Work

1. Add an `ApplicationLifecycleManager` responsible for Studio API and Agent Runner process registration, readiness, restart, shutdown, and cleanup.
2. Replace daemon-thread job authority with a durable local job store using SQLite WAL, leases, heartbeats, idempotency keys, and explicit terminal states.
3. Add an append-only `RunEventStore` with cursor-based replay, bounded retention, redaction, and SSE projections.
4. Define and persist `FormalProject`, `TaskSandbox`, `AgentSession`, and `RunWorkspace` identities instead of treating a run directory as all four concepts.
5. Recover queued, running, stopping, and interrupted jobs on application restart without marking them complete.
6. Add per-project and per-route locks before any Runner can execute a formal task.
7. Add application-data schema versions, forward migrations, pre-migration backups, and failed-migration recovery.
8. Expose one health projection for the frontend covering API, job supervisor, event store, Agent Runners, and Model Connections.
9. Add failure-injection tests for process crash, stale lease, duplicate submission, SSE reconnect, malformed event, and shutdown during writeback.

### Acceptance

- No daemon thread or in-memory queue is the sole authority for job state.
- Restarting Studio preserves queued and interrupted runs and never fabricates task completion.
- A client can reconnect with an event cursor and continue from the last acknowledged event.
- Stopping or restarting an Agent Runner cannot modify or invalidate the formal project.
- Schema migration is backed up, testable, and recoverable.
- The lifecycle foundation works headlessly before Tauri packaging begins.

## 8. Milestone C: Claude Code Compatibility Repair

### Objective

Keep Claude Code as a proven optional runtime while the OpenCode path is built.

### Work

1. Add `--verbose` when stream-json output requires it.
2. Probe CLI version, `auth status`, supported flags, selected model, and a minimal real inference separately.
3. Use safe mode and disable unrequested skills, plugins, hooks, MCP servers, auto-memory, and project instruction discovery where authentication remains available.
4. Make model selection explicit and display the actual provider/model returned by the runtime.
5. Replace blocking `subprocess.run` with a cancellable process and incremental stdout/stderr parsing.
6. Normalize Claude stream-json into the shared runtime event schema.
7. Add fake-executable conformance tests plus an opt-in live smoke test that never touches a formal project.

### Acceptance

- The adapter no longer reports ready when only `--version` works.
- A real probe can authenticate, infer, stream events, stop, and exit cleanly.
- The runtime cannot read or change anything outside the sandbox.
- User-global Claude skills and settings do not alter a formal Studio task.

## 9. Milestone D: Embedded OpenCode Runtime

### Objective

Make OpenCode the built-in default Agent Runner without giving it ownership of the literary workflow.

### Components

- `opencode_binary.py`: locate bundled target-specific binary and verify checksum/version.
- `opencode_server.py`: start, health-check, authenticate, stop, and recover the local server.
- `opencode_client.py`: minimal typed OpenAPI client for config, providers, auth, sessions, messages, abort, diffs, and SSE.
- `runtimes/opencode.py`: adapt formal task execution to the existing `AgentRuntime` contract.
- `opencode_profiles.py`: generate application-owned worker and advisor configurations.
- `runtime_events.py`: normalize OpenCode SSE events.

OpenCode is registered through the Agent Runner registry and supervised through the application lifecycle contract. Its provider and model choices are projected through `ModelConnection`; they are not folded into the Runner identity.

### Formal worker profile

Create a hidden `literary-worker` Agent with:

- read, list, glob, and grep allowed inside the sandbox;
- edit allowed only because the sandbox writeback checker remains authoritative;
- shell, task/subagent, web, skill loading, external directories, and sharing denied;
- no permission prompts that can deadlock a headless run;
- the CLI-issued `AGENT_TASK.md` as the execution program;
- no access to the formal project root.

### Execution sequence

1. Worker obtains and opens a formal task.
2. Studio stages the sandbox and records baseline hashes.
3. Studio creates an OpenCode session bound to the sandbox.
4. OpenCode executes with the literary worker profile.
5. Studio streams normalized events and supports abort.
6. Studio requests the OpenCode session diff and compares it with its own filesystem hashes.
7. Unexpected changes block the run.
8. Expected outputs enter diff preview or automatic import according to writeback policy.
9. Studio performs `task-submit`, `task-complete`, and `route-audit`.

### Acceptance

- A machine without a global OpenCode installation can execute a fixture task using the bundled binary.
- OpenCode cannot modify source artifacts or the formal project root.
- Stop, timeout, server crash, malformed output, permission denial, and missing output all produce recoverable states.
- OpenCode events appear incrementally rather than only after process exit.
- The bundled OpenCode version and MIT notice are present in release artifacts.

## 10. Milestone E: Model Connection and Agent Runner Settings

### Objective

Replace developer configuration with a safe, guided frontend experience.

### Frontend information architecture

Add a first-class `模型与 Agent` page containing:

- separate Agent Runner and Model Connection sections;
- OpenCode Runner version, process health, capabilities, and current session state;
- provider connection cards;
- OAuth or API-key connection flow;
- provider/model selector and actual active model;
- cloud versus local model explanation;
- connection test with readable failure recovery;
- context window, output budget, task cost ceiling, timeout, and retry policy;
- formal worker and read-only advisor capability summaries;
- advanced Claude Code compatibility settings;
- privacy and storage explanation.

Configuration forms should be generated from versioned schemas where practical. Secret fields, one-time OAuth flows, and destructive disconnect actions remain dedicated components rather than generic form fields.

### Credential rules

- Provider keys never enter a work project, task package, event log, screenshot, error message, or normal Studio config.
- The browser renderer posts a credential once over the local authenticated application channel and immediately clears the field.
- The backend hands the credential to OpenCode Auth or an OS credential store and returns only provider id, connection state, and masked metadata.
- OAuth is preferred when supported.
- Secrets are redacted from subprocess environments and crash logs.
- Application and OpenCode server passwords rotate per launch.

### First-run states

The app must distinguish:

- runtime unavailable;
- runtime ready but no provider connected;
- provider connected but no model selected;
- model selected but probe failed;
- fully ready;
- local model endpoint unreachable.

### Acceptance

- A user can connect, test, select, change, and disconnect a provider without editing files or opening a terminal.
- The user sees which model actually executed each task.
- Secret scanning finds no credentials in projects, config, logs, fixtures, screenshots, or Git history introduced by this feature.

## 11. Milestone F: Prompt Engineering Completion

### Objective

Move from registry coverage to measured prompt reliability across the embedded runtime.

### Prompt assets

Retain route-level wildcard assets as fallbacks. Add exact assets first for:

- roleplay execution;
- branch execution and branch selection;
- composition execution;
- longform word-budget review and scene inventory expansion;
- source-work extraction and extraction review;
- character/world asset creation and review;
- review committee execution;
- export approval and publication preparation.

Do not create 61 nearly identical files merely to remove wildcard matches. Exact assets are justified by creative risk, output complexity, or gate impact.

### Evaluation harness

Add fixture projects and reusable prompt cases that measure:

- expected-output and schema success;
- route-gate pass rate;
- exact-source review provenance;
- Canon and character consistency;
- word-budget, reader-experience, rhythm, bridge, and style adherence;
- workflow-trace leakage into reader-facing prose;
- forbidden shortcut and subagent violations;
- false pass and `pass_with_notes` handling;
- token use, latency, retries, and cost.

Use deterministic tests for contract structure and optional live evaluations for semantic quality. Store only prompts, outputs allowed for fixtures, scores, and public metadata, never hidden reasoning.

### Acceptance

- Every high-risk task resolves to an exact prompt asset.
- OpenCode and Claude wrappers produce semantically equivalent task instructions.
- Prompt changes require regression results, not only registry validation.
- At least one small end-to-end fixture reaches promotion and export through the embedded OpenCode path.

## 12. Milestone G: Read-Only Project Advisor

### Objective

Provide conversational project understanding without creating a second project director or a write path.

### Architecture

The advisor is separate from formal workflow tasks:

- it cannot call `task-next`, `task-submit`, `task-complete`, promotion, apply, or export operations;
- it receives a read-only snapshot or a curated project index;
- its OpenCode profile denies edit, shell, task/subagent, web, skills, and external directories;
- its answer schema separates project facts, cited evidence, inference, uncertainty, and suggested next formal action;
- conversations are application metadata and do not become Canon.
- advisor sessions use a separate read-only `AgentSession` and can never be resumed as formal Worker sessions.

### Retrieval

Start with deterministic project-library and file-index retrieval:

- project brief and target scale;
- Canon and forbidden changes;
- major and relevant minor characters;
- scene YAML and completed prose;
- branch selections and alternatives;
- AgentReview and route-audit evidence;
- word-budget debt, reader questions, promises/payoffs, rhythm, and bridges;
- style mounts and prompt quality reports.

Add vector retrieval only after deterministic search quality and stale-index behavior are measured. Every answer must cite artifact paths or user-facing artifact labels.

### Frontend

Add a persistent `项目顾问` panel with:

- suggested questions based on current project state;
- streaming answers;
- expandable evidence cards rather than raw JSON;
- clear labels for fact, inference, and missing evidence;
- no edit, apply, or "let me fix it" controls.

### Acceptance

- Filesystem snapshots before and after every advisor session are identical.
- Prompt injection inside project prose cannot grant write or shell access.
- Answers cite current project evidence and warn when the index is stale.
- Advisor sessions survive application restart without changing formal workflow state.

## 13. Milestone H: Durable Worker and Human Writeback

### Objective

Make long-running Agent execution safe for ordinary desktop use.

### Work

1. Build the formal Worker supervisor on the Milestone B lifecycle, job, lock, and event contracts rather than creating a second execution loop.
2. Add per-project locks, idempotency keys, concurrency limits, heartbeat, lease expiry, and crash recovery.
3. Add stop, retry, resume, duplicate-run prevention, and runtime switching.
4. Persist normalized events incrementally with bounded retention and redaction.
5. Generate writeback diffs before import.
6. Require approval for body prose replacement, Canon, character facts, state apply, and release artifacts.
7. Allow safe automatic import only for low-impact generated support files explicitly classified by policy.
8. Restore backups when import or downstream core validation fails.

### Acceptance

- Killing Studio or OpenCode during a task does not mark it complete or corrupt the project.
- Restarted Studio identifies interrupted work and offers retry, resume, discard, or runtime switch.
- Two tasks cannot mutate the same project route concurrently.
- High-impact files are never imported before the user sees an understandable diff and impact summary.

## 14. Milestone I: Native Desktop Packaging

### Objective

Deliver Studio as a native application with no external browser or development runtime requirement.

### Recommended shell

Use Tauri 2 and retain the existing frontend. Package:

- the Tauri desktop shell;
- the existing static frontend;
- a frozen Studio Python application service;
- the target-specific OpenCode binary;
- required templates, schemas, prompt assets, icons, and license notices.

The first desktop release should keep the Studio API sidecar rather than rewrite the embedded Python engine in Rust. The Tauri shell owns process startup, random ports, authentication tokens, lifecycle shutdown, native file dialogs, keychain access, logs, and updates.

The shell should follow subsystem boundaries rather than becoming a second business backend: orchestration, backend/Runner process control, lifecycle, bridge policy, window/tray behavior, updater, and shared desktop state remain separate Rust modules.

### Desktop capabilities

- native project folder and export destination dialogs;
- open output folder and reveal file actions;
- system keychain integration;
- one-instance project locking;
- window state and reading position persistence;
- application update channel;
- crash-safe shutdown of Studio and OpenCode sidecars;
- optional WebView2 offline installer for Windows release builds.

### Acceptance

- A clean Windows test machine with no Python, Node, OpenCode, or browser window can install and launch Studio.
- The UI works offline up to the point where a cloud model connection is required.
- Uninstall removes application binaries but preserves user projects and asks before removing application data.
- Release artifacts are reproducible, checksummed, license-complete, and code-signing ready.

## 15. Milestone J: Product Verification and Release

### Automated verification

- existing Studio unit and API tests;
- embedded engine prompt-registry validation;
- runtime conformance tests for fake, Claude, and OpenCode adapters;
- real OpenCode fixture workflow tests;
- browser and Tauri WebDriver interaction tests;
- SSE reconnect and long-run interruption tests;
- path traversal, prompt injection, unexpected write, credential leakage, and localhost authentication tests;
- Windows package install, upgrade, repair, and uninstall tests;
- large-project library, search, reader, and event-stream performance tests.

### Release scenarios

The release candidate must demonstrate:

1. first launch and provider connection;
2. project creation and direction entry;
3. automatic issue and execution of a formal task;
4. live progress display and safe cancellation;
5. a required human decision;
6. writeback diff and gate validation;
7. read-only project Q&A with citations;
8. completed prose reading;
9. clean DOCX/export delivery;
10. interruption and recovery.

## 16. Development Order and Stop Gates

Work in this order:

1. Milestone A: contracts and baseline.
2. Milestone B: application lifecycle, durable jobs, persistent events, and recovery.
3. Milestone C: Claude repair, used to validate the Runner contract and lifecycle foundation.
4. Milestone D: OpenCode server and formal Worker integration.
5. Milestone E: Model Connection and Agent Runner settings.
6. Milestone F: prompt evaluation and high-risk exact assets.
7. Milestone G: read-only advisor.
8. Milestone H: durable formal Worker and writeback approval.
9. Milestone I: Tauri packaging.
10. Milestone J: release verification.

Do not integrate a bundled OpenCode process before Milestone B can supervise, stop, recover, and replay a fake Runner. Do not start native packaging before OpenCode execution, secret handling, stop/recovery, and writeback diff are stable. Packaging an unstable runtime only makes failures harder to diagnose.

## 17. Key Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| OpenCode upstream changes break the client | Pin a tested binary version, probe capabilities, keep a narrow OpenAPI adapter, and update intentionally. |
| Windows OpenCode behavior differs from WSL | Test the native release binary on clean Windows machines; avoid shell-dependent worker behavior; do not require WSL in the ordinary-user edition. |
| Global OpenCode/Claude configuration contaminates tasks | Use application-owned config directories, pure/safe modes, disabled plugins and skills, and isolated sandboxes. |
| API keys leak into projects or logs | Use one-way local submission, OS credentials or OpenCode Auth, redaction, secret scanning, and renderer isolation. |
| Agent bypasses workflow rules | Keep engine-issued task packages, expected-output-only writeback, deterministic validation, and route audit as authority. |
| Read-only advisor writes through a tool loophole | Use a read-only filesystem snapshot plus deny-all write/shell/task policy; verify before/after hashes. |
| Model quality varies by provider | Display the actual model, publish recommended profiles, run prompt evaluations, and never silently substitute models. |
| Desktop package becomes too large | Keep system WebView2 as default on modern Windows; offer an offline installer build separately. |
| Product claims become misleading | Say "no development environment required" rather than "no model configuration required." |
| Runner and model configuration collapse into one abstraction | Keep versioned `AgentRunner` and `ModelConnection` contracts, separate UI sections, and independent readiness states. |
| In-memory events disagree with recovered job state | Persist state transitions and events transactionally before publishing SSE projections. |
| A broad plugin ecosystem expands the attack surface | Defer public plugins; if extensions are later added, use capability-scoped APIs and isolated frontend bridges. |

## 18. Definition of Done

This productization round is complete when:

- Agent Runner and Model Connection are separate contracts and separate user-facing readiness states;
- Studio API, jobs, events, Runner sidecars, sessions, and shutdown are controlled by one recoverable application lifecycle;
- OpenCode is bundled and is the default formal Agent Runner;
- a user can connect and test a model entirely in the frontend;
- every formal Agent run remains inside a task sandbox and passes engine writeback gates;
- task progress streams live and interrupted work can be recovered;
- high-impact writebacks require an understandable diff and approval;
- the project advisor can answer with citations and is technically unable to write;
- the native desktop client installs without Python, Node, OpenCode, or an external browser workflow;
- prompt quality is covered by a regression harness, with exact assets for high-risk tasks;
- the full create, execute, decide, review, read, and export journey works on a clean Windows test machine.
