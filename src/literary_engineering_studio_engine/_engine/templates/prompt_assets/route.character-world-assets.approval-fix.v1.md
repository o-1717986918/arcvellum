---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.character-world-assets.approval-fix.v1
match: route.character-world-assets.approval-fix.v1
version: v2
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
  - Change the candidate content and candidate report only. Studio Worker deterministically sets review status to recheck_required, records applied revision evidence, and resets review completion evidence.
  - A fresh independent review and a new candidate-digest-bound approval are mandatory after revision.
style_constraints:
  - Preserve useful causal structure while fixing the exact approval concern; do not add decorative detail as camouflage.
output_contract:
  - Write only the declared candidate and candidate report. Studio Worker resets review lifecycle metadata after the candidate has changed.
review_requirements:
  - The candidate digest must differ from the digest captured when this task opened.
  - The revised asset cannot claim pass or promotion readiness.
forbidden_shortcuts:
  - Do not edit canon, formal character files, plot, scenes, drafts, exports, or releases.
  - Do not reuse an approval bound to the prior candidate content.
---

# Approval-Bound Asset Revision

Implement the latest approval rationale as a candidate-local revision. Preserve the previous review trail, let Studio Worker reset it for independent recheck, and leave approval and promotion to later formal gates.

The approval rationale is an executable change request. Make one candidate-local structural clarification that answers it, for example a documented merge strategy, an explicit canonical-character reference, or a declared dual-ID relationship. Do not modify the promoted asset itself.

Use the `write` tool, not the `edit` tool, when replacing multi-line JSON or Markdown. Every write call must contain both `filePath` and `content`. Do not edit review JSON, review Markdown, or completion receipts: Studio Worker creates their `recheck_required` lifecycle reset only after it detects a real candidate change.
