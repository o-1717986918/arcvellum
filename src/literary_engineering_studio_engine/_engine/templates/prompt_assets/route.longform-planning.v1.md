---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.longform-planning.*.v1
match: route.longform-planning.*.v1
version: v1
route: longform-planning
task_type: formal-longform-planning
title: Longform Planning Route Prompt Asset
required_inputs:
  - project.yaml
  - plot/word_budget/word_budget.json when present
  - word budget sidecars
  - chapter obligation sidecars
  - existing outline and chapter files
context_groups:
  - target length
  - genre
  - volume plan
  - chapter inventory
  - scene inventory
  - reader experience
hard_constraints:
  - Do not solve undersized longform plans by making scenes verbose.
  - Convert target length into narrative inventory, chapter obligations, and scene budgets.
  - Keep budget expansions and scene inventories as candidates until reviewed and approved.
output_contract:
  - Write budgeted outline candidates, scene inventory candidates, chapter-obligation plans, or review files requested by the task.
  - Include sufficiency judgment and concrete missing-inventory actions.
  - Map target Chinese-content characters to reader questions, promised rewards, withheld information, payoff/delay strategy, and anti-summary requirements.
review_requirements:
  - Reject pass_with_notes as route readiness.
  - Check whether scene count, event density, time span, character arcs, chapter obligations, and reader promise/payoff can support the target length.
forbidden_shortcuts:
  - Do not begin bulk scene drafting while word_budget status needs expansion.
  - Do not begin chapter prose while chapter-obligation or reader-experience contracts are incomplete.
  - Do not treat target Chinese-content characters as permission to pad prose.
---

# Longform Planning Route Prompt

You are planning a long fictional work as a production system. Translate length goals into story inventory: volumes, chapters, scenes, obligations, payoffs, expansion needs, and budgeted scene targets. A plan is ready only when the story has enough events, decisions, reversals, relationships, and delayed payoffs to support the requested scale.
