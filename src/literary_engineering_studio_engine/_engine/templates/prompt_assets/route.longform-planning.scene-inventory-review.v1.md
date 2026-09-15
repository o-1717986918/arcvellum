---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.longform-planning.scene-inventory-review.v1
match: route.longform-planning.scene-inventory-review.v1
version: v1
route: longform-planning
task_type: platform-agent-review
title: Scene Inventory Independent Review
required_inputs:
  - plot/word_budget/word_budget.json
  - exact scene inventory candidate
  - digest-bound review JSON template
context_groups:
  - exact scene and character totals
  - chapter allocation
  - scene functions and causal handoffs
  - participant identity hygiene
hard_constraints:
  - Review the exact candidate without editing it.
  - Recount machine-readable rows and target characters instead of trusting asserted totals.
  - Treat totals.scene_count totals.target_chinese_chars and chapter_budgets as the candidate acceptance contract. scene_inventory_binding status missing_scenes and word_shortfall describe the formal project before this candidate is materialized and must not be used as evidence that a correctly reconciled candidate is incomplete.
  - Treat the task-bound machine digest as authoritative. Ignore any self-reported digest in candidate prose for identity binding; report embedded lifecycle metadata as a candidate cleanup revision only.
  - Use revise for every defect repairable inside the declared candidate. Reserve block for an irreconcilable user canon or budget conflict that cannot be repaired within this task.
  - A pass cannot retain required changes.
style_constraints:
  - Findings must identify concrete rows or missing causal obligations.
output_contract:
  - Fill the authoritative structured review JSON and write its readable Markdown report at declared paths.
review_requirements:
  - Check every dimension declared by the prepared template.
forbidden_shortcuts:
  - Do not pass a malformed table even when its narrative ideas appear usable.
---

# Scene Inventory Independent Review

Verify row shape, exact totals, chapter distribution, scene functions, causal bridges, and participant identities. The generated budget's pre-materialization deficit fields explain why this candidate exists; they are not post-candidate acceptance criteria. Use `pass`, `revise`, or `block`; the JSON controls the Gate and the Markdown report explains the result.
