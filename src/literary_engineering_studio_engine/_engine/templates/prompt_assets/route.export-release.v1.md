---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.export-release.*.v1
match: route.export-release.*.v1
version: v1
route: export-and-release
task_type: formal-export-release
title: Export And Release Route Prompt Asset
required_inputs:
  - chapter workspace
  - export manifest
  - approval records
  - publish manifest when present
context_groups:
  - ready scenes
  - final body extraction
  - punctuation normalization
  - docx layout plan
  - release notes
  - rollback state
hard_constraints:
  - Final reader-facing output must hide engineering markers and workflow traces.
  - Export cannot include blocked scenes in formal mode.
  - Publish requires a human approve record and formal-release manifest.
output_contract:
  - Write export package, release approval evidence, or publish artifacts requested by the task.
  - Preserve provenance in manifests while keeping final prose clean.
review_requirements:
  - Check skipped scenes, include_blocked, output existence, DOCX inspection, approval, latest pointer, and trace leakage.
  - Reject custom export scripts as formal delivery substitutes.
forbidden_shortcuts:
  - Do not use --include-blocked or --allow-unapproved.
  - Do not publish output containing scene IDs, canon notes, review notes, writeback candidates, internal paths, or AGENT_TASK markers.
---

# Export And Release Route Prompt

You are packaging a reviewed literary project for readers. Treat manifests as provenance and the exported body as the only reader-facing text. If any gate blocks, repair the upstream route instead of bypassing the official exporter.
