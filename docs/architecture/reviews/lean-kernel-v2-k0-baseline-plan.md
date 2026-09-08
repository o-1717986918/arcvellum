# Lean Literary Kernel v2 - K0 Baseline Change Packet

Status: implemented

Scope: documentation and characterization only

Production behavior change: none

## Purpose

Freeze the externally observable strict-v1 scene sequence before the lean kernel is introduced. The baseline proves rollback compatibility; it must not be used as an argument for keeping the current internal gate count.

## Inputs

- workflow/state_scene.py::_scene_state()
- Task Protocol v2 parser and transport tests
- docs/architecture/arcvellum-lean-literary-kernel-v2-design.md
- observed project metrics from C:/Users/26532/Documents/ArcVellum/Works/兄弟

## Outputs

- tests/fixtures/lean_kernel_v2/strict_v1_scene_baseline.json
- tests/test_lean_kernel_v2_strict_baseline.py

## Invariants

- No production Python, TypeScript, Vue, schema or prompt file changes.
- Existing dirty worktree changes are not staged or rewritten.
- The fixture records a compatibility sequence, not a target v2 design.
- The test creates an isolated minimal project and does not read a user work project.

## Verification

1. Run tests.test_lean_kernel_v2_strict_baseline.
2. Run Task Protocol v2 tests.
3. Run git diff --check.

## Rollback

Remove the fixture, test and this change packet. No data migration or production rollback is needed.

## Exit decision

K0 exits when the compatibility test passes and the v2 design is linked as the current upper-level architecture decision. K1 may then add pure Engine contracts without touching the strict route.
