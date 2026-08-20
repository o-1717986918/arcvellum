# AGENTS

This repository is a standalone Literary Engineering Studio. It embeds the workflow engine, task contracts, prompt assets, schemas, deterministic gates, project templates, and export logic required at runtime.

## Product Boundary

- The embedded engine owns literary routes, task packages, schemas, deterministic checks, promotion, canon, review, export, and release gates.
- The Studio layer owns project lifecycle, user directions, Agent runtime discovery, isolated task workspaces, process execution, writeback, streaming observation, and the user-facing client.
- Do not introduce a runtime dependency on `literary-engineering-project-skill`, `LEW_CORE_REPO`, or another source checkout.
- Do not add a model-provider abstraction, API-key store, direct HTTP LLM client, or hidden fallback model call. Intelligence comes from a connected host Agent or an installed Agent runtime such as Claude Code or Codex CLI.
- The frontend is the primary user client. New project-management or human-decision capabilities should be exposed there instead of requiring users to edit project files.

## Development Entry

Do not discover architecture by searching the whole repository and editing the first matching file.

1. Locate the owning module in `docs/architecture/module-catalog.md`.
2. Follow `docs/architecture/agent-interface-development-standard.md` and write a Module Change Packet before editing.
3. Import Engine behavior only through `literary_engineering_studio_engine.public` surfaces.
4. Compose replaceable infrastructure only through `ApplicationContainer` and Studio-owned ports.
5. Use the owning Vue feature client; components must not call the generic transport directly.

`docs/architecture/module-boundaries.md` contains detailed implementation history. `docs/architecture/generated-module-map.md` is a machine-generated ownership inventory, not a substitute for the stable public interfaces above.

## Worker Constitution

1. Obtain formal work only through embedded `task-next` and `task-open` state-machine operations.
2. Stage only the task package, its listed reading, user-direction digest, and `source_paths`.
3. Allow an Agent runtime to write only `expected_outputs` inside the isolated workspace.
4. Reject unexpected file changes before importing anything.
5. Back up an existing expected output before replacement.
6. Import expected outputs, then call `task-submit` and `task-complete`.
7. Treat `route-audit` as final evidence; Studio must not reinterpret a failed gate as success.
8. Pause at human approval, canon apply, state apply, and release/publish approval tasks.
9. Never enable a debug waiver or `LEW_MAINTAINER_MODE`.
10. The selected external CLI instance is the main Agent for creative tasks. It must not delegate body prose to subagents.
11. Never expose legacy embedded provider commands through Studio API, UI, or public CLI.

These Worker rules describe product execution. They do not authorize code Agents to bypass the module and interface rules in the Development Entry.

## Verification

```powershell
python -m unittest discover -s tests -v
python -m literary_engineering_studio doctor
python -m literary_engineering_studio --help
python scripts/architecture_audit.py
python scripts/generate_module_map.py --check
python -m literary_engineering_studio_engine prompt-registry-validate --json
npm run client:test
npm run client:build
npm run pi-worker:check
```

API work should verify `/health`, `/projects`, `/runtime/adapters`, one read-model endpoint, and one SSE endpoint against a real or freshly initialized work project. Frontend changes require desktop and mobile screenshots plus overlap and horizontal-overflow checks.
