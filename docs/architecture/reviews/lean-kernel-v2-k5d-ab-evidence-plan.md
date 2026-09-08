# Lean Kernel v2 K5D: A/B evidence gate

## Scope

Create one small comparison contract for `strict-v1` and `lean-v2`. It records
structural cost separately from blind literary judgement. It must never infer
literary quality from task count, test count, or deterministic lint results.

## Inputs

- Frozen strict-v1 characterization fixture.
- Measured lean route calls, recoverable states, and project Agent task files.
- Optional anonymized literary scores using the rubric in the architecture
  decision record.
- Canon or continuity regression counts from the same sample set.

## Outputs

- JSON report with raw values, reductions, criterion results, and decision.
- `ready-for-default` only when structural targets pass and literary evidence
  is non-inferior.
- `pending-literary-evidence` when model access or blind scores are absent.

## Rollback and verification

The comparison module is read-only and has no production dependency. Removing
it changes no route behavior. Unit tests cover threshold boundaries and prevent
missing scores from producing a passing decision.
