---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.character-world-assets.review-fix.v1
match: route.character-world-assets.review-fix.v1
version: v2
route: character-and-world-assets
task_type: platform-agent-revision
title: Character and World Asset Revision Exact Prompt Asset
required_inputs:
  - exact candidate asset and candidate report
  - previous asset review JSON and Markdown
  - candidate sha256 before revision
context_groups:
  - candidate
  - review findings
  - canon and character logic already supplied by the task package
hard_constraints:
  - Resolve every blocking issue and revision action in the candidate itself.
  - Do not create files outside Allowed Outputs. Reclassify an old cross-task action as a follow-up warning or promotion risk and revise only candidate-local findings.
  - Preserve valid creative intent while removing contradictions vague placeholders and unearned complexity.
  - Change the candidate content; changing only review labels is forbidden.
  - Do not self-pass the review that requested this revision.
  - After revision set review status to recheck_required, set revision_round to an integer >= 1, and record applied_revision_actions as a non-empty array. Each entry must contain id, action, and concrete evidence in the candidate.
  - Reset the review completion marker to recheck_required with expected_artifacts_checked false so a fresh review task must run.
style_constraints:
  - Keep background story as hidden behavioral causality rather than direct exposition.
  - Mounted style may shape expression but cannot override canon user direction or causal clarity.
output_contract:
  - Rewrite the declared candidate JSON and candidate Markdown report.
  - Update the prior review JSON with status recheck_required, revision_round, revised_at, and one applied_revision_actions entry for every original revision action. Do not treat the old revision_actions array as revision evidence.
  - Update the review Markdown to explain the revision evidence and say that independent recheck is pending.
  - Reset the declared review completion marker; never write complete or pass in this revision task.
review_requirements:
  - Each previous blocking issue or revision action must map to a concrete candidate change or a critical explanation that the issue cannot be resolved without user direction.
  - A new asset-review-agent-task makes the next verdict.
forbidden_shortcuts:
  - Do not write pass failed or revise_required as the new review verdict.
  - Do not delete critical findings without recording how the candidate changed.
  - Do not edit confirmed canon or promoted character files.
  - Do not create unrelated candidate assets merely because an earlier reviewer crossed the current task boundary.
---

# Character and World Asset Revision

Treat the review as a change request, not as paperwork. Revise the candidate, preserve auditable evidence, invalidate the old completion marker, and hand the result to a fresh reviewer.

Before finishing, verify the review JSON has this revision shape (use the task's actual original action IDs):

```json
{
  "status": "recheck_required",
  "revision_round": 1,
  "applied_revision_actions": [
    {
      "id": "REV-001",
      "action": "what was changed",
      "evidence": "candidate path and concrete changed field"
    }
  ]
}
```

The new status is not a pass. It means an independent reviewer must review the changed candidate again.
