# ArcVellum v0.99.1 Module Change Packets

## Batch A: Unbounded Autopilot Authorization

```yaml
module_change_packet:
  objective: "Autopilot no longer pauses because a task, runtime, estimated-cost, or authorization-expiry ceiling was reached."
  primary_module: "src/literary_engineering_studio/automation"
  public_entry: "automation/policy.py::DelegationPolicy and automation/controller.py::AutopilotController"
  variation_point: "Delegation mode and failure/revision recovery policy remain configurable; run duration and creative spend are no longer authorization dimensions."
  inputs: ["delegation policy", "durable autopilot run", "campaign checkpoint settings"]
  outputs: ["normalized open-ended policy", "continuous run state", "quality-failure pause evidence"]
  invariants:
    - "Manual pause, project completion, deterministic failures, repeated revision failure, and recovery exhaustion still stop a run."
    - "Engine task, review, promotion, Canon, state, continuity, and release gates are unchanged."
    - "Word-count budgets, prompt/context budgets, provider accounting, and process lease expiry are not Autopilot authorization limits and remain intact."
  allowed_dependencies: ["orchestration campaign contracts", "application persistence ports", "runtime worker port"]
  forbidden_dependencies: ["Engine gate duplication", "automatic approval outside delegated policy", "infinite retry after no progress"]
  tests: ["tests/test_autopilot.py", "tests/automation/test_campaign_runtime.py", "client/src/components/AutopilotPanel.spec.ts"]
  rollback_unit: "v0.99.1 batch A commit"
  documentation: ["docs/releases/v0.99.1.md", "this change packet"]
```

Compatibility policy: stored pre-v0.99.1 policies may still contain legacy
`max_tasks`, `max_runtime_hours`, `max_cost`, and `expires_at` fields. The
normalizer discards these authorization ceilings instead of letting an old
project silently re-enable them.

## Batch B: Single Brand Theme

```yaml
module_change_packet:
  objective: "ArcVellum exposes and renders one coherent default color identity: Moss/Mineral Orrery."
  primary_module: "client/src/services/orreryPreferences.ts"
  public_entry: "readOrreryExperience(), applyOrreryExperience(), loadOrreryBackground()"
  variation_point: "Motion, depth, and render quality remain user preferences; color theme and background palette do not vary."
  inputs: ["legacy localStorage values", "appearance controls", "Orrery host"]
  outputs: ["theme=moss", "background=mineral", "single visual identity"]
  invariants:
    - "Reduced motion, still mode, depth, and efficient rendering remain available."
    - "No literary, workflow, project, or Agent behavior changes."
    - "Legacy non-default preferences normalize to the default without a migration prompt."
  allowed_dependencies: ["workflow Overview view", "settings appearance view", "Orrery asset loader"]
  forbidden_dependencies: ["project persistence", "backend theme state", "new asset generation"]
  tests: ["orreryPreferences.spec.ts", "Orrery visual Playwright smoke", "client build"]
  rollback_unit: "v0.99.1 batch B commit"
  documentation: ["docs/releases/v0.99.1.md", "this change packet"]
```

## Batch C: Versioned Release

```yaml
module_change_packet:
  objective: "Produce and publish a reproducible signed ArcVellum v0.99.1 Windows release."
  primary_module: "packaging and release metadata"
  public_entry: "packaging/build_desktop.ps1 and .github/workflows/release.yml"
  variation_point: "release version and generated artifacts"
  inputs: ["tested source commit", "synchronized version declarations", "signing environment"]
  outputs: ["installer", "updater signature", "latest.json", "SHA256SUMS", "Git tag and GitHub Release"]
  invariants:
    - "All version declarations match the tag."
    - "The frozen sidecar and bundled Pi Worker pass provenance checks."
    - "No dirty or untracked release code is omitted from the source commit."
  allowed_dependencies: ["client production build", "Python sidecar", "Pi Worker bundle", "Tauri"]
  forbidden_dependencies: ["manual binary substitution", "unsigned updater metadata", "tag before validation"]
  tests: ["version sync", "full deterministic suite", "architecture audit", "desktop packaging smoke"]
  rollback_unit: "v0.99.1 release commit and tag"
  documentation: ["docs/releases/v0.99.1.md", "docs/releases/v0.99.1-verification.md"]
```

## Batch D1: Narrative Projection Convergence

```yaml
module_change_packet:
  objective: "Reduce v4 projection complexity while preserving the complete creative constellation contract."
  primary_module: "src/literary_engineering_studio/projections"
  public_entry: "build_narrative_projection_v4()"
  variation_point: "graph assembly, payload assembly, semantic-parent selection, and workflow activity projection"
  inputs: ["v4 narrative projection inventory", "dashboard", "library", "reader manifest"]
  outputs: ["contract-equivalent v4 projection and node detail"]
  invariants:
    - "No projection schema, node/edge meaning, activity status, focus behavior, or revision digest input changes."
    - "Compatibility facades contain no business dependencies; unreleased v4 code uses its canonical module path."
  allowed_dependencies: ["projection submodules", "read model DTOs"]
  forbidden_dependencies: ["API transport", "new Gate logic", "new global state", "baseline relaxation"]
  tests: ["narrative projection v4 tests", "architecture audit"]
  rollback_unit: "v0.99.1 batch D1 commit"
  documentation: ["generated module map", "v0.99.1 verification record", "this change packet"]
```

## Batch D2: API Composition Convergence

```yaml
module_change_packet:
  objective: "Keep the API composition root and narrative router within architecture budgets without changing HTTP behavior."
  primary_module: "src/literary_engineering_studio/api"
  public_entry: "build_narrative_router() and create_app()"
  variation_point: "versioned route registration and dependency composition"
  inputs: ["NarrativeRouterDependencies", "HTTP query/path parameters"]
  outputs: ["unchanged v2/v3/v4 HTTP and SSE endpoints"]
  invariants: ["No path, query default, response schema, SSE event, or error status changes."]
  allowed_dependencies: ["API DTOs", "projection public callables"]
  forbidden_dependencies: ["router business state", "duplicate projection logic", "baseline relaxation"]
  tests: ["API server tests", "narrative stream tests", "architecture audit"]
  rollback_unit: "v0.99.1 batch D2 commit"
  documentation: ["generated module map", "this change packet"]
```

## Batch D3: Orrery Layout Convergence

```yaml
module_change_packet:
  objective: "Separate narrative timing from spatial placement while preserving every Orrery coordinate and layout grammar."
  primary_module: "client/src/features/orrery/layout"
  public_entry: "buildSpatialLayout()"
  variation_point: "rhythm smoothing, temporal spacing, and scene clustering"
  inputs: ["SpatialNarrativeNode[]", "SpatialGrammar", "layout hints"]
  outputs: ["coordinate-identical SpatialLayout"]
  invariants: ["No coordinate formula, stable seed, collision behavior, or focus behavior changes."]
  allowed_dependencies: ["Orrery spatial types", "curve profiles", "layout hints"]
  forbidden_dependencies: ["Vue stores", "backend DTO mutation", "new display heuristics"]
  tests: ["Orrery layout unit tests", "Vitest", "visual Playwright", "architecture audit"]
  rollback_unit: "v0.99.1 batch D3 commit"
  documentation: ["generated module map", "this change packet"]
```

## Batch D4: Frontend Composition Convergence

```yaml
module_change_packet:
  objective: "Remove concrete cross-feature component imports from Orrery and spatial feature modules."
  primary_module: "client application workspace composition"
  public_entry: "creativeWorkspaceRegistry and Orrery workspace dock"
  variation_point: "application-level lazy component registration"
  inputs: ["workspace id", "creative node kind", "window state"]
  outputs: ["same visible workspace component and dock behavior"]
  invariants: ["No workspace, title, supported node type, geometry, or interaction disappears.", "Feature modules do not own another feature's component."]
  allowed_dependencies: ["application composition registry", "workspace descriptor contract", "Orrery window store"]
  forbidden_dependencies: ["feature-to-feature concrete component import", "duplicate workspace metadata"]
  tests: ["workspace registry tests", "Vitest", "architecture audit"]
  rollback_unit: "v0.99.1 batch D4 commit"
  documentation: ["generated module map", "this change packet"]
```
