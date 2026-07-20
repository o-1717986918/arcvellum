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
  - Preserve canon and candidate-only writeback boundaries.
style_constraints:
  - Revisions are semantic edits, not regex cleanup.
output_contract:
  - Write revision candidate, revision report, manifest, prompt manifest, and completion marker at the task package paths.
review_requirements:
  - Revision candidate must be re-reviewed before promotion or export.
  - Anti-evasion burden-of-proof is required when a transition, contrast, dash, or AI-trace issue is touched.
forbidden_shortcuts:
  - Do not promote revision without exact AgentReview.
---

# Exact Revision Prompt Asset

Resolve review notes without hiding the same problem under new wording. Any retained transition needs a critical burden-of-proof note in the revision report.
