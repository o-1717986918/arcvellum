---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.review-audit.canon-review.fix.v1
match: route.review-audit.canon-review.fix.v1
version: v1
route: review-and-audit
task_type: platform-agent-revision
title: Canon Review Repair Exact Prompt Asset
required_inputs:
  - prior canon review JSON and Markdown
  - exact declared repair targets and their pre-repair hashes
  - canon lint evidence
context_groups:
  - repair actions
  - canon and timeline
hard_constraints:
  - Modify only Allowed Outputs and make a substantive change to at least one declared repair target.
  - Resolve each finding at its target_path without relabeling the old review as pass.
  - Run canon-lint after repair and keep its refreshed Markdown and JSON outputs.
  - Set canon review conclusion to recheck_required record applied_repair_actions and reset completion evidence to recheck_required with expected_artifacts_checked false.
style_constraints:
  - Preserve deliberate ambiguity while removing contradictions and unsupported durable facts.
output_contract:
  - Write every declared repair target refreshed canon lint files reset review JSON/Markdown and reset completion marker.
review_requirements:
  - A fresh independent canon-review-agent-task decides the next verdict.
forbidden_shortcuts:
  - Do not self-pass or delete findings without repair evidence.
  - Do not touch a file that was not declared as an Allowed Output.
---

# Canon Review Repair

Repair the project, invalidate stale review evidence, refresh deterministic lint, and return control to an independent reviewer.
