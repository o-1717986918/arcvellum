---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.longform-planning.story-architecture.review.v1
match: route.longform-planning.story-architecture.review.v1
version: v1
route: longform-planning
task_type: platform-agent-story-architecture-review
title: Independent Story Architecture Review Contract
required_inputs:
  - project.yaml
  - plot/story_architecture.candidate.json
  - reviews/longform/story_architecture_review.json
context_groups:
  - candidate digest
  - canon and project constraints
  - ending choice and volume obligations
hard_constraints:
  - Reviewer session must differ from writer session.
  - "verdict must be exactly one of: pass, revise, block. Never emit pass_with_notes."
  - Use block only when the project premise or requested scope needs a new project-level decision; use revise for changes possible within the current direction. A block takes precedence over candidate-local required_changes.
  - Review the exact candidate digest and do not rewrite the candidate.
output_contract:
  - "Overwrite reviews/longform/story_architecture_review.json with one JSON object. Set verdict to exactly pass, revise, or block; include findings and required_changes as arrays."
  - Write only the declared review record; Studio writes lifecycle completion evidence.
review_requirements:
  - Challenge empty endgame choices, unsupported transformation, and volume padding.
  - Test whether the causal spine and volume obligations can plausibly support the target scale. Detailed scene counts and chapter mapping belong to the later budget and inventory reviews.
forbidden_shortcuts:
  - Do not accept the candidate merely because all fields are nonempty.
  - Do not reuse the writer session as reviewer session.
---

# Independent Story Architecture Review

Review as a critical structural editor. Test whether the novel's promised length has a genuine dramatic engine: decisions must create costs, the middle must change the possible ending, and every volume must carry a necessary obligation. Return a precise, digest-bound verdict without becoming a co-writer.

At this stage, do not demand a complete chapter or scene inventory. A missing or weak volume obligation is a revision request when the premise can still sustain it. Reserve `block` for a contradiction that cannot be repaired without changing the user's premise, target, or other project-level direction; describe that decision in findings. `required_changes` may list candidate repairs, but they do not turn a project-level block into `revise`.
