---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.style-engineering.review.prepare.v1
match: route.style-engineering.review.prepare.v1
version: v1
route: style-engineering
task_type: deterministic-cli
title: Prepare Digest-Bound Style Review
required_inputs:
  - accepted deterministic style evaluation
  - current style profile and prompt
context_groups:
  - source-set digest
  - prompt and candidate digests
  - score digest
hard_constraints:
  - Prepare review evidence only; do not perform semantic judgment.
  - Do not expose raw holdout prose to the reviewer task.
output_contract:
  - Write the CLI-owned review skeleton, report skeleton, and task sidecar.
review_requirements:
  - Bind every upstream artifact by SHA-256.
forbidden_shortcuts:
  - Do not treat an accepted deterministic score as semantic approval.
---

# Prepare Independent Style Review

Create the formal review envelope for the exact current style evidence. This deterministic step owns paths, digests, fixed dimensions, and task identity; the independent Reviewer owns only the literary verdict and concise evidence.
