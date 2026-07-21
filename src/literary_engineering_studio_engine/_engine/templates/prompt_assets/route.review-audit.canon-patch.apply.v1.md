---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.review-audit.canon-patch.apply.v1
match: route.review-audit.canon-patch.apply.v1
version: v1
route: review-and-audit
task_type: deterministic-cli
title: Canon Patch Apply
required_inputs:
  - apply-ready canon patch candidate
  - current content-bound approve record
context_groups:
  - canon writeback ledger
hard_constraints:
  - Apply only the exact approved digest.
  - Never use allow_unapproved in a formal route.
  - Preserve an immutable apply manifest and append the canon change log.
style_constraints:
  - This is a deterministic ledger operation; do not generate narrative prose.
output_contract:
  - Write the apply JSON report patch applied metadata and canon change log entry.
review_requirements:
  - Verify approval digest and patch schema before any write.
forbidden_shortcuts:
  - Do not mutate unrelated canon files during ledger apply.
---

# Canon Patch Apply

Apply the approved patch into the durable canon ledger and preserve complete provenance.
