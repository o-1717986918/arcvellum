---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.continuity-ledger.v1
match: route.scene-development.continuity-ledger.v1
version: v1
route: scene-development
task_type: platform-agent-continuity-ledger
title: Reader Question and Promise Ledger Contract
required_inputs:
  - promoted draft
  - promotion manifest
  - existing reader-question ledger
  - existing promise ledger
context_groups:
  - evidence in exact promoted prose
  - open reader questions
  - promises and payoff windows
  - scene bridge hooks
hard_constraints:
  - Only the main Agent may make the editorial delta judgment.
  - Every ledger change must cite promoted prose evidence.
  - Assess every existing open reader question and promise against the promoted scene before declaring no change.
  - A repeated motif that gains new information, pressure, interpretation, delay, or payoff is an advance of the existing ledger item, not a duplicate.
  - Top-level evidence_paths contains file paths; every change row separately requires a non-empty scalar evidence string grounded in the promoted scene.
  - A review session must differ from the delta writer session.
output_contract:
  - Write only the declared delta/review records and completion evidence.
  - Formal ledgers are changed only by deterministic apply-continuity-ledger.
  - Use the literal lifecycle enum `status: complete` when the record is ready; never invent prose lifecycle labels such as `agent_judged`.
review_requirements:
  - Reject a promise without setup evidence or a question that merely repeats an older open question.
  - Use no_change_reason only when the scene neither affects any existing open item nor creates a new reader question or promise; name the existing open item IDs that were checked and explain why they remain unchanged.
  - Flag overdue questions and promises that are delayed without a new pressure or consequence.
forbidden_shortcuts:
  - Do not infer ledger changes from unpromoted candidates or task commentary.
  - Do not directly edit formal ledger files.
---

# Continuity Ledger

Track what the reader has actually been invited to expect. A ledger entry is not a decorative label: it records a question, promise, delay, payoff, reversal, or closure with textual evidence and a future responsibility. Keep it concise, exact, and causally useful to the next scene.
