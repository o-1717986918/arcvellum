---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.review-audit.committee.fix.v1
match: route.review-audit.committee.fix.v1
version: v1
route: review-and-audit
task_type: platform-agent-revision
title: Committee Repair Exact Prompt Asset
required_inputs:
  - prior committee verdict
  - exact declared repair targets
  - canon review and longform audit evidence
context_groups:
  - committee action items
  - cross-module consequences
hard_constraints:
  - Modify only declared repair targets and resolve every action item or disagreement critically.
  - Rerun canon-lint and longform-audit after repairs.
  - Reset canon review and committee review to recheck_required with applied_repair_actions.
  - Reset both completion markers to recheck_required with expected_artifacts_checked false.
style_constraints:
  - Do not sacrifice character causality or prose quality merely to make metrics green.
output_contract:
  - Write repaired targets refreshed deterministic audits reset canon review evidence and reset committee evidence.
review_requirements:
  - Fresh canon and committee agents must independently re-evaluate the changed project.
forbidden_shortcuts:
  - Do not self-approve the committee verdict.
  - Do not keep stale audit evidence after changing project sources.
---

# Committee Repair

Implement the committee's exact repairs, refresh deterministic evidence, and reopen both semantic review layers.
