---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.agent-review.v1
match: route.scene-development.agent-review.v1
version: v6
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
  - pass_with_notes must contain at least one exact, actionable unresolved finding and must go through revise-scene or an explicit candidate-bound acceptance; it does not promote cleanly.
  - Deterministic low/info findings below the configured threshold are diagnostics, not revision obligations by themselves. Keep them as `blocks_pass: false` evidence under a clean pass unless an independent scene-specific literary defect is demonstrated from exact prose.
  - Never turn an already-satisfied revision action into a new action merely to drive a metric toward zero. Verify the prior action against its stated target and current threshold.
  - Canon writeback must be classified as no_change, declared, needs_patch, or unknown.
style_constraints:
  - Be stricter than the writer about mechanical contrast, punctuation evasion, and AI-trace patterns.
output_contract:
  - Write only the declared review JSON and Markdown report. Studio writes the protected sidecar and lifecycle receipt after deterministic preflight.
review_requirements:
  - Review JSON must cite the exact candidate path.
  - Review JSON candidate_sha256 must equal the digest supplied in the task package.
  - conclusion=pass requires no actionable warning, revision action, actionable style deviation, word-budget failure, reader-experience failure, rhythm/bridge failure, or new-character issue. `style_notes` is an evidence ledger for positive or neutral observations and may be non-empty. A below-threshold lint observation or approved waiver may remain as a low/info warning or deviation only with `blocks_pass: false`; set `style_adherence.status=pass` when these are the only style observations.
  - Every revision action is blocking by definition. Do not put `blocks_pass: false` on a revision action. Move optional polish to `style_notes` or a non-blocking warning.
  - Always emit a complete `revision_integrity` object. For an original, never-revised candidate use `status=not_applicable`, but still set `anti_evasion_checked=true` and `evasion_risks_unresolved=[]`. For a revised candidate use `status=pass` only after checking the exact revision source and current candidate; incomplete integrity evidence is a review-artifact failure, not a reason to revise the prose again.
forbidden_shortcuts:
  - Do not call a local dry-run or external hidden reviewer.
---

# Exact Scene Agent Review Prompt Asset

Judge the exact candidate as a formal gate, not as praise. Deterministic clean evidence proves only machine checks; it never proves literary execution. Compare every declared scene obligation--especially external/internal conflict, character choice, scene turn, reader effect, incoming/outgoing bridge, narrative distance, texture, and word budget--with text actually present. Missing or merely asserted obligations require an exact actionable finding even when lint/rhythm projections say pass or not_required. Read the exact candidate, compact evidence, scene, composition, branch, and mounted style; use the full sidecar only for digest conflict or recovery. Write the required `scene_review.v1` JSON and Markdown immediately; do not search beyond sufficient evidence. Include narrative_rhythm_adherence and canon_writeback. Use pass_with_notes only for unresolved work, never for harmless diagnostics or optional polishing.
