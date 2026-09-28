---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.longform-planning.chapter-obligation.execute.v1
match: route.longform-planning.chapter-obligation.execute.v1
version: v2
route: longform-planning
task_type: main-platform-agent-chapter-obligation
title: Chapter Obligation And Reader Experience Contract
required_inputs:
  - project.yaml
  - plot/outline.md
  - plot/word_budget/word_budget.json
  - plot/candidates/scenes/word_budget_scene_inventory.md
context_groups:
  - chapter budgets and planned scene counts
  - reader questions and promised rewards
  - withheld information and payoff windows
  - inherited and outgoing hooks
hard_constraints:
  - Bind every chapter obligation to its target Chinese-content character count and planned scene inventory.
  - Add event pressure when inventory is insufficient.
  - Distinguish setup payoff delay and intentional non-resolution.
  - Keep the plan candidate-only until semantic review and approval pass.
  - Write the plan in ordered chunks of no more than five chapter rows per write_expected_output call.
output_contract:
  - Write only the declared chapter-obligation plan; Studio owns lifecycle completion receipts and assigns a separate Reviewer.
review_requirements:
  - A separate digest-bound Reviewer must approve the completed candidate before materialization.
forbidden_shortcuts:
  - Do not review your own candidate or write a verdict.
  - Do not create or edit lifecycle completion receipts.
---

# Chapter Obligation And Reader Experience Planning

Build one chapter row for every planned chapter. Each row must identify `chapter_id`, target Chinese-content characters, target scene count, `chapter_function`, `must_payoff`, `must_setup`, `must_change`, `must_not_resolve`, inherited hooks, ending hook, inventory sufficiency, and any expansion needed.

Write at most five consecutive chapter rows in one tool call. Start the plan with `operation=replace, final=false`; append later groups with `operation=append`. Mark only the group containing the final planned chapter as `final=true`. Never repeat an earlier chapter row in a later chunk.

For each chapter, state the question the reader carries in, the reward it promises, what is deliberately withheld, what is paid or delayed, and what changes the reading of the next chapter. A quiet, transitional or aftermath chapter can earn its space by letting a relationship be lived, a person become legible, an old detail acquire a new charge, or an unspoken possibility gather evidence. Indicate where the chapter should move quickly and where it should let ordinary duration be felt. Where the current inventory cannot sustain its length, prescribe a distinct lived situation, relationship pressure, information release, failure or consequence rather than decorative expansion.

Do not write a review verdict. A separate digest-bound Reviewer verifies chapter coverage, reader obligations, causal handoffs, and scale sufficiency. Studio writes the completion receipt after deterministic preflight; do not create it.
