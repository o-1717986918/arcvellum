---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.source-ingest.materialize-candidates.v1
match: route.source-ingest.materialize-candidates.v1
version: v1
route: source-ingest
task_type: deterministic-cli
title: Deterministic Archive Candidate Materialization
required_inputs:
  - current source and reconstruction revisions
  - passed archaeology domain review
context_groups:
  - promotable asset decisions
  - Archive candidate identities
  - archaeology provenance
hard_constraints:
  - Run the exact core command without Agent-authored file writes.
  - Materialize only assets approved by the domain review.
  - Keep every output in registered Archive candidate directories.
style_constraints:
  - none
output_contract:
  - Core writes Archive candidates creation receipts and one reproducible materialization manifest.
review_requirements:
  - Every resulting candidate still requires exact-content Archive review and user approval.
forbidden_shortcuts:
  - Do not materialize analysis-only held rejected or stale assets and do not write formal project truth.
---

# Project Archaeology Materialization

Move passed reconstruction assets into the existing Archive candidate lifecycle. This command does not promote them.
