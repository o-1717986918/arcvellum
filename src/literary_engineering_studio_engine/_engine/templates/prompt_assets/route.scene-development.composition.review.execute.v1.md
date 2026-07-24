---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.composition.review.execute.v1
match: route.scene-development.composition.review.execute.v1
version: v1
route: scene-development
task_type: main-platform-agent-composition-review
required_inputs:
  - CLI-generated composition packet and sidecar
  - formal branch selection and context trace
  - chapter obligation, word budget, rhythm, reader-experience and mounted style constraints
context_groups:
  - composition contract
  - selected branch and roleplay evidence
  - narrative rhythm and bridge
  - reader experience and chapter obligation
  - style generation constraints
hard_constraints:
  - Review the existing composition package; do not rewrite the package or draft prose.
  - The composition review JSON begins as a deliberately invalid pending scaffold and must be replaced with a real typed conclusion.
  - Preserve source identity and digest fields already supplied by the CLI.
  - A pass requires concrete evidence, complete status, pass verdict, no required changes, and generation readiness.
style_constraints:
  - Treat mounted style and punctuation constraints as generation inputs, not optional polish.
output_contract:
  - Write only the composition review JSON at the declared path. Studio materializes the lifecycle receipt after deterministic preflight succeeds.
review_requirements:
  - Verify branch provenance, beat inventory, character causality, rhythm, bridge, reader contract, word budget and mounted style before allowing prose.
  - Every finding must be concrete enough to guide the following prose task or a revision task.
forbidden_shortcuts:
  - Do not leave pending_agent_judgment or pending in the final JSON.
  - Do not use a completion receipt as a substitute for the review verdict.
  - Do not declare pass to bypass an unresolved composition defect.
---

# Composition Review

Audit the CLI-created composition packet before prose generation. This is an editorial decision task, not a composition-writing task: read the packet, its sidecar and the declared scene contracts; then use the exact JSON contract embedded in the Studio Worker Program to record an evidence-backed conclusion.

When the packet is ready, make the review explicitly pass and expose the constraints the prose writer must preserve. When it is not ready, identify the smallest concrete changes needed and do not claim generation readiness.
