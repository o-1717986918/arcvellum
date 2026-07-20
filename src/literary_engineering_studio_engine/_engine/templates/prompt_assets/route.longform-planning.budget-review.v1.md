---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.longform-planning.budget-review.v1
match: route.longform-planning.budget-review.v1
version: v1
route: longform-planning
task_type: platform-agent-budget-review
title: Longform Budget Review Exact Prompt Asset
required_inputs:
  - project scale target
  - word budget json and report
  - volume chapter and scene inventory
context_groups:
  - target Han-character count
  - narrative time span
  - genre density
  - event inventory
hard_constraints:
  - Judge whether event inventory can support target length without padding.
  - Use Han-character targets and the configured machine-character mapping consistently.
  - Identify chapter scene and subplot debt before prose generation.
style_constraints:
  - Do not propose adjective inflation repeated introspection or recap as expansion.
output_contract:
  - Write budget review findings and expansion actions at declared paths.
review_requirements:
  - Totals reconcile from project to volume chapter and scene levels.
forbidden_shortcuts:
  - Do not accept a short-novella inventory for a long-novel target.
---

# Longform Budget Review

Audit length as narrative inventory. Expansion must add choices, consequences, relationships, investigations, reversals, or temporal development rather than verbosity.
