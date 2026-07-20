# Orchestration

In the project-type skill architecture, Codex, Claude, or another tool-layer platform is the primary orchestrator. LangGraph, Dify, FastAPI, and the local workflow runner are optional integration layers.

Do not rebuild the full Creative Director inside the repository unless the user explicitly asks for local/offline orchestration. Prefer to expose stable file contracts and helper commands so the platform agent can plan, delegate, observe, and revise directly.

Any orchestration node that calls an LLM, drafts JSON, creates prose, simulates characters, scores branches, proposes writebacks, or chooses a route must return auditable artifacts to the supervising platform agent. The adapter may execute a node, but the tool-layer agent remains responsible for final creative judgment, canon/style/schema checks, user-facing decisions, and promotion approval.

The current implementation is intentionally file-backed and CLI-first. Treat every command as a future workflow node.

## Recommended Stack

- Core state machine: LangGraph.
- Reviewer console and human input: Dify Workflow / Chatflow.
- Retrieval layer: LlamaIndex + Qdrant.
- Structured facts: SQLite first, PostgreSQL later.
- Graph layer: Neo4j later, fed by `plot/longform_graph.json`.
- Durable execution: Temporal later, only after workflow shape stabilizes.

## Node Graph

Recommended graph:

```text
LoadProjectState
  -> RetrieveMemory
  -> BuildContextPacket
  -> CharacterSimulation
  -> WorldConsequence
  -> DirectorSelection
  -> DraftWorkspace
  -> DraftWriter
  -> ReviewCI
  -> ChapterWorkspace
  -> LongformAudit
  -> StateWriteback
  -> ExportPackage
```

## CLI To Node Mapping

| Workflow node | CLI command |
| --- | --- |
| LoadProjectState | file read / `init` |
| RetrieveMemory | `index`, `search` |
| PlanWordBudget | `word-budget`, `longform-budget` |
| BuildContextPacket | `context` |
| CharacterSimulation | `simulate-scene` |
| DraftWorkspace | `draft-scene` |
| ReviewCI | `review-scene` |
| ChapterWorkspace | `chapter-workspace` |
| LongformAudit | `longform-audit` |
| ExportPackage | `export-package` |
| PlatformBlueprint | `orchestration-plan` |
| WorkflowRunner | `run-workflow` |
| LangGraphAdapter | `run-langgraph` |
| DifyHttpBackend | `serve-api` |
| GlobalConfig | `config-init`, `config-show`, `config-set-profile` |
| LocalConsole | `serve-api` `/` |
| AssetWorkshop | `agent-create-*`, `asset-create`, `review-candidate-asset`, `promote-candidate-asset` |

## Local Runner And LangGraph

Use `run-workflow` before building external adapters:

```powershell
python -m literary_engineering_studio_engine run-workflow "<work-dir>" --mode full-cycle
```

This creates:

- `workflow/runs/{run_id}/workflow_state.json`
- `workflow/runs/{run_id}/workflow_log.md`

LangGraph should wrap the same node functions. Dify should display these state/log artifacts and collect approval when `human_approval_required` is true.

When optional orchestration dependencies are installed, `run-langgraph` executes a real LangGraph `StateGraph`:

```powershell
python -m literary_engineering_studio_engine run-langgraph "<work-dir>" --scene scenes/scene_0001.yaml --chapter-id chapter_0001
```

Current graph:

```text
START -> scene_loop -> chapter_publish -> END
```

Later graph expansion should keep using the same file-backed workbench functions so that CLI, LangGraph, and Dify do not drift.

## Dify Role

Dify is a frontend reviewer console, not the source of truth.

Good Dify uses:

- collect `project_root`, `chapter_id`, `scene_id`, task type;
- display context packets, context traces, simulations, drafts, reviews, audits, and exports;
- collect `Approve`, `Revise`, `Reject`, and comments through Human Input;
- call a workbench backend through HTTP Request.

Start that backend with:

```powershell
python -m literary_engineering_studio_engine serve-api --host 127.0.0.1 --port 8765 --allowed-root "<parent-workspace>"
```

Use these endpoints:

- `GET /health`
- `GET /`
- `GET /config`
- `POST /config`
- `POST /director/chat`
- `GET /director/status`
- `POST /assistant/chat`
- `POST /asset/create`
- `GET /asset/candidates`
- `POST /asset/review`
- `POST /asset/promote`
- `POST /workflow/run`
- `GET /workflow/runs/{run_id}`
- `GET /workflow/artifact`
- `POST /workflow/approve`

Project-type Skill note: Dify is optional. When Codex or Claude is already supervising the project, let the tool-layer agent hold the user conversation, inspect files, call subagents, and edit artifacts directly. Use `/director/chat` only as a legacy/local bridge when you explicitly want the built-in workbench director to run inside `serve-api`. `/workflow/run`, `/asset/*`, `/style-lab/*`, and artifact endpoints remain useful as deterministic helpers behind a platform-agent-led workflow.

Do not let Dify:

- directly edit `canon/`;
- bypass `review-scene`;
- export blocked scenes as deliverables;
- treat Knowledge Retrieval output as confirmed canon.

## Human Approval Gates

Require explicit approval for:

- confirmed canon;
- major character turn;
- main plot branch merge;
- final chapter export;
- exact public-domain or authorized style reproduction mode;
- blocked-scene preview export.

## Knowledge Base Plan

Short term:

- `memory/index.json` is the lightweight index.
- `memory/context_packets/*.md` are working memory packets.
- `memory/context_packets/*.trace.json` are machine-readable context provenance records and are required for formal scene work.
- `plot/longform_graph.json` is the portable graph.

Later:

- LlamaIndex handles ingestion and retrieval workflows.
- Qdrant handles vector search.
- SQLite/PostgreSQL handles structured facts and approvals.
- Neo4j handles relationships, scene order, causality, and foreshadowing.

## Adapter Principle

Adapters should call the same CLI functions or equivalent backend endpoints. They should not create parallel file formats unless a migration plan is provided.
