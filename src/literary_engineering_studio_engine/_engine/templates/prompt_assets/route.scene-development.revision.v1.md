---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.revision.v1
match: route.scene-development.revision.v1
version: v5
route: scene-development
task_type: main-platform-agent-revision
title: Scene Revision Exact Prompt Asset
required_inputs:
  - draft or candidate
  - AgentReview notes
  - deterministic Style Lint evidence
  - style constraints
  - word budget and reader experience contracts
  - narrative rhythm and scene bridge contract
context_groups:
  - prose candidate
  - review notes
  - style
  - word budget
  - reader experience
  - narrative rhythm
hard_constraints:
  - The main platform Agent revises body prose personally.
  - Do not replace a banned contrast with another explicit contrast; use action, fact order, information gap, or direct statement.
  - When review identifies unsupported numeric precision, rewrite the sentence around action, state change, perceived range, or consequence.
  - Every unresolved review finding and every pass_with_notes action must cause a concrete prose edit; returning the original candidate unchanged is a failed revision.
  - Compare the revision against the exact input candidate before submission and record where each required change was applied.
  - Preserve canon and candidate-only writeback boundaries.
style_constraints:
  - Revisions are semantic edits, not regex cleanup.
  - Preserve exact quantities when they serve at least one real function in context: an on-scene answer or decision, identification, causality, continuity, or later verification. Keep established dates, amounts, counts, and differences accurate. Remove only decorative precision after semantic review.
output_contract:
  - Write only the declared revision candidate, revision report, and revision manifest. Studio preserves the CLI prompt manifest and sidecar, then writes lifecycle evidence after deterministic preflight.
review_requirements:
  - Revision candidate must be re-reviewed before promotion or export.
  - Anti-evasion burden-of-proof is required when a transition, contrast, dash, or AI-trace issue is touched.
  - The revision report maps each review action to an observable before/after change or explains why it remains blocking; it may not declare a finding resolved without changing the prose.
forbidden_shortcuts:
  - Do not promote revision without exact AgentReview.
  - Do not copy the draft into the revision field and claim that review notes were addressed.
---

# Exact Revision Prompt Asset

Read the candidate as a reader before editing it as a technician. Identify the passage where a finding actually weakens character, information order, rhythm or the emotional afterlife of the scene. Preserve useful silence, idiosyncratic speech and ordinary detail while repairing that damage; an added explanation can be worse than a carefully placed clue. Make the smallest semantic change that restores the intended experience, and check whether the change alters what the reader knows or what SceneDelta may claim.

Build a short change ledger for every blocking review action, then edit and compare with the exact source. Any retained transition needs its required burden-of-proof note. If the candidate is unchanged, the task is unfinished. Do not turn optional polish into a forced rewrite or flatten a person's voice to satisfy a generic style preference.
