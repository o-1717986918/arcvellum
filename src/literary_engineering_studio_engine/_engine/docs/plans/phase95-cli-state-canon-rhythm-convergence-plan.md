# Phase 95: CLI State, Canon Writeback, And Narrative Rhythm Convergence

Status: implemented / verified
Purpose: summarize the latest design discussion, check what is already implemented, and define a restrained next development stage without re-planning mechanisms that already exist.

Implementation note: this plan has now been executed in `v0.95.0`. The implemented scope includes the host operating constitution, `canon-evolve`, canon writeback status gates, narrative rhythm / scene bridge contracts, exact high-risk prompt assets, frontend project-library display hooks, and regression tests.

## 1. Working Judgment

The project has already implemented most of the hard workflow kernel:

- registered formal route loop: `task-next -> task-open -> task-submit -> task-complete`;
- Prompt Registry;
- Context Broker and Context Trace;
- New Character Register;
- Workflow Contract Validation;
- longform word budget and Chinese-content character counting;
- Reader Experience / Chapter Obligation Contract;
- Workflow Dashboard;
- frontend project library and completed-prose display;
- Style Lint, anti-evasion revision, exact-candidate review, promotion, export, and debug-waiver gates.

Therefore Phase 95 should not become another broad "everything overhaul". The useful next work is narrower:

1. turn the host-facing entry documents into a concise operating constitution;
2. reduce remaining opportunities for platform agents to treat CLI as optional;
3. add the missing post-scene canon writeback candidate path;
4. fold narrative rhythm and scene-bridge controls into existing reader-experience and scene-development routes;
5. keep frontend and batch orchestration improvements incremental.

## 2. Checked Implementation Baseline

| Mechanism | Current state | Evidence in project | Remaining gap |
| --- | --- | --- | --- |
| Host-facing operating constitution | Partially implemented as rules across entry docs | `SKILL.md`, `AGENTS.md`, `agent-run-protocol.md`, `cli-run-protocol.md` | The rule set exists, but the first-entry documents still expose too much map-like detail before the CLI task loop. |
| CLI-mediated formal route loop | Implemented across main routes | `task_registry.py`, `workflow_state.py`, `workflow_contract.py`, Phase 84 docs | Too many diagnostic commands can still confuse agents; needs a clearer preferred operating surface. |
| Prompt assets from CLI task packages | Implemented at route level | `templates/prompt_assets/`, `prompt_registry.py`, Phase 85 docs | High-risk exact assets can still be refined, but the registry itself exists. |
| Context trace proof | Implemented | `context_broker.py`, `context_trace.v1.json`, Phase 86 docs | Keep extending trace only when new required inputs are added. |
| New character gate | Implemented | `new_character_register.py`, Phase 86.1 docs | New world/canon facts do not yet have an equivalent per-scene writeback path. |
| Workflow contract validation | Implemented | `workflow-validate`, Phase 87 docs | Useful but not a single simple "what should I do now" operator view. |
| Word budget and count unit bridge | Implemented | `word_budget.py`, `text_counts.py`, Phase 65 and 89.1 docs | Continue using Chinese-content chars; do not add another count standard. |
| Reader experience contract | Implemented | `reader_experience.py`, `chapter-obligation`, Phase 88 docs | Covers reader questions and promises, but not explicit scene rhythm and bridge checks. |
| Canon review | Implemented as hard project-level gate | `canon-lint`, `agent-canon-review`, `review-and-audit` route | It checks canon, but does not force every new world fact from a scene into a candidate canon patch. |
| State evolution | Implemented for characters | `state-evolve`, `state-apply` | Explicitly does not write `canon/`; needs a parallel canon candidate path. |
| Frontend project display | Partially implemented | Phase 91-94 docs, frontend/API code | Keep as presentation and choice surface; do not make it a second workflow engine. |
| Batch/concurrency | Partially guarded by per-scene gates | route-audit, workflow validation, batch scene ledger | Real worker leases and queues are still future work; defer unless batch failures recur. |

### Review Correction From Actual Code Inspection

The implementation review changes the emphasis of this phase. The formal `scene-development` chain is already substantially harder than a document-only process: route audit checks context trace, RP and branch sidecar completion, composition provenance, word budget, reader contract, generation provenance, Style Lint, exact-candidate AgentReview, promotion, static review, state patch, and mounted style adherence.

Phase 95 should therefore avoid describing the existing core scene chain as weak. The real weakness is more specific:

1. the host-facing entry surface can still look like a command toolbox;
2. simple status views are less authoritative than route audit and task completion gates;
3. scene-created canon facts lack a formal candidate writeback path;
4. rhythm and scene-to-scene bridge controls are not yet first-class generation/review inputs.

Keep future implementation notes grounded in these four observed gaps.

## 3. Non-Goals For This Stage

Do not build these in Phase 95 unless a concrete failure forces them:

1. a second workflow engine outside the CLI route registry;
2. a large async worker queue with leases, retries, and distributed locking;
3. a complete rewrite of `SKILL.md`, `AGENTS.md`, and `agentread.yaml`;
4. a fully editable frontend that can directly change canon, characters, drafts, or releases;
5. another independent reader-ledger system when Chapter Obligation already exists;
6. local provider or HTTP-agent creative authority revival;
7. a new formal route for every quality idea.
8. contest/SkillHub submission package synchronization. Phase 95 targets the original development repository and, when requested, the installed Codex skill only.

The principle is: extend existing routes first, add new commands only when an existing route cannot express the missing gate.

## 4. Development Direction A0: Formal Host Operating Constitution

### Problem

The current entry documents already contain strong formal-route rules, but they still read partly like a project manual and command map. A capable host agent can see many directories, command names, and route details, then decide it is faster to hand-write artifacts from memory. This does not mean the detailed documents are wrong; it means they should not be the ordinary operating surface for formal host work.

### Design Principle

Do not rely on hiding information for safety. Instead, make the first visible contract say:

```text
For formal artifacts, the host agent's job is to obey the CLI task loop.
The current task package is the runtime source of truth.
Project structure documents are maintenance references, not permission to bypass the task loop.
```

### Minimal Improvement

Add or refactor a short host-facing constitution layer:

1. Add `references/formal-host-operating-constitution.md`, or create an equivalent top section in existing entry docs.
2. Move the first-entry emphasis in `SKILL.md` and `AGENTS.md` toward:
   - formal work starts with `workflow-dashboard` or `task-next`;
   - `task-open` is the concrete runtime instruction package;
   - the platform agent may write only the expected outputs for the current task;
   - direct file edits to formal artifacts are exploratory unless the CLI task package authorizes them;
   - low-level commands are route internals unless issued by the task registry;
   - sidecars are executable work, not completed work;
   - debug/bypass flags are unavailable to formal hosts;
   - subagents cannot write body prose.
3. Keep detailed project structure, route maps, schemas, and implementation history in developer-facing references.
4. Do not delete structure documentation. The goal is entry-point prioritization, not obscurity.
5. Ensure `agentread.yaml` still supports maintainers and advanced agents, but its route details should not contradict the constitution.

Expected documentation outputs:

- `references/formal-host-operating-constitution.md`;
- a shorter first-entry section in `SKILL.md`;
- a shorter first-entry section in `AGENTS.md`;
- optional pointers from `agentread.yaml` without expanding this into another route map.

### Acceptance

- A newly loaded host agent can identify the mandatory formal loop without reading the whole repository.
- The entry docs no longer encourage treating the repository as a free-form file map.
- Detailed maintenance docs remain available for debugging, implementation, and architecture review.
- No CLI behavior changes are required for this subtask.

## 5. Development Direction A: CLI Operating Surface Convergence

### Problem

The state machine exists, but a host agent may still see many commands and choose a shortcut. The project already warns against this, yet the command surface still looks like a toolbox instead of one controlled operating loop.

### Minimal Improvement

Do not rewrite the task registry. Instead:

1. Document one preferred formal operator loop in a short maintenance guide:
   - `workflow-dashboard` for overview;
   - `task-next` for the next formal action;
   - `task-open` for the platform-agent task package;
   - platform agent writes only expected outputs;
   - `task-submit`;
   - `task-complete`;
   - `workflow-advance` or dashboard refresh.
2. Mark low-level commands as route internals in help text or docs where practical.
3. Consider adding a light `doctor` or `status` alias only if it wraps existing `workflow-dashboard`, `workflow-validate`, and `route-audit`; it should not create new state.
4. In CLI help and route docs, distinguish command classes:
   - formal loop commands: `workflow-dashboard`, `task-next`, `task-open`, `task-submit`, `task-complete`, `workflow-advance`;
   - diagnostic commands: `workflow-state`, `workflow-validate`, `agent-task-status`, `route-audit`, `workflow-events`;
   - route-internal commands: `context`, `simulate-scene`, `branch-simulate`, `compose-scene`, `generate-scene`, `agent-review-scene`, `state-evolve`, `canon-evolve` after it exists;
   - legacy/debug commands: local provider, `director-chat`, and regression-only bypass paths.

### State Authority Hierarchy

Make the formal authority order explicit in docs, help text, and later task packages:

1. `task-open` is the current executable instruction package for a formal task.
2. `task-complete` is the task-level completion gate for expected outputs and deep current-state checks.
3. `route-audit` is the route-level pass/fail ledger, especially before promotion, chapter readiness, export, or release.
4. `workflow-dashboard` is the read-only cockpit that gathers route state, route audits, sidecar status, and recent events.
5. `workflow-state` is a navigation summary, not sufficient proof that a formal route is clean.
6. low-level route commands are implementation helpers unless selected by the current task package or a maintainer debugging the skill.

This hierarchy matters because an agent that sees `workflow-state` saying "next step" may otherwise treat that output as equivalent to route readiness. It is not. Formal readiness must be proven through task completion and route audit.

### Acceptance

- A maintainer or host agent can identify the next formal action without reading the whole route map.
- No new state source is introduced.
- Existing route tests still pass.

## 6. Development Direction B: Canon-Evolve Candidate Path

### Problem

Canon is already a hard constraint and release gate. However, scene-generated world facts are not forced into a per-scene canon writeback candidate path. `state-evolve` handles character state, but explicitly does not write canon.

### Minimal Improvement

Add a small canon candidate evolution path, parallel to `state-evolve`, not a full canon database rewrite.

Proposed first version:

```text
canon-evolve <project> --scene <scene_id> --source <draft-or-candidate>
```

It should write:

- `canon/patches/{scene_id}_canon_patch.agent_tasks.md`
- `canon/patches/{scene_id}_canon_patch.json`
- `canon/patches/{scene_id}_canon_patch.md`

The platform agent fills the patch. The CLI only prepares the task and validates structure.

Suggested patch categories:

- new world rule candidate;
- location detail candidate;
- organization detail candidate;
- timeline/history fact candidate;
- foreshadowing fact candidate;
- terminology candidate;
- contradiction or unclear fact;
- user-confirmation-required item.

Formal writeback should not directly edit `canon/`. The first implementation can require review and approval, then reuse or extend existing asset promotion mechanics where possible.

### Minimal Candidate Contract

The first implementation should keep the JSON small and reviewable. A suggested shape:

```json
{
  "schema": "canon_patch.v1",
  "scene_id": "scene_0001",
  "source_path": "drafts/candidates/scene_0001.md",
  "canon_change": "true",
  "no_canon_change_reason": "",
  "items": [
    {
      "id": "canon_patch_item_001",
      "category": "location_detail",
      "claim": "",
      "evidence_quote": "",
      "evidence_location": "",
      "target_asset_type": "location",
      "target_asset_id": "",
      "durability": "one_off | recurring | structural",
      "confidence": "low | medium | high",
      "risk": "none | contradiction | scope_unclear | needs_user_choice",
      "recommended_route": "no_writeback | asset_candidate | canon_review | user_decision"
    }
  ],
  "agent_review": {
    "reviewer": "platform-agent",
    "conclusion": "pending | pass | revise_required | blocked",
    "notes": []
  }
}
```

Keep exact field names flexible during implementation if existing schema conventions suggest a better local pattern, but preserve the contract semantics: source evidence, durability, risk, recommended route, and no direct canon mutation.

### Boundary With Existing Asset Workflow

`canon-evolve` must not become a second worldbuilding asset system. Its job is narrower:

1. detect or collect canon-relevant facts introduced by a scene;
2. package them as a reviewable candidate patch;
3. point to the existing candidate asset / review / approval / promotion mechanisms when the patch requires formal world, location, organization, timeline, terminology, or foreshadowing updates.

The existing `character-and-world-assets` route remains the formal promotion path for durable world assets. `canon-evolve` is the scene-local extraction and routing step.

### Trigger Rules

Avoid both extremes: do not run a heavy canon patch for every scene by default, and do not leave canon change detection to agent memory.

Recommended trigger contract:

1. Every formal scene candidate or promotion manifest records `canon_change` as one of `true`, `false`, or `unknown`.
2. If `canon_change=false`, the manifest must include `no_canon_change_reason`.
3. If `canon_change=true`, `canon-evolve` must create a candidate patch or route to an existing candidate asset task.
4. If `canon_change=unknown`, AgentReview or route-audit treats the scene as blocked for chapter/export readiness until resolved.
5. AgentReview can override a false declaration when it finds new world rules, location facts, organization facts, historical facts, terminology, foreshadowing facts, or contradiction risks in the prose.
6. `route-audit --route scene-development` should pass only when each scene has either a completed canon patch path, an approved route to asset promotion, or an explicit `no_canon_change` record.

### Gate Severity

Use a staged severity model so old projects remain usable while new formal work becomes harder:

- `missing`: warning for untouched legacy scenes, blocking for newly generated or re-promoted scenes.
- `unknown`: blocking for strict longform, chapter readiness, export readiness, or any scene touched after Phase 95.
- `false_without_reason`: blocking once the declaration field exists.
- `true_without_patch`: blocking for promotion readiness and export readiness.
- `patch_pending`: warning during active scene work, blocking before chapter/export.
- `patch_blocked_or_user_choice`: blocking until user choice or candidate asset route is recorded.
- `patch_pass_no_writeback`: pass only when the patch explains why introduced facts are local, non-durable, or already covered.

### Compatibility

Existing projects must not all become blocked on day one.

1. Before Phase 95 adoption, missing canon-change declarations should be warnings.
2. New formal scenes generated after the feature is available should treat missing declarations as blocking.
3. Longform chapters that opt into strict Phase 95 route gates should require the declaration for every included scene.
4. Export readiness should remain compatible with older projects unless a scene is otherwise touched, regenerated, or formally re-promoted.

### Route Integration

Use the existing `scene-development` and `review-and-audit` routes:

1. after `state-evolve`, emit or require a canon-evolve status when scene text contains world/canon writeback candidates;
2. `route-audit --route scene-development` reports unresolved canon patches as blocking for chapter/export only when the scene introduced canon-relevant facts;
3. `review-and-audit` includes unresolved canon patches in canon review evidence.

### Acceptance

- A scene can no longer introduce persistent world facts only inside prose without at least a candidate patch or explicit no-canon-change statement.
- `canon-evolve` does not directly mutate `canon/`.
- Existing `canon-lint` and `agent-canon-review` remain project-level review gates.
- Existing candidate asset promotion remains the durable worldbuilding promotion path.

## 7. Development Direction C: Narrative Rhythm And Scene Bridge Controls

### Problem

Reader Experience Contract already handles reader questions, promised reward, withheld information, payoff/delay, tension source, anti-summary, and aftertaste. What is still under-specified is prose-level scene rhythm and scene-to-scene bridge continuity.

### Minimal Improvement

Do not add a large new route. Extend existing scene planning, composition, generation, and review artifacts with a compact narrative-rhythm block.

Suggested fields:

```yaml
narrative_rhythm:
  rhythm_role: "transition | conflict | information | emotional | action | reversal | aftermath"
  pace_plan: "fast | slow | fast_to_slow | slow_to_fast | layered"
  density_mix:
    dialogue: "low | medium | high"
    action: "low | medium | high"
    exposition: "low | medium | high"
    interiority: "low | medium | high"
  scene_turn: ""
  compression_rule: ""
  expansion_rule: ""

scene_bridge:
  incoming_pressure: []
  outgoing_hooks: []
  unresolved_reader_questions: []
  next_scene_load: ""
```

### Generation And Review Semantics

These fields should not become decorative metadata. They should drive concrete task behavior:

- `rhythm_role` tells the writing agent what this scene is for. A transition scene can be short and clean; an aftermath scene can slow down; an action scene should not be padded with explanatory psychology.
- `pace_plan` controls paragraph length, dialogue/action ratio, compression, and where the prose may linger.
- `scene_turn` must identify the irreversible change in the scene. If no turn exists, the scene is probably summary, setup-only, or should merge with a neighboring scene.
- `compression_rule` names what must be summarized quickly so the scene does not bloat.
- `expansion_rule` names what deserves page time because it carries plot, character, theme, or reader-payoff load.
- `incoming_pressure` explains why this scene starts now instead of floating independently.
- `outgoing_hooks` and `next_scene_load` explain what pressure the next scene inherits.

AgentReview should not merely ask whether the fields are present. It should ask whether the prose obeys them. A scene can fail rhythm/bridge review when it has the right labels but reads as flat summary, unearned climax, disconnected vignette, or repeated tempo.

### Existing Places To Extend

1. `chapter-obligation` already has inherited hooks and ending hooks. Reuse it.
2. `compose-scene` should include `narrative_rhythm` and `scene_bridge` in the composition packet.
3. `generate-scene` should inject these fields into the platform-agent task and prompt manifest.
4. `agent-review-scene` should ask whether the prose followed the intended rhythm and connected to previous/next scene pressure.
5. `chapter-workspace` or `longform-audit` can summarize repeated rhythm roles and weak bridges.

### Duplication Boundary

Do not duplicate Reader Experience fields. Phase 95 rhythm/bridge fields should cover only what the existing contract does not:

- prose tempo and compression/expansion;
- scene-level turn;
- incoming pressure from the previous scene;
- outgoing load for the next scene;
- repeated rhythm-pattern detection at chapter level.

Reader question, promised reward, withheld information, payoff/delay, tension source, and aftertaste should remain in the existing Reader Experience / Chapter Obligation structures.

### Compatibility

1. Existing projects without rhythm fields should not fail immediately.
2. New strict longform scenes should require the fields once the route supports them.
3. Short exploratory scenes may keep rhythm fields optional.
4. Review should treat missing rhythm/bridge as blocking only when the current route declares strict longform or formal chapter production.

### Anti-Overdesign Rule

Do not add a separate "literary quality scoring engine" for this. The useful gate is qualitative and task-local:

1. does this scene have a clear function and turn;
2. does the prose spend words where the scene contract says words matter;
3. does it compress connective tissue without turning into synopsis;
4. does it hand the next scene a concrete unresolved pressure.

This keeps the mechanism close to composition, generation, and review rather than creating another abstract score that agents can satisfy mechanically.

### Acceptance

- The mechanism prevents flat scene pacing without requiring a separate "rhythm route".
- Review can block scenes that ignore required bridge or rhythm goals.
- It does not force every scene into high drama; transition and aftermath are valid rhythm roles.

## 8. Development Direction D: Generation Task Strengthening

### Problem

The project has strong generation constraints already, but the highest-risk tasks still benefit from more exact prompt assets instead of route-level wildcard prompts.

### Minimal Improvement

Prioritize exact prompt assets only for:

1. prose generation;
2. scene review;
3. revision;
4. canon-evolve;
5. style prompt execution.

These assets should not duplicate all docs. They should present the active task package:

- allowed sources;
- forbidden shortcuts;
- word-count contract;
- mounted style priority;
- punctuation and anti-AI-style constraints;
- reader experience;
- narrative rhythm and bridge when present;
- expected output format.

### Prompt Asset Priority

Exact prompt assets should be added only when a task can fail in a way that route-level prompts cannot prevent. The priority order is:

1. `scene-development.prose.generate`: highest risk because this produces body text and must combine canon, style, word budget, reader contract, rhythm, bridge, new-character policy, and anti-AI prose constraints.
2. `scene-development.review.agent`: high risk because review must block exact-candidate failures instead of giving generic notes.
3. `scene-development.revision`: high risk because it can evade Style Lint by substituting a different bad pattern.
4. `scene-development.canon-evolve`: new high-risk route because it decides whether prose facts become candidate canon.
5. `style-engineering.prompt`: medium-high risk because vague style prompts weaken every downstream scene.

Do not create exact prompt assets for every route step in this phase. Too many assets will become another maintenance surface.

### Acceptance

- `prompt-registry-validate` passes.
- `task-open` shows a task-specific prompt asset for the most failure-prone task types.
- The prompt asset remains concise enough that the task package, not the global documentation, controls execution.

## 9. Development Direction E: Frontend As Display And Human Choice Surface

### Current State

Frontend planning and partial implementation already exist for:

- project library display;
- wrapped JSON/Markdown presentation;
- completed prose display;
- user notes and low-risk structured interaction direction.

### Minimal Next Work

Only extend frontend where it supports the CLI state machine:

1. show unresolved canon patches when Direction B exists;
2. show narrative rhythm and scene bridge cards when Direction C exists;
3. expose branch/style/asset/release choices as structured records, not direct file edits;
4. keep completed prose as a main reading module.

### Frontend Boundary

The frontend may display and collect structured human choices, but it should not become an editor of record for formal artifacts in Phase 95. Preferred interaction pattern:

1. frontend reads CLI/dashboard/project evidence;
2. frontend renders it as human-friendly cards, prose panes, branch cards, canon patch cards, and rhythm/bridge cards;
3. user choice is saved as a structured note, approval, or decision artifact;
4. the CLI task loop consumes that artifact through the normal route.

Avoid direct freeform editing of `canon/`, `characters/`, `drafts/scenes/`, release manifests, or route completion markers from the frontend.

### Deferred

- direct canon editing;
- direct formal draft editing;
- frontend-owned workflow progress;
- large visual rewrite not tied to current route evidence.

## 10. Development Direction F: Regression Tests

Add tests only for new or tightened behavior:

1. `canon-evolve` writes sidecar and candidate patch, but does not mutate `canon/`.
2. route audit reports unresolved canon patch when a scene declares `canon_change=true`.
3. route audit blocks `canon_change=unknown` for strict formal chapter/export readiness.
4. route audit accepts `canon_change=false` only when `no_canon_change_reason` exists.
5. AgentReview can override a false no-change declaration when it identifies new canon facts.
6. `canon-evolve` routes durable world/location/organization updates toward the existing asset workflow rather than directly promoting them.
7. narrative rhythm fields are included in composition and generation task packages.
8. AgentReview can mark rhythm/bridge failure as blocking in strict formal longform mode.
9. old projects without rhythm/bridge fields remain warning-compatible until touched or strict mode is declared.
10. prompt registry validates any new exact prompt assets.
11. existing scene-development, longform-planning, review-and-audit, export-and-release route tests remain green.

Do not add broad tests for mechanisms already covered unless the code changes touch them.

## 11. Suggested Implementation Order

### Step 1: Documentation And Audit

Create this convergence document and keep it linked from roadmap or implementation README only after the user approves. No behavior change.

### Step 2: Host Operating Constitution

Refactor the host-facing entry layer so formal hosts see the operating constitution before the detailed map. This is documentation-only, unless help text is later adjusted.

### Step 3: CLI Help Classification

Update docs and, if practical, CLI help text so formal-loop, diagnostic, route-internal, and legacy/debug commands are visibly distinct. Do not rename commands yet.

### Step 4: State Authority And Dashboard Messaging

Make `workflow-state`, `workflow-dashboard`, `task-open`, `task-complete`, and `route-audit` messaging consistent with the authority hierarchy. This is a small but important bridge before adding more gates: agents must understand which output is navigation, which output is executable task instruction, and which output is formal pass/fail evidence.

### Step 5: Canon-Evolve Minimal Path

Implement `canon-evolve` as a sidecar/candidate generator. Add schema and tests. Do not apply patches automatically.

### Step 6: Canon Trigger And Compatibility Gates

Add `canon_change` / `no_canon_change_reason` handling and route-audit compatibility behavior before making canon patches blocking for strict formal scenes.

### Step 7: Rhythm And Bridge Field Injection

Extend existing `chapter-obligation`, `compose-scene`, `generate-scene`, and `agent-review-scene` artifacts with compact fields. Avoid creating a new route.

### Step 8: Exact Prompt Assets For High-Risk Tasks

Add exact prompt assets for generation/review/revision/canon-evolve only if the task packages remain too generic after Step 3.

### Step 9: Frontend Display Hooks

Show canon patches and rhythm/bridge summaries in the existing project library/dashboard. Do not create a new frontend workflow engine.

### Step 10: Development/Install Sync Only

If the user requests installation after implementation, sync the original installed Codex skill. Do not sync the contest package as part of Phase 95.

## 12. Out-Of-Scope Until Needed

These ideas remain valid but should wait:

- distributed batch queue with leases and retry policy;
- full "hide all project structure from host agent" documentation rewrite;
- global command renaming;
- Dify/LangGraph production orchestration upgrade;
- full frontend editor for canon/characters/plot;
- automatic literary quality scoring beyond existing review tasks.
- contest package rebuild or SkillHub submission work.

## 13. Success Definition

Phase 95 is successful if:

1. host-facing entry docs behave like an operating constitution instead of a free-form project map;
2. formal host agents have fewer reasons to choose shortcuts over the task loop;
3. scene-created world facts become reviewable canon candidates instead of hidden prose facts;
4. scene drafting carries explicit rhythm and bridge requirements;
5. existing Reader Experience, Word Budget, Prompt Registry, Context Trace, Review, Promotion, and Export gates are reused rather than duplicated;
6. the change set remains small enough to verify with focused unit tests plus the existing suite.
