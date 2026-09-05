---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.longform-planning.budget-review.v1
match: route.longform-planning.budget-review.v1
version: v1
route: longform-planning
task_type: platform-agent-budget-review
title: Longform Budget Review Exact Prompt Asset
required_inputs:
  - project.yaml
  - plot/word_budget/word_budget.json
  - exact budgeted outline candidate
  - digest-bound review JSON template
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
  - Fill the authoritative structured review JSON and write its readable Markdown report at declared paths.
  - Keep candidate_path candidate_sha256 writer_session_id reviewer_session_id and schema as Studio-owned fields.
review_requirements:
  - Use pass revise or block. A pass has no required_changes; revise or block lists concrete required changes.
  - Check every dimension already declared in checked_dimensions.
forbidden_shortcuts:
  - Do not accept a short-novella inventory for a long-novel target.
---

# Longform Budget Review

Audit length as narrative inventory without editing the candidate. Expansion must add choices, consequences, relationships, investigations, reversals, or temporal development rather than verbosity. The JSON verdict controls the formal Gate; the Markdown report only explains it to users.
