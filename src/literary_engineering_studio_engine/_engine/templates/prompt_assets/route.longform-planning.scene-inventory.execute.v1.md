---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.longform-planning.scene-inventory.execute.v1
match: route.longform-planning.scene-inventory.execute.v1
version: v2
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
  - Write the inventory as the exact chapter-heading plus 11-column scene table contract required for deterministic materialization.
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

## Required Machine-Readable Inventory Shape

Write `plot/candidates/scenes/word_budget_scene_inventory.md` in this exact repeated shape. Do not replace it with per-scene cards, bullet lists, or prose explanations.

```md
### Ch 0001 — Chapter title |

| scene_id | name | target_chars | function | participants | conflict | information_release | consequence | setup_payoff_role | rhythm_role | obligation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SC-001 | Scene title | 1400 | mainline_action | Person A、Person B | concrete conflict | released fact | concrete consequence | setup or payoff | escalation | reader-facing obligation |
```

Use one unique `SC-###` row for every planned scene. `target_chars` must be a positive integer. The 11 data columns are mandatory, and the total row count must reconcile with `word_budget.json`.
