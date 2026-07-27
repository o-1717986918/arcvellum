---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.agent-review.v1
match: route.scene-development.agent-review.v1
version: v3
route: scene-development
task_type: platform-agent-review
title: Scene Agent Review Exact Prompt Asset
required_inputs:
  - exact candidate path
  - digest-bound compact review evidence
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
  - Review the exact candidate path and candidate_sha256 supplied by the task; stale or wrong-content reviews fail.
  - Treat the compact review evidence as the authoritative deterministic projection. Its candidate, full-sidecar, and output-schema digests must match; use the full sidecar only as exact-on-demand recovery evidence.
  - Medium+ Style Lint, unresolved word-budget failure, reader-experience failure, new-character unresolved status, missing scene function, reader question/promise-payoff failure, narrative-distance monotony, texture repetition, or rhythm/bridge failure blocks pass.
  - pass_with_notes must go through revise-scene or explicit user accepted notes; it does not promote cleanly.
  - Canon writeback must be classified as no_change, declared, needs_patch, or unknown.
style_constraints:
  - Be stricter than the writer about mechanical contrast, punctuation evasion, and AI-trace patterns.
output_contract:
  - Write only the declared review JSON and Markdown report. Studio writes the protected sidecar and lifecycle receipt after deterministic preflight.
review_requirements:
  - Review JSON must cite the exact candidate path.
  - Review JSON candidate_sha256 must equal the digest supplied in the task package.
  - conclusion=pass requires no unresolved warnings, revision actions, style deviations, word-budget failure, reader-experience failure, rhythm/bridge failure, or new-character issues. `style_notes` is an evidence ledger only: use it for concise positive or neutral observations; put every actionable style defect in warnings, revision_actions, or style_adherence.deviations. A below-threshold lint observation or an already-approved waiver may be retained only as a structured low/info warning with `blocks_pass: false`; otherwise a warning is treated as unresolved.
forbidden_shortcuts:
  - Do not call a local dry-run or external hidden reviewer.
---

# Exact Scene Agent Review Prompt Asset

Judge the candidate as a formal gate, not as praise. First read the exact candidate, the digest-bound compact review evidence, scene definition, composition review, branch selection, and mounted style evidence. The compact evidence carries exact deterministic Style Lint, word-budget, reader-experience, rhythm/bridge, style-version, output-schema, and digest contracts. The full CLI review sidecar remains available on demand for recovery or evidence conflict; do not reread it by default when the compact evidence validates. Then immediately write the required `scene_review.v1` JSON and Markdown report. Do not inspect directories, search for more project files, or keep gathering background after those materials are sufficient. Include narrative_rhythm_adherence and canon_writeback in the review result. Check scene function, reader effect, incoming pressure, outgoing hook, narrative distance, and texture variety, and do not let pass_with_notes behave like pass.
