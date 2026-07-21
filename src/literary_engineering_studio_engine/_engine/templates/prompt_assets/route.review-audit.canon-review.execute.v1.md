---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.review-audit.canon-review.execute.v1
match: route.review-audit.canon-review.execute.v1
version: v1
route: review-and-audit
task_type: platform-agent-review
title: Canon Review Exact Prompt Asset
required_inputs:
  - canon lint JSON and report
  - canon review sidecar
  - confirmed canon character plot and scene evidence
context_groups:
  - canon continuity
  - character causality
  - timeline
  - unresolved facts
hard_constraints:
  - Record pass pass_with_notes revise_required or reject honestly; a non-pass verdict is a valid completed review.
  - Do not edit project sources during this review task.
  - Every non-pass repair recommendation must be an object with exact target_path action and verification.
  - target_path must be one text file under canon characters plot scenes or drafts/candidates; never name a directory review file or workflow file.
style_constraints:
  - Prefer exact contradictions and downstream consequences over generic advice.
output_contract:
  - Write canon_review.v1 JSON Markdown and the declared completion marker.
review_requirements:
  - Pass requires no blocking issues warnings unresolved facts or timeline risks.
  - Non-pass findings must remain visible until a separate repair task changes their declared targets.
forbidden_shortcuts:
  - Do not invent a pass merely because the route is waiting.
  - Do not hide a repair requirement in prose without a machine-readable target_path.
---

# Canon Review

Treat the project as a versioned narrative system. Report the real verdict, identify exact repair ownership, and leave implementation to the separately sandboxed repair task.
