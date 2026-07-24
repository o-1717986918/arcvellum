# Dual-Workspace Agent Runtime

## Purpose

ArcVellum tasks must be reproducible enough for deterministic CLI validation,
while an Agent must receive only the small, explicit reading set required to
make the current creative decision.  These are different responsibilities and
must not share one filesystem view.

The runtime therefore stages every task into two workspaces beneath one run
directory:

| Workspace | Consumer | Contents | Authority |
| --- | --- | --- | --- |
| `control-workspace/` | Studio CLI and deterministic preflight | Full `source_paths`, command inputs, command-owned outputs, and all validation dependencies | May run formal CLI commands; never shown as an Agent worktree |
| `workspace/` | Agent runtime | Only `agent_source_paths`, compact references, declared outputs, task contract, and project directions | May read and write only the declared Agent contract |

`workspace/` remains the historical path name used in run links and is always
the Agent-visible directory.  It is not a synonym for the control workspace.

## Lifecycle

1. `stage_task` creates both directories and copies the complete formal input
   set into `control-workspace/`.
2. A deterministic core command, when present, executes only in
   `control-workspace/`.
3. The runtime snapshots command-owned files, then materializes `workspace/`
   from the **curated Agent set**.  The Agent does not inherit arbitrary
   project folders merely because the CLI needs them.
4. The Agent writes only `expected_outputs` in `workspace/`.  A baseline hash
   rejects all other changes.
5. `sync_agent_outputs_to_control` copies only those expected outputs into
   `control-workspace/`.
6. Canonicalization and deterministic preflight run against a control-view of
   the sandbox.  They can inspect the whole formal dependency set without
   expanding the Agent's permissions.
7. A successful writeback imports declared outputs from the control workspace
   into the formal project, atomically and with a preview/backup.

## Invariants

- Task Markdown and `TASK_CONTEXT.json` must name only Agent-visible paths.
- `source_paths` may be broader than `agent_source_paths`; this is expected.
- Do not solve a missing Agent input by exposing whole directories.  Add the
  precise file to `agent_source_paths` or derive a compact task reference.
- Do not solve a preflight failure by weakening control validation.  Add the
  necessary formal source to the task's control sources.
- `core_managed_outputs` are snapshotted from control and restored into the
  Agent view before output synchronization, so an Agent cannot rewrite
  CLI-owned evidence.
- The missing-output result is normal before an Agent has performed its task.
  A preflight failure about an unavailable source is a contract defect.

## Debugging Rule

When a run fails, inspect both workspaces before changing a blueprint:

1. Is the file required by the formal command/preflight? It belongs in control
   sources.
2. Does the Agent need to reason from its content? It also belongs in the
   curated Agent source set.
3. Is it an output the Agent must create? It belongs in `expected_outputs`,
   not in an unrestricted project copy.

The repair should change the narrowest of these declarations.  Never make the
Agent workspace a duplicate of the work project merely to make a task pass.
