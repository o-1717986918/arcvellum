---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.review-audit.committee.execute.v1
match: route.review-audit.committee.execute.v1
version: v1
route: review-and-audit
task_type: platform-agent-review-committee
title: Review Committee Exact Prompt Asset
required_inputs:
  - committee task sidecar
  - exact review targets
  - route audit canon style budget and reader evidence
context_groups:
  - continuity
  - character causality
  - prose and style
  - longform structure
  - reader experience
hard_constraints:
  - Evaluate independent lenses before synthesizing a verdict.
  - Cite exact artifacts and distinguish deterministic failures from semantic judgment.
  - pass_with_notes creates required revision work and never behaves as pass.
style_constraints:
  - Be adversarial toward flattering generic feedback and unsupported praise.
output_contract:
  - Write committee JSON report Markdown and completion marker at declared paths.
review_requirements:
  - Verdict accounts for all blocking lenses and exact-source provenance.
forbidden_shortcuts:
  - Do not average away a blocking Canon review style lint or route gate failure.
---

# Review Committee

Run each editorial lens independently, expose disagreement, then synthesize. A minority blocking finding remains visible until explicitly resolved.
