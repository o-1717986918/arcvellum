---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.character-world-assets.create.v1
match: route.character-world-assets.create.v1
version: v3
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
  - Candidate lifecycle schema review approval promotion and workflow rules are metadata.
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

Build an editable candidate. Derive the smallest coherent foundation supported by the premise, user direction, and confirmed canon. Keep rules that change character choices, conflicts, costs, evidence, or scene causality; make each core mechanism's boundary, failure consequence, and downstream use explicit and internally consistent. Do not invent named institutions, exact laws, historical incidents, clock/calendar facts, metaphysics, or elaborate access procedures unless the evidence requires them. Put unresolved causes and unsupported possibilities in open questions. Reject any rule that removes plausible character agency, pre-solves the central mystery, or exists only as decorative lore. Character assets must distinguish confirmed facts, behavioral inferences, and unresolved possibilities.

World rules describe facts and causal mechanisms inside the fictional world. Keep instructions about prose texture, psychological narration, dialogue length, figurative language, and atmosphere in the editable style or creative-direction context. For characters, identify a few enduring temperament and relationship traits that can shape speech and response across scenes; place scene duties and immediate actions in scene planning.
Chapter and scene counts, viewpoint, cast scope, and time arrangement belong in the plan; they are not fictional-world rules.
Give each major character a speech range shaped by temperament, relationship, and changing emotion; let the voice have room for talk, digression, humor, evasion, and intensity when the character's life calls for them.

Project lifecycle facts such as candidate status, schema review, approval, promotion, or whether an asset is already Canon belong to Studio metadata. They are never fictional world rules and must not appear in `core_rules`, `constraints`, `history_pressure`, or other literary fields.
