---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.state-apply.v1
match: route.scene-development.state-apply.v1
version: v1
route: scene-development
task_type: deterministic-cli
title: Atomic State Apply
required_inputs:
  - reviewed state patch JSON
  - current matching approval record
context_groups:
  - exact patch digest
  - approval record
  - character files
hard_constraints:
  - Apply only the exact reviewed and approved patch.
  - Update allowed character fields and apply receipt as one rollback-capable batch.
style_constraints:
  - none
output_contract:
  - Write state apply JSON and Markdown receipt with pre/post hashes.
review_requirements:
  - Canon remains untouched by state apply.
forbidden_shortcuts:
  - Do not use allow-unapproved or allow-unresolved in a formal route.
---

# State Apply

Apply only an independently reviewed, digest-bound approved state patch. The CLI must atomically update the allowed character files and the apply receipt. It must never silently write Canon or unrelated project assets.
