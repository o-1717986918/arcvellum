# Literary Engineering Studio

Literary Engineering Studio is the execution platform for the separate [Literary Engineering Project Skill](../literary-engineering-project-skill/README.md). The core remains a reusable Skill and CLI state machine; Studio turns its formal task packages into controlled Agent runs.

The project deliberately does **not** contain an LLM provider or API-key configuration. It can hand a task to the current host Agent, or launch an installed Claude Code or Codex CLI session that already owns its account and model access.

## What Is Already Working

- Reuses the core `task-next -> task-open -> task-submit -> task-complete -> route-audit` loop.
- Validates `agent-task/v1` packages and rejects paths that escape the work project.
- Creates an isolated per-task workspace containing only listed reading, `source_paths`, task files, and expected outputs.
- Rejects writes outside `expected_outputs` before formal-project writeback.
- Preserves backups of replaced expected outputs in the run directory.
- Provides `host-agent`, `claude-code`, and `codex-cli` runtime adapters.
- Reuses the existing workflow dashboard, project library, activity stream, human-choice, and style-library read models.
- Reuses the existing Chinese frontend and adds an Agent Worker execution center.
- Persists background Worker jobs and exposes an SSE status stream.

## Architecture

```text
Literary Engineering core
  task-next / task-open
          |
          v
Studio Agent Worker
  task contract validation
  trusted core-command preflight
  isolated task workspace
          |
          +--> current host Agent
          +--> Claude Code CLI
          +--> Codex CLI
          |
          v
expected-output whitelist and backup
          |
          v
core task-submit / task-complete / route-audit
```

The core is the policy authority. Studio is an execution client. A Studio run can never convert a core gate failure into success.

## Local Setup

```powershell
cd C:\Users\26532\Documents\Codex\2026-07-16\c-users-26532-documents-codex-2026\outputs\literary-engineering-studio
python -m pip install -e ".[api]"
python -m literary_engineering_studio config-init
python -m literary_engineering_studio doctor
```

The default config discovers the sibling `literary-engineering-project-skill` repository. To use another checkout, set `LEW_CORE_REPO` or edit `core.repo` in `%USERPROFILE%\.literary-engineering-studio\config.json`.

No model keys belong in this configuration.

## Formal Commands

Prepare a task for the current host Agent:

```powershell
python -m literary_engineering_studio task-prepare C:\path\to\work-project --route scene-development --runtime host-agent
```

Execute one task with an installed Agent CLI:

```powershell
python -m literary_engineering_studio task-run C:\path\to\work-project --route scene-development --runtime claude-code
python -m literary_engineering_studio task-run C:\path\to\work-project --route scene-development --runtime codex-cli
```

Run the next formal task for a route:

```powershell
python -m literary_engineering_studio agent-worker-once C:\path\to\work-project --route scene-development --runtime claude-code
```

Start the local Studio:

```powershell
python -m literary_engineering_studio serve --port 8791
```

Then open `http://127.0.0.1:8791/`.

## Current Safety Boundary

- Human approval and apply/publish gates pause automatically.
- Runtime tools are scoped to the isolated workspace; Claude Code receives file tools without Bash.
- Codex runs with `workspace-write`, ephemeral sessions, and JSON event output.
- The Worker does not use dangerous permission bypasses.
- Runtime output is not trusted as completion. Only imported files plus successful core validation complete a task.

See [new-studio-architecture.md](docs/architecture/new-studio-architecture.md) and [implementation-route.md](docs/roadmap/implementation-route.md) for the full design and remaining phases.

