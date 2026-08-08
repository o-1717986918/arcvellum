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
  - Treat deterministic manifest branches as fallbacks; write 2-5 scene-specific proposals with agent_branch_<slug> ids.
  - Every proposal must differ in causal premise, action chain, irreversible cost, reader effect, and concrete state writeback.
  - Score character consistency canon safety dramatic yield future cost and reader promise.
  - Preserve losing branches and their useful elements for formal selection.
style_constraints:
  - Branch notes are engineering evidence and never enter prose.
output_contract:
  - Write branch_proposals.json and branch_selection.md only at declared paths; lifecycle completion is Worker-owned.
review_requirements:
  - Every branch identifies its irreversible cost and next-scene pressure.
forbidden_shortcuts:
  - Do not preselect a branch or collapse alternatives into one answer.
---

# Branch Simulation

Explore causally distinct futures. A branch is valid only when it changes a choice, cost, relationship, revealed fact, or future obligation. Do not rename, paraphrase, or lightly decorate the deterministic fallback archetypes.
