---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.longform-planning.budget-expansion.execute.v1
match: route.longform-planning.budget-expansion.execute.v1
version: v1
route: longform-planning
task_type: main-platform-agent-budget-expansion
title: Longform Budget Expansion Execution Contract
required_inputs:
  - project.yaml
  - plot/outline.md
  - plot/word_budget/word_budget.json
context_groups:
  - target Han-character count
  - genre and time span
  - volume and chapter inventory
  - planned scene counts by chapter
  - reader questions promises and payoffs
hard_constraints:
  - Expand narrative inventory rather than padding prose.
  - Reconcile project volume and chapter Han-character targets and planned scene counts.
  - Do not enumerate every scene in this task; the formal scene-inventory task owns scene-level expansion.
  - Keep the expanded outline as candidate material pending human approval.
output_contract:
  - Write only the declared outline candidate; Studio writes lifecycle completion evidence and assigns a separate Reviewer task.
review_requirements:
  - A separate digest-bound Reviewer must approve the completed candidate before downstream planning.
forbidden_shortcuts:
  - Do not declare pass merely because numeric totals reconcile.
  - Do not create or edit lifecycle completion receipts.
---

# Longform Budget Expansion

Build a candidate longform structure whose event inventory can actually carry the requested scale. Preserve enough specificity to prove that the requested length is supported, but leave scene-by-scene expansion to the next formal scene-inventory task.

The candidate must be organized from volume to chapter. For every chapter, record its target Chinese-content character count, planned scene count, chapter function, key dramatic turn, main-plot load, subplot load, character-change load, world/canon load, consequence load, detail level, reader obligation, incoming causal pressure, and outgoing handoff. For every volume, summarize the inventory of core events, action or investigation chains, relationship changes, information releases, failures and costs, setup/payoff obligations, and the planned chapter and scene totals. Numeric reconciliation alone is insufficient: every allocated block must correspond to enough distinct causal events to sustain the requested scale without repetitive prose or summary compression.

Do not review your own candidate or write a review verdict. A separate digest-bound Reviewer task evaluates event density, causality, obligations, and reader payoff inventory after this candidate is complete. Do not create the completion receipt; Studio writes it after deterministic preflight.
