---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.longform-planning.reader-experience.v1
match: route.longform-planning.reader-experience.v1
version: v1
route: longform-planning
task_type: main-agent-reader-experience-contract
title: Exact Chapter Obligation And Reader Experience Contract
required_inputs:
  - project.yaml
  - current scene
  - plot/word_budget/word_budget.json
  - current chapter obligation scaffold
  - planned scenes in the current chapter
context_groups:
  - current chapter budget and scene inventory
  - reader questions and promised rewards
  - withheld information and payoff windows
  - inherited and outgoing hooks
hard_constraints:
  - Preserve the scaffold schema chapter_id count units target counts source_paths and output_path.
  - Set status to pass only when every required chapter and scene field is complete.
  - must_payoff must_setup must_change must_not_resolve inherited_hooks and expansion_needed are always JSON arrays of strings.
  - When no expansion is needed write expansion_needed as an empty array; never use false null or a prose string.
  - reader_experience_by_scene is a non-empty array with one contract for every planned scene in this chapter.
output_contract:
  - Write only the declared chapter obligation JSON and Markdown; Studio owns sidecars and completion receipts.
  - Keep target counts as Chinese-content characters including Chinese punctuation.
  - Preserve useful existing creative content while repairing only invalid fields.
review_requirements:
  - Each scene states reader_question promised_reward withheld_information payoff_or_delay emotional_curve tension_source curiosity_hook freshness_requirement anti_summary_requirement and reader_aftertaste.
  - The combined scene inventory must support the chapter target without decorative padding.
forbidden_shortcuts:
  - Do not use boolean false as a substitute for an empty list.
  - Do not omit quiet transition or aftermath obligations merely because they are not action scenes.
  - Do not create or edit lifecycle completion receipts.
---

# Exact Reader Experience Task

Complete the current chapter obligation from the supplied scaffold and project evidence. Keep all list-shaped fields as arrays even when empty. `expansion_needed=[]` means the inventory is sufficient; a non-empty array must contain concrete missing events, relationship pressure, information releases, failures, or consequences.

For every planned scene in the current chapter, define what question the reader carries in, what reward is promised, what is deliberately withheld, what is paid or delayed, how tension and emotional movement change, what prevents summary-like prose, and what pressure is handed forward. Do not change target counts to make an undersized inventory appear sufficient.
