---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.source-ingest.review-reconstruction.v1
match: route.source-ingest.review-reconstruction.v1
version: v1
route: source-ingest
task_type: platform-agent-archaeology-domain-review
title: Independent Archaeology Domain Review
required_inputs:
  - current aggregate and identity resolution
  - typed candidate project
context_groups:
  - character
  - world
  - plot
  - style
  - promise
hard_constraints:
  - Review all five domains and every proposed Archive asset.
  - Do not pass a domain or promote an asset while blocking issues remain.
  - Treat this as evidence review not user approval or Archive promotion.
  - Analysis mode requires analysis_only decisions.
style_constraints:
  - Findings must be specific actionable and evidence-aware.
output_contract:
  - Write one typed domain review JSON and one readable report.
review_requirements:
  - Every domain and asset appears exactly once in the review.
forbidden_shortcuts:
  - Do not change reconstruction content silently or convert a warning into approval.
---

# Project Archaeology Domain Review

Challenge the reconstruction before it reaches the Archive queue. Passing fewer reliable candidates is better than passing a larger speculative project.
