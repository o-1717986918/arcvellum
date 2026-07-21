---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.review-audit.canon-patch.approval.v1
match: route.review-audit.canon-patch.approval.v1
version: v1
route: review-and-audit
task_type: human-approval-boundary
title: Canon Patch Content-Bound Approval
required_inputs:
  - current canon patch JSON and report
  - current candidate SHA-256
context_groups:
  - canon writeback decision
hard_constraints:
  - The writing Worker cannot approve its own patch.
  - Record the decision against the exact current candidate digest.
  - Revise reject and defer remain explicit states; none may be treated as approve.
style_constraints:
  - Present approval evidence concisely and separately from the literary work.
output_contract:
  - Append one approval record with run_id decision actor notes and subject_sha256.
review_requirements:
  - Judge whether each fact is durable supported and correctly scoped before approval.
forbidden_shortcuts:
  - Do not reuse approval after any candidate change.
---

# Canon Patch Approval

Record a content-bound decision. Applying the patch remains a separate deterministic task.
