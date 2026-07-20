# Agent Quickstart

This repository is a project-type skill. The platform agent using it is the director.

Read in order:

1. `SKILL.md`
2. `AGENTS.md`
3. `agentread.yaml`
4. `references/project-director-playbook.md`

Then choose one route in `agentread.yaml`. Do not load all docs by default.

Common entry points:

- Project direction / continue: act as director using `references/project-director-playbook.md`.
- New work project: read `templates/work-project/project.yaml` and `docs/implementation/phase1-initializer.md`.
- Style learning: read `docs/modules/style-compiler.md` and Style Skill phase docs.
- Existing text / complete work ingest: read `docs/modules/source-ingest-engine.md` and `docs/implementation/phase64-existing-work-ingest.md`.
- Longform target length / insufficient word count: read `docs/modules/longform-word-budget.md`, `docs/modules/reader-experience-contract.md`, `docs/implementation/phase65-longform-word-budget.md`, and `docs/implementation/phase88-reader-experience-contract.md`.
- Character/world/outline candidates: read asset candidate docs, then write candidate files first.
- Scene work: read plot/character/scene composer docs, then create context, branches, composition, draft candidate, review, and state patch.
- Review/release: read artifact contracts, review CI, canon lint, chapter, longform, export, and publish docs.
- Formal route CLI: read `references/workflows.md` when a route has sidecars, manifests, or provenance gates.
- Orchestration/Dify/LangGraph: read `references/orchestration.md`.

Principle: Codex/Claude owns planning, generation, review, and subagent delegation. Local CLI commands are helpers, not the source of creative authority.
