# Changelog

All notable ArcVellum changes are documented in this file. Detailed release evidence remains under `docs/releases/`.

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

[0.95.1]: https://github.com/o-1717986918/arcvellum/releases/tag/v0.95.1
[0.95.0]: https://github.com/o-1717986918/arcvellum/releases/tag/v0.95.0
