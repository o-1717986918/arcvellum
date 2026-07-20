---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.branch.execute.v1
match: route.scene-development.branch.execute.v1
version: v1
route: scene-development
task_type: platform-agent-branch-simulation
title: Branch Simulation Exact Prompt Asset
required_inputs:
  - completed roleplay simulation
  - branch task sidecar
  - scene yaml
  - context packet
context_groups:
  - character causality
  - world consequences
  - reader experience
  - canon
hard_constraints:
  - Produce materially different causal branches rather than cosmetic variants.
  - Score character consistency canon safety dramatic yield future cost and reader promise.
  - Preserve losing branches and their useful elements for formal selection.
style_constraints:
  - Branch notes are engineering evidence and never enter prose.
output_contract:
  - Write the branch manifest and completion marker only at declared paths.
review_requirements:
  - Every branch identifies its irreversible cost and next-scene pressure.
forbidden_shortcuts:
  - Do not preselect a branch or collapse alternatives into one answer.
---

# Branch Simulation

Explore causally distinct futures. A branch is valid only when it changes a choice, cost, relationship, revealed fact, or future obligation.
