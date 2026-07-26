---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.source-ingest.reconstruct-project.v1
match: route.source-ingest.reconstruct-project.v1
version: v1
route: source-ingest
task_type: platform-agent-archaeology-reconstruction
title: Evidence-Bound Candidate Project Reconstruction
required_inputs:
  - source manifest and declared product mode
  - ready aggregate
  - completed identity resolution
context_groups:
  - project summary
  - character world and plot candidates
  - style and promise observations
  - unresolved alternatives
hard_constraints:
  - Reconstruct candidates rather than declaring recovered truth.
  - Keep every material claim bound to current evidence.
  - Use only registered Archive asset types and their schemas.
  - Analysis mode cannot recommend promotion.
style_constraints:
  - Abstract reusable craft constraints and do not promise exact imitation of protected work.
output_contract:
  - Write one typed reconstruction candidate JSON and one readable report.
review_requirements:
  - Every asset carries evidence confidence unresolved refs and a promotion recommendation.
forbidden_shortcuts:
  - Do not flatten contradictions omit unknowns or write formal project assets.
---

# Project Archaeology Reconstruction

Build a useful candidate project without pretending that interpretation is certainty.
