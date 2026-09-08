# Lean Kernel v2 K6 Compatibility and Retirement Inventory

## Decision

K6 does not delete `strict-v1`, historical task readers, or adaptive
orchestration modules. Lean-v2 remains a preview because the structural A/B
gate passed while the blind literary non-inferiority gate has no accepted
scorecard. The packaged compatibility manifest therefore recommends
`strict-v1` for both new and legacy projects.

## Compatibility surface

| Surface | Current owner | K6 disposition |
|---|---|---|
| Project kernel selection | Studio compatibility manifest and policy service | Keep; explicit migration and rollback |
| Historical scene route | Embedded Engine `workflow/state_scene.py` and `routes/scene/*` | Keep as `strict-v1` |
| Historical task protocol | Engine task packages and Studio worker transport | Keep for strict-v1 and non-scene routes |
| Lean scene transaction | Engine public literary facade plus Studio application service | Preview, opt-in |
| Creative-live projection | Studio transaction events and existing SSE projection | Keep; supports both kernels |
| CLI diagnostics | Studio `scene-transaction-*` adapter | Keep; uses production services |

No compatibility path writes placeholder sidecars for work that lean-v2 did
not execute. Migration changes only the persisted project policy.

## Orchestration consumer audit

The Studio orchestration package currently contains 51 Python modules,
including its package facade. Direct production consumers found in this K6
audit are:

| Consumer | Imported capability |
|---|---|
| `automation/controller.py`, `api_server.py` | orchestration settings |
| `automation/campaign_runtime.py` | campaign, checkpoint and progress contracts |
| `automation/run_result_handler.py`, `automation/no_progress.py` | bounded recovery policy |
| `automation/lean_scene_loop.py` | chapter planning facts reader |
| `application/chapter_checkpoint.py` | chapter planning facts contracts |
| `infrastructure/project_scene_transactions.py` | scene risk profile |
| `runtime/worker.py` | active plan, chapter policy, project fingerprint and scene binding |
| `runtime/bundle_executor.py` | execution bundles |
| `runtime/context_ledger.py` | truth partitions |
| persistence plan repositories | creative-plan event contracts |
| strategy and capability projections | orchestration settings |

`orchestration/__init__.py` eagerly re-exports much of the package. Import
reachability through that facade is therefore not proof of a real production
consumer. Planner, reviewer, normalizer, compiler, simulator, constitution,
shadow, and related planning modules remain held for compatibility and
experimentation; K6 does not assert that they are safe to delete.

## Retirement ledger

| Candidate family | Confirmed zero-consumer releases | Required hold | Deletion now allowed |
|---|---:|---:|---:|
| `strict-v1` scene route | 0 | 2 | No |
| Historical scene sidecar readers | 0 | 2 | No |
| Adaptive orchestration shadow/planner family | 0 | 2 | No |

A future deletion change must first replace eager facade imports with explicit
consumer evidence, observe two released versions, name every removed import,
command and fixture, and provide a user migration path. This inventory is the
initial observation, not the first zero-consumer release.

## Structural evidence

The K5 A/B fixture records the expected simplification for a comparable
standard scene:

- Agent calls: 8 to 2.
- User-visible workflow states: 31 to 5.
- Project-local Agent task files: 8 to 0.
- Machine-owned metadata remains post-processed by Studio.
- Strict-v1 remains the default until literary blind review is accepted.

## Rollback

An operator can pause Autopilot and select `strict-v1` through the same policy
API or frontend selector. Project files do not require reverse migration,
because lean-v2 writes only committed project artifacts plus its scene commit
receipt and keeps transient transaction data in Studio storage.
