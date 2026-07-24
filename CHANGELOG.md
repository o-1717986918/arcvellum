# Changelog

All notable ArcVellum changes are documented in this file. Detailed release evidence remains under `docs/releases/`.

## [0.95.2] - 2026-07-25

### Fixed

- Separated formal CLI control inputs from Agent-visible task inputs so a model never receives paths that its sandbox denies, preventing repeated read failures and missing-output false blockers.
- Prevented passing scene reviews from reopening revisions merely because they contain explanatory Style Lint evidence or explicitly non-blocking, low-risk warnings.
- Bound scene-review candidate paths deterministically so revision tasks retain the exact reviewed source instead of falling back to an ambiguous in-place candidate.
- Moved continuity-ledger validation into Studio preflight so an untouched pending ledger template is repaired inside the Agent session instead of failing only after formal CLI writeback.

### Changed

- Strengthened the Agent review contract: positive style evidence is recorded separately from actionable findings, while unclassified warnings still block promotion.
- Made continuity-ledger task packages spell out the required prose evidence or no-change rationale, while Studio owns lifecycle receipts and session binding.
- Verified the real full-auto route through exact review, promotion, and the first promoted formal prose draft.

## [0.95.1] - 2026-07-24

### Fixed

- Prevented duplicate deterministic task renders from invalidating a completed word-budget platform-agent receipt solely because a sidecar timestamp changed.
- Bound modern task completion receipts to a task-content digest; a materially reissued task still requires fresh completion evidence.
- Made Windows CI provision the same bundled OpenCode resources required by the Tauri desktop package.

### Changed

- Added repository maintenance governance files and protected `main` with required CI checks, pull-request review, resolved-conversation, no-force-push, and no-deletion rules.

## [0.95.0] - 2026-07-24

### Added

- Formal task-contract coverage for longform planning, scene development, review, promotion, state evolution, and continuity evidence.
- Version synchronization and sidecar-provenance checks for desktop releases.
- Modular Studio and engine boundaries with expanded contract and route tests.

### Changed

- Strengthened automatic task execution, word-budget propagation, rhythm/continuity context, and formal writeback validation.
- Published the signed Windows installer and automatic-update manifest for `v0.95.0`.

### Fixed

- Candidate output, lifecycle status, and continuity-ledger edge cases found during end-to-end scene promotion testing.

[0.95.2]: https://github.com/o-1717986918/arcvellum/releases/tag/v0.95.2
[0.95.1]: https://github.com/o-1717986918/arcvellum/releases/tag/v0.95.1
[0.95.0]: https://github.com/o-1717986918/arcvellum/releases/tag/v0.95.0
