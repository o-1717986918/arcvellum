---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.longform-planning.chapter-obligation-review.v1
match: route.longform-planning.chapter-obligation-review.v1
version: v1
route: longform-planning
task_type: platform-agent-review
title: Chapter Obligation Independent Review
required_inputs:
  - plot/word_budget/word_budget.json
  - exact chapter obligation candidate
  - digest-bound review JSON template
context_groups:
  - chapter coverage
  - reader questions
  - promises and payoffs
  - withheld information and chapter change
hard_constraints:
  - Review the exact candidate without editing it.
  - Every planned chapter needs an executable reader obligation and outgoing causal pressure.
  - A pass cannot retain required changes.
style_constraints:
  - Findings must point to concrete chapters and obligations.
output_contract:
  - Fill the authoritative structured review JSON and write its readable Markdown report at declared paths.
review_requirements:
  - Check every dimension declared by the prepared template.
forbidden_shortcuts:
  - Do not accept numeric chapter coverage without sufficient events promises or payoffs.
---

# Chapter Obligation Independent Review

Check chapter coverage, reader questions, promise and payoff timing, withheld information, chapter-level change, and anti-summary pressure. Use `pass`, `revise`, or `block`; the JSON controls the Gate and the Markdown report explains the result.
