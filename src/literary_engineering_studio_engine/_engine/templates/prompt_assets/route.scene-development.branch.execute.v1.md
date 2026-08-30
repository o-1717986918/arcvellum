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
  - Treat deterministic manifest branches as fallbacks; write exactly the branch_count declared by branch_manifest.json with agent_branch_<slug> ids. Never infer a 2-5 range when the manifest has already fixed the count.
  - Every proposal must differ in causal premise, action chain, irreversible cost, reader effect, and concrete state writeback.
  - Preserve the exact branch_proposals.json scaffold field names; never substitute id, rationale, irreversible_cost, or next_scene_pressure for branch_id, causal_premise, cost, or reader_effect.
  - Keep state_writeback values as string lists, and keep every beat serves value as a list of obligation names.
  - Put only changes that visibly occur in this scene into character_changes or relationship_changes. Put intentions, possible future turns, and explicitly not-yet-realized changes into next_scene_inputs instead.
  - Keep alternatives concise: normally use the supplied two-beat scaffold; add at most one third beat only when the causal turn cannot be represented clearly in two. A beat may serve several obligations.
  - Across each beat_plan cover incoming_bridge goal turn cost reader_effect and outgoing_hook; each beat declares pace and detail_level.
  - Score character consistency canon safety dramatic yield future cost and reader promise.
  - Preserve losing branches and their useful elements for formal selection.
style_constraints:
  - Branch notes are engineering evidence and never enter prose.
output_contract:
  - Write branch_proposals.json and branch_selection.md only at declared paths; lifecycle completion is Worker-owned.
review_requirements:
  - Every branch identifies its irreversible cost, next-scene pressure, and a beat plan whose obligations are complete.
forbidden_shortcuts:
  - Do not preselect a branch or collapse alternatives into one answer.
---

# Branch Simulation

Explore causally distinct futures. A branch is valid only when it changes a choice, cost, relationship, revealed fact, or future obligation. Do not rename, paraphrase, or lightly decorate the deterministic fallback archetypes.
