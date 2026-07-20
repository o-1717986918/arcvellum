# Phase 89.1 - Count Unit Bridge Hardening

Completed in `v0.89.1`.

## Background

Two length gates were easy to misread:

- mountable style prompts need a 500-2500 length gate, but that gate should count Chinese content characters, not all non-whitespace characters;
- longform word budgets should compare the user's target against cleaned Chinese deliverable prose, while machine character counts are useful only as diagnostics.

The failure mode was subtle: a model, front-end, or review manifest could see a large machine non-whitespace count from Markdown, ASCII labels, paths, JSON keys, or workflow residue and treat it as if the scene had reached the Chinese prose budget.

## Implemented

- `text_counts.py` now exposes a two-layer mapping:
  - formal Chinese content count: Han characters plus Chinese punctuation;
  - machine nonspace diagnostic count with an observed machine-to-Chinese ratio.
- `chinese_machine_count_mapping()` now reports:
  - `rough_expected_machine_chars` and `rough_expected_machine_chars_range` based on the current cleaned text ratio;
  - `baseline_machine_chars_1_to_1_range` for ordinary Chinese prose;
  - `diagnostic_warning` when machine counts are inflated or unusually low.
- `word_budget_adherence_for_body()` now emits `formal_count_policy`, making `target_chinese_chars/min_chinese_chars/max_chinese_chars` the pass/fail basis and marking `*_words` fields as legacy aliases.
- `export-package` manifests now report:
  - `draft_chars` / `draft_chinese_chars` as cleaned Chinese content characters;
  - `draft_machine_chars` as machine diagnostic characters;
  - explicit `count_unit` and `machine_count_unit`.

## Validation

- `tests/test_text_counts.py` covers Han + Chinese punctuation counting and machine mapping.
- `tests/test_word_budget.py` verifies a scene can pass by Chinese content chars even when ASCII inflates machine chars, while preserving the diagnostic bridge.
- `tests/test_export_package.py` verifies export manifests keep machine counts as diagnostics.

## Operating Rule

For formal pass/fail, always use cleaned Chinese content characters. Machine nonspace counts are only a bridge for UI displays, platform diagnostics, and residue detection.
