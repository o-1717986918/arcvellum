# Current Core Review

Review target: `literary-engineering-project-skill` version `0.100.0`.

## Evidence Examined

- 306 tracked project files reported by the repository file scan.
- 285 unit tests completed successfully on 2026-07-20.
- Formal CLI surface and handlers in `cli.py`.
- Task lifecycle and seven route definitions in `task_registry.py`.
- Task, submission, and completion schemas.
- Workflow dashboard, activity, project library, human-choice, and style read models.
- Current frontend and SSE observation endpoints.
- Historical model config, HTTP Agent provider, creative director, and workflow-runner code.

## What The Core Already Does Well

The formal scene route is not a loose checklist. It validates context traces, RP and branch sidecars, formal branch selection, composition provenance, word budget, reader experience, narrative rhythm and bridge, generation provenance, exact-candidate AgentReview, Style Lint, promotion, static review, state evolution, and canon writeback classification.

The task package contract is a strong integration boundary. It already provides:

- task identity, route, state, and task type;
- prompt asset identity and inlined prompt body;
- required reading and source paths;
- hard and style constraints;
- word-count bounds;
- expected outputs;
- submission and completion commands;
- validation gates and forbidden shortcuts.

The frontend read models are also mature enough to reuse: they translate project artifacts into Chinese dashboard cards, readable prose, project-library sections, activity lanes, user decisions, and SSE snapshots.

## What Must Stay In The Core

- All route selection and state derivation.
- Prompt registry and prompt assets.
- Scene, style, source-ingest, asset, review, canon, state, export, and release rules.
- Deterministic lint, counts, schema checks, provenance, promotion, and audits.
- Task schema authority and task lifecycle records.
- DOCX and delivery packaging.

Copying these modules would create two policy authorities and inevitable version drift. Studio therefore invokes the core CLI instead of forking them.

## What Was Reused In Studio

| Core capability | Reuse method |
| --- | --- |
| Formal CLI state machine | Subprocess bridge to the existing Python module |
| Task/submission/completion contract | Versioned schema snapshots plus consumer validation |
| Workflow dashboard | Direct import of the core read model |
| Agent activity and task package summaries | Direct import of the core read model |
| Project library and cleaned prose display | Direct import of the core read model |
| Human choices and safe display edits | Direct import of the core service |
| Style library and mounts | Direct import of the core service |
| Chinese frontend, CSS, editorial icons | Copied as the Studio visual baseline |

## What Was Deliberately Not Migrated

- `model_config.py`, `agent_provider.py`, and HTTP chat generation.
- DeepSeek or other API-key UI and endpoints.
- The early creative-director conversation loop.
- Dify/LangGraph model orchestration.
- `workflow_runner.py` as an alternative route engine.

Those modules belong to the old optional internal-LLM experiments. The new product direction uses platform Agent runtimes and keeps one formal state machine.

## Integration Gaps Found

1. CLI output is human-readable `key: value` text rather than a versioned machine JSON mode. Studio currently parses the stable key lines. A future core `--json` mode should replace this adapter detail.
2. A task `command` is a shell-like string, not structured argv. Studio accepts only a strict `python -m literary_engineering_workbench` grammar and rejects shell operators and formal bypass flags.
3. The task schema does not explicitly declare `execution_policy`, `human_gate`, `agent_role`, or `runtime_capabilities`. Studio uses conservative state-name detection until the core contract adds these fields.
4. `expected_outputs` mixes deterministic CLI products, Agent-authored products, and sidecar completion records. A future contract should split `preflight_outputs`, `agent_outputs`, and `core_completion_outputs`.
5. The existing API server is monolithic: read models, model credentials, HTTP LLM execution, director tools, style tools, and workflow endpoints share one application. Studio reuses the underlying read-model functions instead of mounting the whole app.
6. Required-reading paths do not distinguish project-relative resources from core-owned resources. Prompt bodies are fortunately inlined into task Markdown, but the next schema should add a resource origin.
7. External Agent process capability is not part of the core contract. Studio owns runtime detection, permission policy, timeout, logs, and sandbox writeback.

## Review Conclusion

The core is mature enough to remain the product kernel. The new repository should not replace it. The correct next move is a separate execution plane that consumes formal tasks, runs platform Agents in isolation, and returns evidence to the existing gates.

