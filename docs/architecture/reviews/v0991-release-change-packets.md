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

