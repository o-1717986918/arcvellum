---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.state-approval.v1
match: route.scene-development.state-approval.v1
version: v1
route: scene-development
task_type: human-approval-boundary
title: State Patch Approval Boundary
required_inputs:
  - reviewed state patch JSON
  - digest-bound state review
  - proposed character files summary
context_groups:
  - character state candidate
  - review evidence
  - approval records
hard_constraints:
  - Approval binds to the exact state-patch SHA-256.
  - Approval alone never writes a character or Canon file.
style_constraints:
  - none
output_contract:
  - Record only a formal approve/revise/reject decision through the approval mechanism.
review_requirements:
  - State patch must have a passing independent semantic review first.
forbidden_shortcuts:
  - Do not use allow-unapproved or alter the patch after recording approval.
---

# State Patch Approval

Present only the reviewed character-state changes and their prose evidence. An approval records intent; it must bind to the exact current state-patch SHA-256 and never writes character files itself. A revise/reject decision returns the patch to review or repair.
