---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.character-world-assets.create.v1
match: route.character-world-assets.create.v1
version: v1
route: character-and-world-assets
task_type: platform-agent-asset-creation
title: Character and World Asset Creation Exact Prompt Asset
required_inputs:
  - asset creation sidecar
  - project canon characters plot and style
context_groups:
  - confirmed canon
  - relevant relationships
  - narrative role
  - hidden causality
hard_constraints:
  - Create a candidate asset that satisfies its schema and the smallest requested scope.
  - Character background story remains hidden behavioral causality rather than obligatory exposition.
  - Distinguish major characters from relevant minor characters for context economy.
style_constraints:
  - Style may shape voice and naming but cannot override canon or user constraints.
output_contract:
  - Write candidate JSON readable report and completion marker only at declared paths.
review_requirements:
  - Candidate includes risks provenance and promotion notes.
forbidden_shortcuts:
  - Do not write directly to confirmed canon characters plot scenes or drafts.
---

# Character and World Asset Creation

Build an editable candidate, not an unquestionable truth. Favor specific motives, limits, institutions, material conditions, and consequences over decorative lore.
