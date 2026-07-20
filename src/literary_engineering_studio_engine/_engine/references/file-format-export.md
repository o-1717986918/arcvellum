# File Format Export Reference

Use this reference when the user asks for final work delivery in `.docx` or another concrete file format.

## DOCX Export Scope

- Use `export-package --formats md,docx` when exporting a reviewed chapter into the standard novel, screenplay, and video prompt deliverables plus editable Word files.
- Use `export-docx <source.md>` when the user has a final Markdown/text artifact and wants a single Word document.
- Keep Markdown exports as auditable source artifacts. DOCX files are delivery artifacts, not canon.
- Do not write API keys, prompt manifests, `[AGENT_TASK: ...]`, draft review notes, or unapproved candidate metadata into final DOCX files unless the user explicitly requests an internal working copy.
- Before exporting final Chinese prose, check `references/punctuation-standard.md`; DOCX output should not preserve accidental English punctuation in Chinese sentences, wrong ellipses, wrong dashes, or repeated exclamation/question marks.
- Final delivery exports should not expose engineering identifiers or draft workbench sections such as `scene_0001`, `chapter_0001`, scene file paths, context packet paths, canon notes, workflow traces, review state, `## 状态变化`, `## 世界状态变化`, `## 新角色候选登记`, `### 人物状态变化`, or writeback candidates. Keep those in manifests and workbench files only.

## Migrated Office DOCX Rules

The DOCX layer inherits the useful file-handling principles from `office-academic-skill` without importing its academic/PPT workflow:

- Generate editable `.docx` rather than image-only or flattened documents.
- Write a companion DOCX layout plan before/alongside generation so font, heading, page, list, and table choices are auditable.
- Use structured Word headings for titles, chapters, sections, and scene headings.
- Use real Word numbering for bullet and numbered lists; avoid fake list text when possible.
- Convert simple Markdown tables to native Word tables rather than plain pipe-text paragraphs.
- Use Chinese-capable fonts for East Asian text and standard Latin fonts for English/numbers.
- Do not insert raw line breaks inside a text run; create separate paragraphs.
- Validate the package structure after generation: content types, relationships, document XML, styles, numbering, settings.
- Write a companion inspection JSON after generation, including paragraph count, table count, style ids, East Asian font presence, page size/margins, numbering, and warnings.
- Preserve source labels in the manifest rather than embedding internal paths noisily into the final prose.

Not migrated by design: academic paper evidence extraction, PPT template workflows, PowerPoint COM inspection, tracked-change editing, comments/replies, image insertion, formulas, citations, and full OOXML schema validation. Those remain outside the literary delivery baseline unless a future route explicitly needs them.

## Recommended Delivery Flow

1. Run chapter readiness and review gates. Clean delivery requires every scene to be `ready`; `pass_with_notes`, missing RP/branch/composition gates, stale AgentReview, or unresolved style notes block final export.
2. Run:

```powershell
python -m literary_engineering_studio_engine export-package "<work-dir>" --chapter-id chapter_0001 --formats md,docx
```

3. Inspect `exports/{chapter_id}/export_manifest.json`.
4. Inspect generated `*.layout.json` and `*.inspection.json` files, then open the `.docx` files if visual fidelity matters.
5. If publishing, run:

```powershell
python -m literary_engineering_studio_engine publish-chapter "<work-dir>" --chapter-id chapter_0001 --approval-run-id "<approved-run-id>" --export-formats md,docx
```

## Current DOCX Presets

- `novel`: chapter/scene headings use Word heading styles and later major sections start on a new page.
- `screenplay`: preserves scene metadata and dialogue/action text as an editable working draft.
- `video_prompt_pack`: preserves prompt sections, lists, constraints, and notes as a structured Word document.
- `report`: generic document preset for review or project reports.

## Quality Gate

Before delivering a DOCX:

- confirm the source Markdown or export manifest exists;
- confirm `inspect_docx` passes without missing required package parts;
- confirm companion layout and inspection files exist when DOCX is requested;
- confirm the exported Chinese prose has passed the standard punctuation review or has a recorded exception;
- confirm horizontal quote style is unified as `“”` / `‘’`; final exports normalize corner/vertical quotes only as a delivery hygiene step, not as an excuse to skip review;
- confirm the DOCX text does not contain workbench traces such as `世界状态变化`, `状态变化候选`, `scene_0001`, `[AGENT_TASK: ...]`, prompt manifests, canon notes, or review notes;
- ensure final DOCX is not used as canon writeback evidence by itself;
- report the source file, DOCX path, and unresolved formatting limitations.
