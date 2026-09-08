# K5B: Opt-In Autopilot Wiring

## Purpose

Allow the existing durable Autopilot controller to advance lean scene
transactions while retaining strict-v1 as the production default.

## Production Semantic Change

`DelegationPolicy.literary_kernel=lean-v2` redirects only the
`scene-development` route. Every other route, lease, project lock, pause,
release, and decision behavior stays on the existing controller.

Each loop advances one transaction state. Model work is limited to create,
risk-triggered review, and one revision. Chapter checkpoints run before the
next chapter starts. Runtime artifacts remain below the Studio data root.

## Boundaries

- Reuse the existing SQLite scene repository and Pi conversation transport.
- Do not add a task registry, generic DAG, compatibility sidecar, or direct
  character/Canon mutation.
- A high-risk commit without delegated approval pauses.
- A blocking chapter checkpoint pauses with preserved outputs.
- `strict-v1` remains the default until K6 exit evidence passes.

## Verification

- Policy normalization is backward compatible.
- The coordinator proves a complete low-risk scene, standard review, one
  revision, chapter checkpoint, and route completion with fake runtimes.
- ClaimedRunLoop dispatches to the lean host only when explicitly enabled.
- Existing strict-v1 Autopilot tests remain untouched.
