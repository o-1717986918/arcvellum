---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.longform-planning.scene-inventory.execute.v1
match: route.longform-planning.scene-inventory.execute.v1
version: v1
route: longform-planning
task_type: main-platform-agent-scene-inventory
title: Scene Inventory Expansion Exact Prompt Asset
required_inputs:
  - approved outline
  - budget review
  - canon and character arcs
context_groups:
  - volume obligations
  - chapter obligations
  - reader questions and promises
  - tension curve
hard_constraints:
  - Add causally necessary scenes until inventory supports the approved scale.
  - Give each scene a function target Han-character count rhythm role bridge and obligation.
  - Balance setup escalation payoff aftermath and transition scenes.
style_constraints:
  - Scene summaries must describe events and choices not prose decoration.
output_contract:
  - Write budgeted scene inventory artifacts only at declared paths.
review_requirements:
  - Inventory totals reconcile and no scene exists only to fill length.
forbidden_shortcuts:
  - Do not multiply near-duplicate conversations or split one beat cosmetically.
---

# Scene Inventory Expansion

Expand the story's causal surface, not its sentence count. Every added scene must change knowledge, choice, relationship, risk, obligation, or payoff timing.
