---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.longform-planning.chapter-obligation.execute.v1
match: route.longform-planning.chapter-obligation.execute.v1
version: v1
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
  - Add event pressure when inventory is insufficient; never ask prose to fill a structural deficit.
  - Distinguish setup payoff delay and intentional non-resolution.
  - Keep the plan candidate-only until semantic review and approval pass.
output_contract:
  - Write only the declared chapter-obligation plan and semantic review; Studio owns lifecycle completion receipts.
  - The review must contain a standalone line exactly shaped as - 结论： pass, - 结论： revise_required, or - 结论： reject.
review_requirements:
  - Every major chapter has an executable reader-experience contract and a causal handoff.
  - Use revise_required when a chapter has a numeric budget but insufficient events obligations or payoffs.
forbidden_shortcuts:
  - Do not use pass_with_notes.
  - Do not create or edit lifecycle completion receipts.
---

# Chapter Obligation And Reader Experience Planning

Build one chapter row for every planned chapter. Each row must identify `chapter_id`, target Chinese-content characters, target scene count, `chapter_function`, `must_payoff`, `must_setup`, `must_change`, `must_not_resolve`, inherited hooks, ending hook, inventory sufficiency, and any expansion needed.

For each chapter, state the question the reader carries in, the reward the chapter promises, information deliberately withheld, promises paid here, promises delayed, and the concrete causal pressure passed to the next chapter. A chapter can be quiet, transitional, or aftermath-focused, but it cannot be structurally empty. Where the current inventory cannot sustain the allocated length, prescribe additional events, relationship pressure, information release, failure, or consequence rather than decorative expansion.

Write the declared review report with an exact conclusion line. Use `pass` only when all major chapters have executable obligations whose combined inventory supports the requested scale. Studio writes the completion receipt after deterministic preflight; do not create it.
