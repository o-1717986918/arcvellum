# Contributing to ArcVellum

ArcVellum is a local literary-engineering studio. Contributions should preserve its central boundary: Agents may supply creative judgment, while the formal project state machine validates every durable write.

## Before opening a pull request

1. Locate the owner and stable entry in `docs/architecture/module-catalog.md`.
2. Follow `docs/architecture/agent-interface-development-standard.md` and record a Module Change Packet before editing.
3. Create a focused branch from `main`; keep contract changes, adapter migrations, behavior changes, tests, and release metadata reviewable.
4. Do not commit credentials, generated installers, local work projects, full prose fixtures, model transcripts, or private paths.
5. Update tests whenever a task contract, API response, route gate, prompt asset, or desktop resource contract changes.
6. Update user-facing documentation when behavior, installation, privacy, or release steps change.

## Required local checks

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src
python scripts/architecture_audit.py
python scripts/generate_module_map.py --check
python scripts/verify_version_sync.py
python -m literary_engineering_studio_engine prompt-registry-validate --json
npm run client:test
npm run client:build
npm run pi-worker:check
```

For changes to packaging, Tauri resources, sidecars, or updater metadata, also run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging/build_desktop.ps1 -SkipPythonInstall -SkipNodeInstall
```

## Pull request expectations

- Explain the user-visible behavior and the route or task contract affected.
- Name one primary owning module, its stable public entry, allowed dependencies, and invariants.
- State which checks were run and what was not run.
- Keep generated build outputs out of Git unless they are explicit source resources required by the desktop bundle.
- Never weaken a formal gate, review, approval, sandbox, or path-validation rule merely to make a task advance.
- Do not raise `architecture/quality-baseline.json` to admit new debt. Existing oversized-file and function counts are a ratchet, not an allowance.

## Development boundary

`AGENTS.md` defines the operational constraints for tool-layer agents. Module ownership is in `docs/architecture/module-catalog.md`; the required development loop is in `docs/architecture/agent-interface-development-standard.md`; detailed implementation history is maintained in `docs/architecture/module-boundaries.md`. Release-specific requirements live in `docs/releases/RELEASING.md`.
