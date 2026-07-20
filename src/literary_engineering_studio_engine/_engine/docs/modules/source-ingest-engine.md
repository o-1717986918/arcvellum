# Source Ingest Engine

`source-ingest` lets a work project accept existing texts, old drafts, complete works, scripts, or pseudo-record materials as engineering input.

Its purpose is not to let the local CLI “understand” literature. The CLI performs deterministic preparation:

1. store source text under `sources/imports/{work_id}/raw/`;
2. normalize and split it into chunk files;
3. write `source_manifest.json` and `source_ingest.md`;
4. write `extract_project_files.agent_tasks.md` for the platform agent.

The platform agent then performs the creative and analytical work.

## Use Cases

- Continue a user-owned old draft without losing existing continuity.
- Rewrite a complete work into a new structure while preserving stable facts.
- Convert a script, pseudo-record file, or fragmented notes into a structured work project.
- Extract a project brief, character map, world rules, outline, timeline, foreshadowing, and style notes from source material.

## Command

```powershell
python -m literary_engineering_workbench protocol source-ingest
python -m literary_engineering_workbench source-ingest "<work-dir>" --source "<source-file-or-dir>" --title "源作品" --work-id source-work
```

Short pasted text can use:

```powershell
python -m literary_engineering_workbench source-ingest "<work-dir>" --text "源文本片段" --title "旧稿" --work-id old-draft
```

Supported text file extensions are `.txt`, `.md`, and `.markdown`.

## Output Contract

Import artifacts:

```text
sources/imports/{work_id}/raw/*.txt
sources/imports/{work_id}/chunks/chunk_0001.md
sources/imports/{work_id}/source_manifest.json
sources/imports/{work_id}/source_ingest.md
sources/imports/{work_id}/extract_project_files.agent_tasks.md
```

Expected platform-agent candidate outputs:

```text
sources/imports/{work_id}/extracted/project_brief.md
characters/candidates/extracted/{work_id}_characters.md
canon/candidates/extracted/{work_id}_world.md
plot/candidates/extracted/{work_id}_outline.md
plot/candidates/extracted/{work_id}_timeline.md
plot/candidates/extracted/{work_id}_foreshadowing.md
style/candidates/{work_id}_style_generation_notes.md
reviews/source_ingest/{work_id}_extraction_review.md
```

## Platform Agent Duties

When executing the sidecar, the platform agent should:

- separate confirmed source evidence from inference;
- attach `evidence_refs`, confidence, unknowns, and contradiction notes to important claims;
- classify characters as `major`, `secondary`, or `cameo`;
- preserve `background_story` as hidden behavioral causality;
- extract world rules, locations, organizations, limitations, and loopholes;
- reconstruct outline, timeline, setup/payoff, unresolved questions, and continuation hooks;
- extract style notes as generation guidance, not as a mountable Style Skill yet;
- write a review report with risks and promotion recommendations.

## Guardrails

- Source-derived material is evidence, not canon.
- Do not overwrite `canon/`, `characters/{id}.yaml`, `plot/outline.md`, `style/active_style_skill.json`, drafts, exports, or releases.
- Do not copy long source passages into candidate files.
- Do not treat source-derived style notes as a reliable Style Skill until converted into a reviewed 500-2500 Chinese-content-character LLM-facing prompt.
- For protected or unauthorized sources, use abstract craft analysis and avoid exact imitation or continuation that would imply rights ownership.
