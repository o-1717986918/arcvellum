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
  - plot/word_budget/word_budget.agent_tasks.md
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
  - Use pass only when inventory supports the target and no blocking issue remains.
  - Do not use pass_with_notes; nonblocking observations belong in a notes section under pass.
output_contract:
  - Write only the declared outline candidate review report and completion evidence.
  - The review must contain a standalone machine-readable line exactly shaped as - 结论： pass, - 结论： revise_required, or - 结论： reject.
  - Completion evidence must use literary-engineering-workbench/agent-task-completion/v1 and cite the source task.
review_requirements:
  - Verify event density causal chains relationship changes information release consequences and setup/payoff inventory.
  - Treat missing inventory as revise_required rather than hiding it in notes.
forbidden_shortcuts:
  - Do not declare pass merely because numeric totals reconcile.
  - Do not invent completion evidence before all declared outputs have been checked.
---

# Longform Budget Expansion

Build a candidate longform structure whose event inventory can actually carry the requested scale. Give every volume and chapter a causal function, target Han-character budget, planned scene count, reader obligation, consequence, and handoff. Preserve enough specificity to prove that the requested length is supported, but leave scene-by-scene expansion to the next formal scene-inventory task.

The review status is a formal gate. Write one standalone status line in the exact form required by the output contract. Use `pass` when remaining observations are genuinely nonblocking and place those observations in a separate notes section. Use `revise_required` whenever the outline still lacks events, causality, obligations, or sufficient reader payoff inventory. Only after all outputs exist and have been checked may you write the completion JSON.
