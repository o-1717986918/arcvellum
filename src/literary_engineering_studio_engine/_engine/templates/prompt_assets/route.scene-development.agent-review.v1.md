---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.agent-review.v1
match: route.scene-development.agent-review.v1
version: v4
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

Judge the exact candidate as a formal gate, not as praise. Deterministic clean evidence proves only machine checks; it never proves literary execution. Compare every declared scene obligation--especially external/internal conflict, character choice, scene turn, reader effect, incoming/outgoing bridge, narrative distance, texture, and word budget--with text actually present. Missing or merely asserted obligations require warning or revision even when lint/rhythm projections say pass or not_required. Read the exact candidate, compact evidence, scene, composition, branch, and mounted style; use the full sidecar only for digest conflict or recovery. Write the required `scene_review.v1` JSON and Markdown immediately; do not search beyond sufficient evidence. Include narrative_rhythm_adherence and canon_writeback. pass_with_notes never behaves as pass.
