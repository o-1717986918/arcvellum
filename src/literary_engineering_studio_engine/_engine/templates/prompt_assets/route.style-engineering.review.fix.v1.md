---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.style-engineering.review.fix.v1
match: route.style-engineering.review.fix.v1
version: v1
route: style-engineering
task_type: platform-agent-revision
title: Repair Rejected Style Evidence
required_inputs:
  - rejected independent review
  - current style prompt and candidate
  - deterministic score evidence
context_groups:
  - required changes
  - prompt repair
  - evaluation candidate repair
hard_constraints:
  - Repair every required change without editing score or review evidence.
  - Invalidate the previous generation or score evidence.
  - Keep the prompt within the formal 500-2500 Chinese-content character contract.
output_contract:
  - Revise only the declared prompt and evaluation candidate artifacts.
review_requirements:
  - A fresh deterministic evaluation and independent review must follow.
forbidden_shortcuts:
  - Do not relabel the old review as pass.
  - Do not copy reference phrases to improve similarity.
---

# Repair Style Evidence

Revise the executable style prompt and evaluation candidate against every independent-review finding. Preserve the literary mechanism while removing vagueness, metric gaming, copy risk, and unusable instructions. End with deliberately stale evaluation evidence so the state machine must score and review the new version.
