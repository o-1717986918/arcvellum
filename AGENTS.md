# AGENTS

This repository is the Agent execution platform for the separate `literary-engineering-project-skill` core.

## Product Boundary

- The core repository owns literary routes, task packages, prompt assets, schemas, deterministic checks, promotion, canon, review, export, and release gates.
- This Studio owns Agent runtime discovery, isolated task workspaces, process execution, output collection, streaming observation, and user-facing execution controls.
- Do not copy or fork core route logic into this repository.
- Do not add a model-provider abstraction, API-key store, direct HTTP LLM client, or hidden fallback model call. Intelligence comes from a connected host Agent or an installed Agent runtime such as Claude Code or Codex CLI.

## Worker Constitution

1. Obtain formal work only through the core `task-next` and `task-open` commands.
2. Stage only the task package, its listed reading, and its `source_paths`.
3. Allow an Agent runtime to write only `expected_outputs` inside the isolated workspace.
4. Reject unexpected file changes before importing anything.
5. Back up an existing expected output before replacement.
6. Import expected outputs, then call core `task-submit` and `task-complete`.
7. Treat core `route-audit` as the final evidence; Studio must not reinterpret a failed gate as success.
8. Pause at human approval, canon apply, state apply, and release/publish approval tasks.
9. Never enable a core debug waiver or `LEW_MAINTAINER_MODE`.
10. The selected external CLI instance is the main Agent for creative tasks. It must not delegate body prose to subagents.

## Verification

Run from this repository:

```powershell
python -m unittest discover -s tests -v
python -m literary_engineering_studio doctor
python -m literary_engineering_studio --help
```

Frontend JavaScript must pass a syntax check before commit. API work should also verify `/health`, `/runtime/adapters`, and one read-model endpoint against a real Literary Engineering work project.

