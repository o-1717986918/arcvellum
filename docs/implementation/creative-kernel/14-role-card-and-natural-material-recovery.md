# Role Card Initialization and Natural Material Recovery

## Module Change Packets

### Batch A — Role card is the sole personality initialization

```yaml
module_change_packet:
  objective: "A roleplay actor receives the complete saved character card verbatim as its sole personality initialization."
  primary_module: "Engine literary/scene/roleplay"
  public_entry: "literary_engineering_studio_engine.public.literary.render_actor_initialization_prompt"
  variation_point: "The Studio resolves the scene participant to a project character-card file; Engine renders the card without persona synthesis."
  inputs:
    - "Scene participant identity"
    - "Complete UTF-8 character-card source text"
    - "Separate per-turn scene task and interaction protocol"
  outputs:
    - "Character-card source text preserved verbatim, including line endings"
  invariants:
    - "Scene turn task, current knowledge, and output contract remain separate from personality initialization."
    - "An absent or ambiguous card must be surfaced; generated actor tags are not a fallback personality source."
    - "Roleplay candidates remain isolated and are not formal prose or canon."
  allowed_dependencies:
    - "Studio scene_interaction runtime through the Engine public literary API"
    - "Existing character YAML card files"
  forbidden_dependencies:
    - "Planner-authored actor_personas or actor_prompts as personality initialization"
    - "Global default voice tags or appended immersion/personality instructions"
  tests:
    - "Engine public initialization contract tests"
    - "Studio character-card resolution and roleplay-session initialization tests"
  rollback_unit: "Batch A code and its tests"
  documentation:
    - "This implementation packet"
    - "Public API contract docstring"
```

### Batch B — Recover creator material decisions once

```yaml
module_change_packet:
  objective: "An invalid final material decision receives one correction attempt against the exact candidates and already generated body; recovery reuses preserved answers."
  primary_module: "Studio runtimes/scene_creator_material_policy.py"
  public_entry: "repair_material_choice; PiSceneTransactionRuntime and NaturalCreatorMixin adapters"
  variation_point: "Structured compatibility output and natural output use the same selection policy with their existing transport adapters."
  inputs:
    - "Natural creator answer and extracted payload"
    - "Frozen material index candidate IDs"
    - "Previously accepted material decisions"
  outputs:
    - "A validated creator payload with an accountable candidate choice, or the existing structured blocker"
  invariants:
    - "Candidate IDs and choices are validated against the transaction's actual material index."
    - "No invalid ID or choice is silently rewritten."
    - "The correction attempt preserves already generated prose and SceneDelta."
    - "Only one focused correction attempt is allowed per creator answer."
  allowed_dependencies:
    - "scene_creator_material_policy"
    - "NaturalOutputProcessor"
    - "NaturalTurnStore"
    - "PiSceneTransactionRuntime compatibility adapter"
  forbidden_dependencies:
    - "New model/provider client"
    - "Relaxed candidate validation or formal writeback bypass"
  tests:
    - "Natural creator recovery tests for unknown IDs and invalid choices"
    - "Regression proving valid candidate decisions need no extra invocation"
  rollback_unit: "Batch B code and its tests"
  documentation:
    - "This implementation packet"
    - "Natural creator recovery test evidence"
```

## Completion criteria

- A role actor's initialization equals its complete character-card source, without planner-generated persona tags, default style tags, or appended immersion prose.
- The character's card fields, including `speech_style`, examples, habits, and behavior patterns, are all available in that initialization.
- Invalid natural creator material decisions get one targeted correction attempt; valid decisions do not incur that extra attempt.
- Existing prompt snapshots and historical initialization fields remain traceable; recovery continues through the original creation run.
- Targeted tests and architecture checks pass; no external model execution is used as a substitute for deterministic verification.

### Batch C — Align the top-level guidance with card initialization

```yaml
module_change_packet:
  objective: "The top-level Agent identifies the character card as the current personality source and treats stored persona tags as historical configuration."
  primary_module: "Studio project_agent"
  public_entry: "ProjectAgentDependencies.actor_personas read model and Project Agent tool descriptions"
  variation_point: "Historical tag storage stays readable; current initializer provenance is reported explicitly."
  inputs: ["Existing actor tag read model", "Current character archive fields"]
  outputs: ["Actor persona source metadata", "Updated versioned Project Agent prompt assets"]
  invariants: ["Historical configurations remain readable", "Character changes use the existing archive transaction and audit"]
  allowed_dependencies: ["Engine prompt assets", "Pi tool descriptor adapter", "Existing Project Agent read models"]
  forbidden_dependencies: ["Direct project writes", "New role personality synthesis"]
  tests: ["Project Agent read-model and tool protocol tests", "Prompt registry tests"]
  rollback_unit: "Batch C guidance and read-model metadata"
  documentation: ["This packet", "Tool source descriptions"]
```

## Implementation facts

- The affected active transaction uses the compatibility creator chain, not natural v2. Its repair call had generic feedback and regenerated a full delivery without the prior invalid selection or explicit valid IDs.
- The repair now sees the exact IDs, invalid values, and original body; only its material decisions are merged. Original body and SceneDelta are retained.
- Compatibility creator answers and corrections are cached as original text through the existing turn store. Repeating a blocked transaction with unchanged inputs reuses both answers.
- Natural v2 also gets the focused correction. Its extractor verifies that selected candidate IDs occur in the creator's source text, and repairs extraction before asking the creator again.
- New compatibility actor sessions load complete saved character-card source. Natural and structured v2 actor system initialization contains the rendered sixteen-section card. Per-turn tasks carry scene stimuli separately.
- When a legacy session gets a new actor turn, a character-card initialization is frozen beside its historical tag initialization. Historical fields and existing turn history remain traceable; subsequent calls use the card initialization.
- New performance plans carry scene tasks rather than synthesized actor persona tags. Existing transaction session files and historical persona configurations are retained.

## Validation and live recovery

- Full Python matrix: 1819 tests, pass, one opt-in test skipped. The additional legacy-session migration suite passed 50 tests after that matrix.
- Client: 272 tests and production build passed. Pi Worker: 124 tests, type checks, and build passed.
- Architecture audit passed with 16 existing file debts, 76 function debts, no cycles or forbidden Studio-to-Engine imports. Module inventory, version synchronization, prompt registry, compile, doctor, CLI help, and diff checks passed.
- The actual saved Lumiya and Grom card initialization strings matched their complete source text, including speech-style fields: 2816 and 3207 characters respectively.
- The original blocked transaction's first recovered body contained Chinese choice labels and selected the `scene-context` resource. Its focused correction returned valid candidate decisions with no replacement body. The first body and subsequent literary revision were both preserved.
- After one literary revision, the recovered candidate passed review. Commit then correctly stopped because the scene file had a recorded edit after the old transaction began. Its current SceneBrief remained equal, while its source revision digest differed.
- The existing source-conflict recovery path was used on the same creation run. It retains the reviewed old candidate and prepares a fresh transaction from current source files; no revision guard was weakened.
- Runtime evidence and file hashes are in the local `work/dev-runtime/role-card-recovery-evidence.json`; test logs remain local.
