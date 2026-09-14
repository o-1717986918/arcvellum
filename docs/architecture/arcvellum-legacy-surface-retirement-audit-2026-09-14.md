# ArcVellum Legacy Surface Retirement Audit

Date: 2026-09-14
Branch: `feat/lean-literary-kernel-v2`
Scope: obsolete UI, superseded product surfaces, compatibility facades, runtimes, task protocols, and literary kernels

## Decision rule

A file is removed only when all of the following are true:

1. It has no production entrypoint or dynamic registry registration.
2. Its replacement is already present on the supported product path.
3. Removing it does not invalidate a published compatibility promise, project migration, rollback path, or persisted data reader.
4. Its tests describe the retired implementation itself rather than a current public contract.
5. Targeted verification and the repository compatibility verifier pass after removal.

Words such as `legacy`, `compatibility`, or `old` are audit hints, not deletion evidence. Migration readers and old-project recovery code remain valuable while released projects still depend on them.

## Immediate retirement cohort

### Disconnected Orrery implementation

The production graph begins at `client/src/main.ts` and reaches the current Pixi spatial scene through `OverviewView.vue` and `WorkspaceOrreryHost.vue`. The following earlier SVG/instrument implementation has no production importer:

- `client/src/components/ImmersiveConsole.vue`
- `client/src/components/ImmersiveInstrumentWindow.vue`
- `client/src/components/StoryTrace.vue`
- `client/src/features/library/LibraryView.vue`
- `client/src/types/immersive.ts`
- `client/src/services/orreryFeatures.ts`

The component-specific tests and CSS selectors retire with that implementation. Historical roadmap references remain because they explain prior decisions and are not runtime dependencies.

### Superseded Advisor presentation

The Project Agent is now the supported conversational control surface and owns the default application route. The old floating Advisor is still mounted only on `/overview`; it duplicates conversation, persona, command dispatch, and streaming UI while retaining a more restricted product contract. This batch removes:

- the `AdvisorDock` mount in `App.vue`;
- Advisor floating-shell, message-thread, and conversation-composable UI code;
- Orrery collision and gesture exceptions created solely for the floating dock;
- Advisor-only styles.

The `advisorClient`, HTTP endpoints, Python service, and `advisor_*` persistence tables remain for one compatibility window. Project Agent records also reuse the physical session tables with `session_kind="project-agent"`; deleting or renaming those tables would be a data migration, not dead-code cleanup.

### Unmanifested Studio import facades

The following top-level modules only forwarded imports to canonical domain packages. Production code already uses the canonical paths; after converting their remaining tests, these facades are removed:

- `agent_session_tracking.py` -> `observability.agent_session_tracking`
- `bootstrap.py` -> `application.bootstrap`
- `execution_coordinator.py` -> `runtime.execution_coordinator`
- `lifecycle.py` -> `infrastructure.legacy_lifecycle`
- `process_manager.py` -> `runtime.process_manager`
- `project_progress.py` -> `application.project_progress`
- `prompt_evaluation.py` -> `automation.prompt_evaluation`
- `read_model_cache.py` -> `projections.read_model_cache`
- `sidecar_protocol.py` -> `runtime.sidecar_protocol`
- `task_program.py` -> `runtime.task_program`

These paths were not listed in the published compatibility manifest. Their implementations and behavior remain; only ambiguous package-root aliases disappear.

## Retained compatibility surfaces

### Lean v2 and strict v1

`src/literary_engineering_studio/compatibility/lean-kernel-v2.json` currently records:

- `lean-v2` as preview;
- `strict-v1` as supported fallback;
- zero observed zero-consumer release cycles;
- `deletion_allowed=false`.

The new Project Agent explicitly drives `lean-v2`, while existing projects and rollback still consume `strict-v1`. The old kernel may be physically removed only after literary non-inferiority evidence changes the default, telemetry or an equivalent inventory proves zero production consumers for two releases, and a project migration command exists.

### Engine public API and aliases

The Engine `public.*` modules are the stable Studio-to-Engine boundary. Six declared top-level Engine aliases and the legacy Engine HTTP entrypoint have `remove_not_before: 1.0.0`. They remain until that release and a fresh external-consumer audit. Internal code must continue importing canonical modules rather than extending the alias surface.

### Historical project readers

Promotion context migration, old schema normalization, historical task readers, and retained field aliases protect user projects already written to disk. They remain read-only migration boundaries. New writes must use current schemas so the compatibility population can monotonically decrease.

### OpenCode historical labels

OpenCode is absent from the runtime registry, product UI, and desktop resources. Remaining occurrences are compatibility-manifest history, config cleanup for old installations, neutral runtime-id fixtures, and retirement tests. Packaging cleanup that deletes stale files from previous builds remains necessary and is not a runtime dependency.

## Deferred retirement packets

### C2: Advisor API compatibility

Remove the old `/advisor/*` API and `advisorClient` after one released version without a product caller. Preserve or migrate Project Agent rows before changing physical table names. Regenerate OpenAPI and client types in the same packet.

### C3: Studio top-level facades

Continue the same inventory for aliases that still have active consumers. `autopilot.py` and `whole_book_release.py` are deferred while their regression files carry an independent uncommitted change set. Move production imports to canonical packages first. Delete only facades with no external promise; add any intentionally retained facade to a bounded manifest.

### C4: strict-v1 kernel

Complete blind literary comparison, switch new-project default, publish migration/rollback guidance, record two zero-consumer releases, then remove the strict route and its exclusive task-sidecar machinery as one atomic change.

### C5: Engine aliases at 1.0

Remove declared aliases only after their `remove_not_before` version, consumer audit, and migration guide. Keep the stable `public.*` boundary unless a separate API version is introduced.

## Guardrails for future development

- New production code may not import deprecated aliases.
- A compatibility reader may parse old data but may not emit old schemas.
- Product runtimes must be registered through the runtime registry; string fixtures do not establish runtime support.
- A retired frontend surface must be removed from imports, styles, tests, onboarding, and collision geometry in the same change.
- Compatibility retirement is versioned engineering work, not a search-and-delete pass.

## Verification

Run after each retirement cohort:

```powershell
.venv\Scripts\python.exe scripts\verify_compatibility_surface.py
npm run client:test
npm run client:build
git diff --check
```

Use focused tests first. The full Python suite is required only when a Python compatibility or kernel packet is changed.

## First cohort result

The 2026-09-14 cleanup removed 25 obsolete source and test files while preserving their active replacements. The net change removes more than 2,200 lines from the maintained surface. It does not alter the persisted project schema, Studio HTTP contract, runtime registry, or either literary-kernel implementation.

Completed verification:

- focused Python compatibility and canonical-import tests: 33 passed;
- Studio compatibility-surface verifier: passed;
- complete frontend suite: 68 files and 215 tests passed;
- production frontend build and desktop asset synchronization: passed;
- whitespace and patch integrity check: passed.

The repository architecture audit still reports two pre-existing debt groups that this cleanup deliberately does not hide by refreshing the baseline:

1. `client/src/features/project-agent/workspaces.ts` imports concrete components owned by other features. A later packet should move workspace descriptors into a neutral composition-root registry.
2. The committed architecture baseline has 14 outstanding size or inventory differences, including `api_server.py` above the configured 500-line budget. These require modular extraction or an explicit architectural decision, not baseline normalization during dead-code removal.

These findings do not invalidate this retirement cohort, but they remain release-quality debt and should be resolved before declaring the architecture baseline clean.
