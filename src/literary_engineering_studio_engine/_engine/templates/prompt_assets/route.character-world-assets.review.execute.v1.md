---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.character-world-assets.review.execute.v1
match: route.character-world-assets.review.execute.v1
version: v1
route: character-and-world-assets
task_type: platform-agent-asset-review
title: Character and World Asset Review Exact Prompt Asset
required_inputs:
  - exact candidate asset
  - asset review sidecar
  - confirmed canon characters plot and style
context_groups:
  - candidate
  - canon
  - character logic
  - promotion risk
hard_constraints:
  - Review schema canon causality originality hidden-background policy and downstream impact.
  - Reject contradictions vague placeholder psychology and promotion that overwrites confirmed facts silently.
  - A clean review is not approval.
  - A revise_required or failed verdict is a valid completed review task and must be recorded honestly.
  - Do not edit the candidate in this task and do not soften findings merely to make the route advance.
  - Revision actions may target only the current candidate JSON or its report. Dependencies on other characters canon assets scenes or routes belong in warnings or promotion_risks and must not block this candidate.
style_constraints:
  - Do not reward ornamental detail that has no behavioral or world consequence.
output_contract:
  - Write review JSON Markdown and completion marker at declared paths.
review_requirements:
  - Pass requires no blocking issues or unresolved revision actions.
  - Revise-required findings must be concrete enough for a separate revision task to implement and recheck.
  - Every revision action target must equal the current candidate path or a field anchor beneath it.
forbidden_shortcuts:
  - Do not self-approve or promote the candidate.
  - Do not convert a real revision finding into a warning to avoid the revision loop.
---

# Character and World Asset Review

Review as the maintainer of a shared codebase would review a schema-changing patch: inspect consistency, ownership, blast radius, migration risk, and whether the new information earns its complexity.
