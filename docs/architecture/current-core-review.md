# Embedded Engine Review

Review source: the formal workflow implementation previously maintained in `literary-engineering-project-skill` version `0.100.0`. The selected engine code and resources are now packaged inside Studio as `literary_engineering_studio_engine`; the original repository is not a runtime dependency.

## Evidence Examined

- Formal CLI surface and handlers.
- Task lifecycle and seven route definitions.
- Task, submission, completion, and Agent-output schemas.
- Workflow dashboard, activity, project library, human-choice, and style read models.
- Prompt registry, packaged templates, references, and project initializer.
- Scene development, review, promotion, character state, canon, word-budget, rhythm, bridge, export, and release gates.
- Historical provider, Dify, LangGraph, and local director modules that must remain outside Studio's formal product surface.

## Strengths Preserved

The formal scene route is not a loose checklist. It validates context traces, RP and branch sidecars, formal branch selection, composition provenance, word budget, reader experience, narrative rhythm and bridge, generation provenance, exact-candidate AgentReview, Style Lint, promotion, static review, state evolution, and canon writeback classification.

The task package provides a strong boundary:

- task identity, route, state, and task type;
- prompt asset identity and inlined prompt body;
- required reading and source paths;
- hard, style, and word-count constraints;
- expected outputs;
- submission and completion commands;
- validation gates and forbidden shortcuts.

The reused read models translate project artifacts into Chinese dashboard cards, readable prose, project-library sections, activity lanes, human decisions, and SSE snapshots.

## Embedded Boundary

Studio packages the following as one installable product:

- route selection and state derivation;
- prompt registry and prompt assets;
- scene, style, source-ingest, asset, review, canon, state, export, and release rules;
- deterministic lint, counts, schema checks, provenance, promotion, and audits;
- task lifecycle records;
- project templates, DOCX, and delivery packaging;
- dashboard, activity, library, human-choice, and style read models.

The package namespace was renamed to `literary_engineering_studio_engine` to avoid collision with an independently installed Skill. Resource lookup now resolves package-owned `_engine` files, not an external checkout.

## Legacy Capability Policy

The migrated source history contains earlier experiments with HTTP model providers, model profiles, a local director, Dify, and LangGraph. Studio does not expose these routes in its frontend, API, configuration, or public `les` CLI.

The embedded engine bridge explicitly rejects:

- `agent-run` and provider-based `agent-repair`;
- `director-chat`;
- `config-show`, `config-init`, and `config-set-profile` from the old engine;
- `serve-api`, `run-workflow`, `run-langgraph`, and `dify-dsl`;
- model API-key arguments and non-`platform-agent` provider values.

Historical files remain migration references until a later cleanup can remove them without weakening formal workflow behavior. They are not part of the supported execution path.

## Current Gaps

1. Engine output remains mostly human-readable `key: value` text rather than versioned JSON.
2. Task commands are shell-like strings instead of structured argv; Studio therefore parses a strict grammar and rejects shell syntax.
3. The task schema should eventually declare `execution_policy`, `human_gate`, `agent_role`, and runtime capabilities explicitly.
4. Expected outputs still mix deterministic, Agent-authored, and completion artifacts.
5. Required-reading paths do not explicitly distinguish project and package resources.
6. The embedded snapshot is now Studio-owned; future upstream improvements require an intentional reviewed synchronization process rather than runtime discovery.

## Conclusion

The engine is mature enough to serve as Studio's embedded policy kernel. The correct architecture is one standalone repository with two clear layers: a deterministic literary workflow engine and a user-facing Agent execution client. Creative intelligence remains in the selected external Agent runtime.
