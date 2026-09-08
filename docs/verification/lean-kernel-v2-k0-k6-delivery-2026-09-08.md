# Lean Kernel v2 K0-K6 Delivery Report

## Delivery status

The implementation objective is complete. Lean-v2 is an opt-in production
preview with strict-v1 rollback. It is deliberately not the default because
the blind literary non-inferiority evidence required by the architecture has
not yet been accepted.

## Delivered capability

- One recoverable `SceneTransaction` owns prepare, create, verify, conditional
  review, one bounded revision and atomic commit.
- Low, standard and high-risk policies change semantic work without weakening
  sandbox, locked fact, Canon or commit protection.
- Pi Worker receives a bounded scene brief and returns prose plus semantic
  delta; Studio supplies protocol metadata after model output.
- Character state, Canon candidates, continuity, promises, reader questions
  and handoff enter one validated commit plan.
- Chapter checkpoints aggregate cross-scene rhythm, length, continuity and
  reader obligations.
- Autopilot advances one transaction state at a time and exposes meaningful
  scene events, prose previews and committed output through Creative Live.
- Project policy, API, CLI and frontend support explicit lean-v2 selection,
  migration and strict-v1 rollback.
- Runtime codec, CLI adapter, policy service and Autopilot host are separate
  modules; Studio reaches Engine literary internals only through the public
  facade.

## Measured structural result

The committed K5 A/B fixture reports:

| Metric | strict-v1 | lean-v2 |
|---|---:|---:|
| Agent calls per standard scene | 8 | 2 |
| User-visible workflow states | 31 | 5 |
| Project-local Agent task files | 8 | 0 |

The blind literary scorecard is absent, so `ready_for_default=false`. Structural
savings do not substitute for prose quality evidence.

A final live `runner-probe` reached the embedded Pi Worker, selected
`deepseek/deepseek-v4-pro`, opened a provider request and received HTTP 402
`Insufficient Balance`. The worker process, model selection and event stream
were available; model output and the literary A/B remain externally blocked.

## Verification

Passed during final closure:

- all 41 `test_lean_kernel_v2*` tests;
- Creative Live API, contract, projection and routing suites;
- exact kernel migration API test;
- full Autopilot suite after compatibility-export repair;
- Studio-to-Engine dependency-direction tests;
- Pi Worker build and 93 tests;
- Vue typecheck and five Autopilot panel tests;
- frontend production build and desktop asset synchronization;
- OpenAPI export and generated TypeScript contract check;
- `compileall` and `git diff --check` for the changed modules.

One full Python discovery run was completed. It exposed a controller
compatibility import, which was fixed and reverified. Its remaining failing
assertion is the repository architecture-baseline test caused by four files
that were already modified outside this objective before K6 closure:

- `src/literary_engineering_studio/preflight/scene.py`;
- `src/literary_engineering_studio_engine/routes/scene/blueprints.py`;
- `src/literary_engineering_studio_engine/workflow/state_scene.py`;
- the corresponding oversized `_blueprint_for_state` function.

The K0-K6 changes add no remaining architecture-audit violation. Those
pre-existing worktree changes were preserved rather than overwritten.

## Operational decision

- New and existing projects continue to resolve to `strict-v1` unless the user
  explicitly selects lean-v2.
- A running Autopilot session must be paused before migration.
- Rollback changes policy only and does not rewrite project files.
- Compatibility and shadow code cannot be deleted until two released versions
  record zero consumers and a dedicated removal review passes.
- Default adoption requires a same-model blind literary A/B scorecard meeting
  the non-inferiority gate.

## Commit trail

- `056009e` K0 baseline;
- `8c7345d` K1 domain contracts;
- `290df60` K2 application service and recovery;
- `381587a` K3 Pi runtime;
- `5cd4c8a` K4 chapter checkpoint;
- `99e4510`, `ccf79b2`, `2ce47b0` project, Autopilot and Creative Live wiring;
- `f4ad633` A/B evidence gate;
- `fd3dc27` K6 compatibility surface;
- `ab71f31`, `76666b8` architecture closure and compatibility repair.
