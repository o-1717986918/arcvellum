---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.style-engineering.version.build.v1
match: route.style-engineering.version.build.v1
version: v1
route: style-engineering
task_type: deterministic-cli
title: Build Immutable Style Version
required_inputs:
  - passing independent style semantic review
  - accepted deterministic evaluation
  - current formal style session
context_groups:
  - source rights and content digests
  - prompt, evaluation, and review evidence
hard_constraints:
  - Derive version identity and destination from current evidence.
  - Write atomically and never overwrite an existing immutable version.
output_contract:
  - Write style_version.json and the declared legacy-compatible package files.
review_requirements:
  - Revalidate every formal Gate and packaged artifact digest.
forbidden_shortcuts:
  - Do not invent a version, mount it, or patch an existing version directory.
---

# Build Immutable Style Version

Run the exact deterministic command from the task package. The Engine owns the
version ID, destination, content hash, evidence inventory, compatibility
manifest, and atomic write. Do not edit source evidence, invent a version, mount
the result, or replace an existing version directory.
