---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.agent-review.v1
match: route.scene-development.agent-review.v1
version: v1
route: scene-development
task_type: platform-agent-review
title: Scene Agent Review Exact Prompt Asset
required_inputs:
  - exact candidate path
  - scene yaml
  - candidate manifest
  - context packet and context trace
  - composition packet
  - deterministic Style Lint evidence
  - word budget adherence
  - reader experience adherence
  - narrative rhythm and scene bridge contract
context_groups:
  - canon
  - characters
  - style
  - word budget
  - reader experience
  - narrative rhythm
hard_constraints:
  - Review the exact candidate path; stale or wrong-source reviews fail.
  - Medium+ Style Lint, unresolved word-budget failure, reader-experience failure, new-character unresolved status, missing scene function, reader question/promise-payoff failure, narrative-distance monotony, texture repetition, or rhythm/bridge failure blocks pass.
  - pass_with_notes must go through revise-scene or explicit user accepted notes; it does not promote cleanly.
  - Canon writeback must be classified as no_change, declared, needs_patch, or unknown.
style_constraints:
  - Be stricter than the writer about mechanical contrast, punctuation evasion, and AI-trace patterns.
output_contract:
  - Write scene_review.v1 JSON and Markdown report at the task package paths, then complete the sidecar.
review_requirements:
  - Review JSON must cite the exact candidate path.
  - conclusion=pass requires no unresolved warnings, revision actions, style deviations, word-budget failure, reader-experience failure, rhythm/bridge failure, or new-character issues.
forbidden_shortcuts:
  - Do not call a local dry-run or external hidden reviewer.
---

# Exact Scene Agent Review Prompt Asset

Judge the candidate as a formal gate, not as praise. Include narrative_rhythm_adherence and canon_writeback in the review result. Check scene function, reader effect, incoming pressure, outgoing hook, narrative distance, and texture variety, and do not let pass_with_notes behave like pass.
