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

Plan the reader's long encounter with this fictional world as well as its production scale. Translate length goals into volumes, chapters, scenes, obligations, payoffs, expansion needs and budgeted targets. Follow how a belief, relationship, recurring detail or public account changes meaning over time. Make room for everyday duration, humor, intimacy and aftermath alongside decisions and reversals. A plan is ready when distinct events and lived situations can support the requested scale, the reader has reasons to continue and to pause, and delayed information can be recognized fairly when it returns. Do not turn every chapter into the same escalation shape.
