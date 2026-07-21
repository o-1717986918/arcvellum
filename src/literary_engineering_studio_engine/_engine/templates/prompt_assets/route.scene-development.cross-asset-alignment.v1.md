---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.cross-asset-alignment.v1
match: route.scene-development.cross-asset-alignment.v1
version: v1
route: scene-development
task_type: human-approval-boundary
title: Cross-Asset Alignment Decision
required_inputs:
  - exact prose candidate
  - exact AgentReview record
  - formal asset named by the review
context_groups:
  - candidate evidence
  - formal asset boundary
  - available decision options
hard_constraints:
  - This is a human decision boundary, not an Agent writing or review task.
  - Do not revise prose or alter canon or character assets while making the decision.
  - Bind the selected option to the exact scene id and candidate SHA-256.
output_contract:
  - Record one offered option through the Studio decision interface; do not create a substitute file.
review_requirements:
  - Aligning prose requires a fresh candidate revision and exact-candidate review before promotion.
  - Holding for asset revision requires the formal asset route and a fresh scene review after the asset changes.
forbidden_shortcuts:
  - Do not treat a generic revision direction as this cross-asset decision.
  - Do not make a silent choice on behalf of the user.
---

# Cross-Asset Alignment

The review found a conflict between the exact prose candidate and a formal project asset. Choose one offered option deliberately:

1. Align the prose to the existing formal asset. The next task will revise only the prose, then require a new review.
2. Hold for formal asset revision. The project must revise that asset through its own route before the scene can continue.

This boundary preserves authorship and canon authority. It is complete only when the Studio records the selected option for this exact candidate.
