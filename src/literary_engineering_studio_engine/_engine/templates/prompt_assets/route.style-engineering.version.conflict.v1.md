---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.style-engineering.version.conflict.v1
match: route.style-engineering.version.conflict.v1
version: v1
route: style-engineering
task_type: human-approval-boundary
title: Resolve Immutable Style Version Conflict
required_inputs:
  - conflicting content-addressed version evidence
context_groups:
  - version identity and integrity errors
hard_constraints:
  - Preserve the conflicting artifact until a user-authorized resolution.
  - Never overwrite or patch an immutable version in place.
output_contract:
  - No Agent output is accepted at this human boundary.
review_requirements:
  - A trusted version must pass the deterministic integrity gate.
forbidden_shortcuts:
  - Do not delete evidence or silently reuse the conflicting version.
---

# Resolve Immutable Style Version Conflict

Stop automated execution. The content-addressed version directory exists but
does not match its manifest or current evidence. Preserve the conflicting
artifact for diagnosis, then explicitly restore a trusted copy or quarantine it
before the deterministic build is retried. Never patch it in place.
