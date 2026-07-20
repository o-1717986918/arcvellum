---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.revision.v1
match: route.scene-development.revision.v1
version: v1
route: scene-development
task_type: main-platform-agent-revision
title: Scene Revision Exact Prompt Asset
required_inputs:
  - draft or candidate
  - AgentReview notes
  - deterministic Style Lint evidence
  - style constraints
  - word budget and reader experience contracts
  - narrative rhythm and scene bridge contract
context_groups:
  - prose candidate
  - review notes
  - style
  - word budget
  - reader experience
  - narrative rhythm
hard_constraints:
  - The main platform Agent revises body prose personally.
  - Do not replace a banned contrast with another explicit contrast; use action, fact order, information gap, or direct statement.
  - Every unresolved review finding and every pass_with_notes action must cause a concrete prose edit; returning the original candidate unchanged is a failed revision.
  - Compare the revision against the exact input candidate before submission and record where each required change was applied.
  - Preserve canon and candidate-only writeback boundaries.
style_constraints:
  - Revisions are semantic edits, not regex cleanup.
output_contract:
  - Write revision candidate, revision report, manifest, prompt manifest, and completion marker at the task package paths.
review_requirements:
  - Revision candidate must be re-reviewed before promotion or export.
  - Anti-evasion burden-of-proof is required when a transition, contrast, dash, or AI-trace issue is touched.
  - The revision report maps each review action to an observable before/after change or explains why it remains blocking; it may not declare a finding resolved without changing the prose.
forbidden_shortcuts:
  - Do not promote revision without exact AgentReview.
  - Do not copy the draft into the revision field and claim that review notes were addressed.
---

# Exact Revision Prompt Asset

Resolve review notes without hiding the same problem under new wording. Any retained transition needs a critical burden-of-proof note in the revision report. Build a short change ledger first, apply every non-deferred item to the prose, then compare the resulting candidate with the exact source. If they are identical, the task is unfinished.
