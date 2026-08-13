---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.canon-review.v1
match: route.scene-development.canon-review.v1
version: v1
route: scene-development
task_type: platform-agent-canon-review
title: Scene Canon Candidate Independent Review
required_inputs:
  - exact promoted draft
  - scene yaml and exact AgentReview
  - state patch boundary
  - candidate Canon patch and report
  - current formal Canon files
context_groups:
  - candidate patch
  - promoted prose
  - review evidence
  - state boundary
  - formal canon
hard_constraints:
  - Review the exact candidate independently; do not rewrite it.
  - Reject temporary character state, transient action, duplicate facts, unsupported inference, and vague target files as Canon.
  - Do not apply the patch or modify formal Canon files.
style_constraints:
  - none
output_contract:
  - Write only canon/patches/{scene_id}_canon_patch_review.json; Studio writes lifecycle completion evidence after deterministic preflight.
review_requirements:
  - Bind every finding to exact promoted prose and current Canon evidence.
  - Pass only when every item is durable, non-duplicative, precisely scoped, and safely routed to declared target files.
  - Otherwise return revise_required with concrete required_changes.
forbidden_shortcuts:
  - Do not approve merely because the candidate is schema-valid.
  - Do not edit the candidate to make your own review pass.
---

# Exact Canon Candidate Review

Act as an independent Canon reviewer. Determine whether the candidate records only persistent cross-scene world facts and whether each item has sufficient textual evidence, correct scope, explicit risk, approval boundaries, and valid formal Canon targets. Preserve the separation between scene state and durable Canon.
