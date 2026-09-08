# Lean Kernel v2 K1 Domain Contracts Change Packet

Status: implemented

## Objective

Introduce the pure scene-transaction domain vocabulary required by the lean literary kernel without changing any production route, worker, API, or user-project behavior.

## Inputs

- `SceneFacts` remains the canonical scene fact projection.
- Existing Studio `SceneRiskProfile` remains the risk scoring implementation during K1.
- Style, rhythm, reader, and word-budget systems provide already-resolved values to the pure builder; K1 performs no file reads.
- `arcvellum-lean-literary-kernel-v2-design.md` is the controlling architecture document.

## Outputs

- Immutable, JSON-safe contracts for `SceneBrief`, `CreativeResult`, `SceneDelta`, reviews, verification, and transaction state.
- A compatibility mapping from `compact/standard/deep` to `low/standard/high`.
- A deterministic policy matrix deciding review, decision-trace, revision, and approval depth.
- Pure brief construction, output verification, and commit-plan construction.

## Allowed dependencies

- Python standard library.
- `literary.scene.facts.SceneFacts`.
- Existing pure text-counting utility from `foundation.draft_text`.

The Engine transaction package must not import Studio orchestration, persistence, API, frontend, worker, CLI, or filesystem loaders.

## Explicit exclusions

- No production controller wiring.
- No model or Pi Worker invocation.
- No filesystem or SQLite writes.
- No changes to `workflow/state_scene.py` or `routes/scene/*`.
- No deletion or weakening of the `strict-v1` route.

## Rollback point

Remove `literary/scene/transaction/` and its K1 tests. No existing production code consumes the package in K1.

## Verification

- Contract construction and serialization.
- Risk compatibility and policy matrix.
- Soft length warnings versus hard deterministic failures.
- SceneDelta reference checks.
- Commit-plan refusal before required review or successful verification.
- Existing strict-v1 characterization remains green.

## Result

K1 adds one cohesive domain package. It deliberately avoids a second risk scorer and leaves current production behavior untouched, giving K2 a stable interface for application-service and repository adapters.
