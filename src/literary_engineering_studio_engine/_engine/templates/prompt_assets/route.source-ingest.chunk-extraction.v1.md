---
schema: literary-engineering-workbench/prompt-asset/v1
prompt_asset_id: route.source-ingest.chunk-extraction.v1
match: route.source-ingest.chunk-extraction.v1
version: v1
route: source-ingest
task_type: platform-agent-extraction
title: Evidence-Bound Archaeology Chunk Extraction
required_inputs:
  - exact source chunk declared by the task package
  - source manifest and evidence index
  - exact chunk extraction sidecar
context_groups:
  - entity observations
  - event observations
  - relation observations
  - factual claims
  - uncertainty and contradictions
hard_constraints:
  - Analyze only the declared chunk and only cite evidence ids allowed by that chunk.
  - Treat every entity event relation and claim as a provisional candidate rather than Canon.
  - Preserve uncertainty contradictions unresolved pronouns and same-name ambiguity explicitly.
  - Do not infer cross-chunk identity or merge aliases inside a chunk.
  - Studio Worker owns schema work chunk path hash evidence revision status and completion metadata.
style_constraints:
  - Use concise semantic labels and summaries rather than copying long source passages.
output_contract:
  - Write one UTF-8 JSON semantic extraction at the declared Agent output path.
review_requirements:
  - Every semantic candidate and attribute has confidence evidence_refs unknowns and contradiction_notes.
forbidden_shortcuts:
  - Do not browse the project search for other chunks invent evidence ids or fill empty collections with plausible material.
---

# Project Archaeology Chunk Extraction

Extract only what the exact source chunk supports. Keep observations separate, preserve competing interpretations, and leave machine identity fields to Studio Worker canonicalization.
