# Agent thinking controls and dead-code audit (2026-09-22)

## Change packets

```yaml
module_change_packet:
  objective: "Persist independent, user-selected thinking levels for Project Agent and creative Worker"
  primary_module: "Studio application/config"
  public_entry: "get_pi_thinking_preferences / set_pi_thinking_preference"
  variation_point: "model-supported thinking levels, handled by the existing Pi adapter"
  inputs: ["role: project|creative", "level: off|minimal|low|medium|high|xhigh|max"]
  outputs: ["saved local configuration", "current preference DTO"]
  invariants: ["no credentials in config", "existing non-default choices survive migration", "Project Agent and Worker remain independent"]
  allowed_dependencies: ["application/config", "api/routers/pi_worker", "api/models"]
  forbidden_dependencies: ["Engine literary gates", "provider HTTP client", "project files"]
  tests: ["config migration and validation", "API route contract"]
  rollback_unit: "configuration/API commit"
  documentation: ["this audit"]
```

```yaml
module_change_packet:
  objective: "Make the creative preference effective in prose task execution, not only in the config file"
  primary_module: "Studio runtime/execution_profiles"
  public_entry: "resolve_task_execution_profile"
  variation_point: "Pi Worker reasoning-budget support"
  inputs: ["formal TaskPackage", "worker execution config plus selected thinking level"]
  outputs: ["profile and Pi Worker runtime arguments with the selected level"]
  invariants: ["deterministic tasks stay off", "request/timeout limits remain", "manifest and execution agree"]
  allowed_dependencies: ["runtime/worker", "runtime/worker_preparation", "runtime/worker_execution_profile"]
  forbidden_dependencies: ["Engine gates", "Provider SDK", "UI"]
  tests: ["creative/prose profile controls", "Worker runtime arguments"]
  rollback_unit: "runtime commit"
  documentation: ["this audit"]
```

```yaml
module_change_packet:
  objective: "Let desktop users inspect and change both thinking levels"
  primary_module: "client/features/settings"
  public_entry: "settingsClient.thinkingPreferences / saveThinkingPreference"
  variation_point: none
  inputs: ["local settings API DTO"]
  outputs: ["visible current values and immediately persisted choices"]
  invariants: ["a failed save restores the confirmed value", "existing model selection remains intact"]
  allowed_dependencies: ["settings feature client", "settings view", "API DTO"]
  forbidden_dependencies: ["generic transport in Vue component", "Engine"]
  tests: ["settings feature client contract", "settings view interaction"]
  rollback_unit: "client commit"
  documentation: ["this audit"]
```

```yaml
module_change_packet:
  objective: "Remove compiler-proven dead frontend locals without changing behavior"
  primary_module: "client TypeScript compilation surface"
  public_entry: "vue-tsc --noUnusedLocals"
  variation_point: none
  inputs: ["current frontend source and Vue templates"]
  outputs: ["zero unused-local diagnostics"]
  invariants: ["no route, model, project, or literary behavior changes"]
  allowed_dependencies: ["client source files named by TS6133/TS6196 diagnostics"]
  forbidden_dependencies: ["Engine", "API", "runtime semantics"]
  tests: ["strict unused-local typecheck", "full client tests and build"]
  rollback_unit: "independent frontend hygiene commit"
  documentation: ["this audit"]
```

## Audit method and disposition

Follow the prior retirement audit's five-part decision rule. Search static production and test references, inspect dynamic registrations and compatibility promises, then remove only zero-consumer duplicates. The settings feature client contains four second copies of catalog/credential/model/disconnect calls (`piCatalog`, `savePiCredential`, `selectPiModel`, `disconnectPiProvider`) and three types used solely by them. Repository source search finds their declarations only; the active view and store use the canonical methods. They are safe to remove in the settings packet.

A repository-wide `vue-tsc --noUnusedLocals` pass identified eight further unused symbols: one unused template loop value, six unused imports in production Vue/TS files, and one unused test import. This mechanical cohort is separated from the settings behavior change.

Do **not** remove `strict-v1`, Advisor API/persistence, Engine public aliases, or historical readers. They have compatibility or rollback consumers documented in `arcvellum-legacy-surface-retirement-audit-2026-09-14.md`; names such as legacy or old are not dead-code proof. A repository-wide deletion claim would be misleading without dynamic registry and release-cycle evidence.

## Behavior decision

Defaults change from Project Agent `max` to `xhigh`, and from creative Worker `low` to `medium`. Existing stored `max`/`low` values lacking the new preference marker are treated as untouched old defaults and migrated once; other values are preserved. The old format cannot distinguish a deliberately reselected `max`/`low` from an untouched default; affected users can restore either level through the new controls, after which the marker prevents another migration. The UI offers every runtime-supported level. A provider may safely lower an unsupported requested level; task request and token limits remain in force. The selected creative level governs Pi Worker task execution, including prose tasks whose previous enforced profile silently reset it to `minimal`.

## Verification record

- Static source-reference audit: all four duplicate settings client methods and their three exclusive types had zero consumers outside their declarations. No dynamic feature registry refers to them.
- Config migration, API read/write/validation, Project Agent command composition, creative/prose execution profiles, and explicit `off` repair behavior have focused tests.
- The final client suite passed (75 files, 248 tests). Strict unused-local typecheck and production build passed.
- Pi Worker check passed (10 files, 102 tests); Project Agent suite passed (39 tests); compatibility surface, prompt registry, generated module map, and architecture audit passed.
- The settings visual test passed at 1440×900 and 390×844. Screenshots were visually inspected, with no horizontal overflow or control overlap. Images are under `build/orrery-visual/results/` (local generated evidence, not source-controlled).
- Full Python suite passed on the corrected tree: 1,494 tests, one conditional skip. The initial pre-extraction run had reported only the architecture budget that was subsequently fixed; the fresh run is the release-quality result.
