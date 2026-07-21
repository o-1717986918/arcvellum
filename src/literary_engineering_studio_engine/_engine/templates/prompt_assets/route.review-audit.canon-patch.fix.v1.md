---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.review-audit.canon-patch.fix.v1
match: route.review-audit.canon-patch.fix.v1
version: v1
route: review-and-audit
task_type: platform-agent-revision
title: Canon Patch Candidate Repair Exact Prompt Asset
required_inputs:
  - current canon patch JSON and report
  - canon-evolve task and completion evidence
  - latest content-bound approval decision and rationale
  - cited scene and durable canon context
context_groups:
  - canon patch candidate
  - approval findings
  - source scene evidence
hard_constraints:
  - Change the candidate content materially; editing only status or approval metadata is not a repair.
  - Keep every durable fact grounded in exact scene evidence and scoped to safe canon target_files.
  - Do not edit canon files and do not mark the patch applied.
  - Update the plain-language report and complete the canon-evolve evidence after the repair.
style_constraints:
  - Preserve useful ambiguity and character-limited knowledge; do not inflate a scene detail into a universal world rule.
output_contract:
  - Write the revised patch JSON report Markdown and completion evidence at the exact Allowed Outputs.
review_requirements:
  - A fresh content-bound approval is mandatory after every patch change.
forbidden_shortcuts:
  - Do not reuse a stale approval.
  - Do not remove a difficult fact merely to make validation pass without explaining the decision.
---

# Canon Patch Candidate Repair

Repair the pending canon writeback candidate against the latest findings. This task changes only the candidate and never writes durable canon directly.
