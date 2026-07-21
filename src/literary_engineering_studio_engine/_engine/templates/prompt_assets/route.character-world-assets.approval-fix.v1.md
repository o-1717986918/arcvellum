---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.character-world-assets.approval-fix.v1
match: route.character-world-assets.approval-fix.v1
version: v1
route: character-and-world-assets
task_type: platform-agent-revision
title: Approval-Bound Asset Revision Exact Prompt Asset
required_inputs:
  - exact current candidate and report
  - latest clean asset review
  - latest matching revise or reject approval rationale
context_groups:
  - candidate
  - review
  - approval rationale
hard_constraints:
  - Revise only the current candidate and its report; confirmed project assets remain read-only.
  - Treat the approval rationale as a critical revision request, not as permission to self-approve.
  - Change the candidate content, record applied_revision_actions, reset review status to recheck_required, and reset review completion evidence.
  - A fresh independent review and a new candidate-digest-bound approval are mandatory after revision.
style_constraints:
  - Preserve useful causal structure while fixing the exact approval concern; do not add decorative detail as camouflage.
output_contract:
  - Write only the declared candidate, candidate report, reset review artifacts, and reset completion marker.
review_requirements:
  - The candidate digest must differ from the digest captured when this task opened.
  - The revised asset cannot claim pass or promotion readiness.
forbidden_shortcuts:
  - Do not edit canon, formal character files, plot, scenes, drafts, exports, or releases.
  - Do not reuse an approval bound to the prior candidate content.
---

# Approval-Bound Asset Revision

Implement the latest approval rationale as a candidate-local revision. Preserve the previous review trail, reset it for independent recheck, and leave approval and promotion to later formal gates.
