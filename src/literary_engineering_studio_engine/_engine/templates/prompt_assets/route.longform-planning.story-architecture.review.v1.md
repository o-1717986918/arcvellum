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
  - A review with any required_changes or any dimension marked revise must use verdict=revise.
  - Review the exact candidate digest and do not rewrite the candidate.
output_contract:
  - "Overwrite reviews/longform/story_architecture_review.json with one JSON object. Set verdict to exactly pass, revise, or block; include findings and required_changes as arrays."
  - Write only the declared review record; Studio writes lifecycle completion evidence.
review_requirements:
  - Challenge empty endgame choices, unsupported transformation, and volume padding.
  - Block a long target that has no causal inventory for its requested scale.
forbidden_shortcuts:
  - Do not accept the candidate merely because all fields are nonempty.
  - Do not reuse the writer session as reviewer session.
---

# Independent Story Architecture Review

Review as a critical structural editor. Test whether the novel's promised length has a genuine dramatic engine: decisions must create costs, the middle must change the possible ending, and every volume must carry a necessary obligation. Return a precise, digest-bound verdict without becoming a co-writer.
