---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.state-evolve.execute.v1
match: route.scene-development.state-evolve.execute.v1
version: v1
route: scene-development
task_type: platform-agent-review
title: State Patch Evidence Review
required_inputs:
  - CLI-generated state patch JSON and state-evolve sidecar
  - exact scene, context packet and context trace
  - source prose or composition evidence named by the state patch
context_groups:
  - state-patch candidate
  - scene and character causality
  - explicit prose/composition evidence
  - approval boundary
hard_constraints:
  - Review the existing state patch; do not apply it or modify character files.
  - The state review JSON begins as a deliberately invalid pending scaffold and must be replaced with a typed evidence-backed conclusion.
  - Preserve source identity and digest fields already supplied by the CLI.
  - A pass requires complete status, pass verdict, approve recommendation, non-empty evidence and findings, and no required changes.
style_constraints:
  - Treat background story as a behavioral constraint, never as an unverified on-page fact.
output_contract:
  - Write only the state patch review JSON at the declared path. Studio materializes the lifecycle receipt after deterministic preflight succeeds.
review_requirements:
  - Verify every proposed character, relationship and arc change against the exact source artifact.
  - A pass may contain only changes that visibly occurred in the exact scene prose. A future intention or explicitly not-yet-realized turn must be returned for reclassification as next_scene_inputs, not approved as state.
  - Check that the patch does not smuggle Canon, plot or unregistered persistent characters into character state.
  - Record a concrete finding even when the patch is approved; do not use an empty approval.
forbidden_shortcuts:
  - Do not leave pending_agent_judgment or pending in the final JSON.
  - Do not create or edit an agent_completion marker.
  - Do not declare pass to bypass missing prose evidence or an unresolved state conflict.
---

# State Patch Review

This is a bounded editorial review, not a state-writing task. Read the CLI-generated patch, its sidecar and the declared scene evidence. Then replace the pending JSON scaffold with the exact conclusion described by the Studio Worker Program.

When the patch is defensible, approve it only as a candidate for the later human approval boundary. When it is not defensible, state precisely what evidence or patch change is required. Do not apply any state in this task.
