---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.branch.selection.v1
match: route.scene-development.branch.selection.v1
version: v1
route: scene-development
task_type: main-platform-agent-decision
title: Branch Selection Exact Prompt Asset
required_inputs:
  - completed branch manifest
  - roleplay simulation
  - scene and longform obligations
context_groups:
  - branch scores
  - canon
  - character arcs
  - reader promises
hard_constraints:
  - Select by causal strength and longform value rather than convenience or novelty alone.
  - Record rejected branches and any elements deliberately retained.
  - Human-gated decisions remain human-gated and cannot be self-approved.
style_constraints:
  - Decision rationale stays outside prose.
output_contract:
  - Write a formal branch selection with selected id rationale retained elements and risks.
review_requirements:
  - The selected branch exists in the manifest and preserves canon and character causality.
forbidden_shortcuts:
  - Do not infer selection from filenames scores alone or the intended outline ending.
---

# Branch Selection

Choose the branch that makes later writing more causally inevitable while keeping meaningful future pressure. Explain why apparently easier alternatives were rejected.
