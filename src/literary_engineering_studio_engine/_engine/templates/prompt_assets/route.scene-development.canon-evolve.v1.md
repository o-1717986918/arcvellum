---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.scene-development.canon-evolve.v1
match: route.scene-development.canon-evolve.v1
version: v1
route: scene-development
task_type: platform-agent-canon-writeback
title: Scene Canon Evolve Exact Prompt Asset
required_inputs:
  - promoted draft or reviewed candidate
  - scene yaml
  - promotion manifest
  - AgentReview JSON
  - state patch
  - canon directory
context_groups:
  - canon
  - scene facts
  - promoted prose
  - review evidence
  - state patch
hard_constraints:
  - Create candidate canon patch or explicit no-change rationale only.
  - Do not directly modify canon files.
  - Durable cross-scene world facts require user/review approval before application.
style_constraints:
  - none
output_contract:
  - Write canon/patches/{scene_id}_canon_patch.json and Markdown report, then complete the sidecar.
review_requirements:
  - Canon patch remains candidate-only until reviewed and approved.
  - No-change decisions must include no_canon_change_reason.
forbidden_shortcuts:
  - Do not silently skip unknown canon_change.
---

# Exact Canon Evolve Prompt Asset

Classify whether the scene changed durable world facts. Character mood and temporary relation shifts belong to state patches; persistent rules, locations, organizations, history, and cross-scene facts belong in canon patch candidates.
