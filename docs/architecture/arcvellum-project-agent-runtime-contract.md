# ArcVellum Project Agent Runtime Contract

> Status: D2 implementation contract
>
> Scope: top-level Project Agent bridge and module boundaries
>
> Out of scope: literary-kernel changes, prose generation, write tools, production UI

## 1. Decision

ArcVellum will extend the embedded Pi runtime with one bounded project-level Agent turn. The turn may call Studio-owned typed tools through a bidirectional JSONL bridge. Pi owns model interaction and tool selection. Python owns project capabilities, authorization, persistence, and process lifecycle.

The bridge is a transport boundary, not a second workflow engine. Existing Application Services remain the only implementation of project behavior.

## 2. Module boundaries

```text
Agent UI (later)
  -> ProjectAgentService (later)
  -> ProjectAgentRuntime
  -> bounded Pi project-agent process
       -> AgentTool proxy
       -> JSONL tool.call
  -> ProjectAgentRuntime validates the call
  -> ProjectAgentDependencies / tool handler
  -> existing Application Service or read model
  -> JSONL tool.result
  -> Pi continues and returns turn.complete
```

Python package:

```text
src/literary_engineering_studio/project_agent/
  contracts.py  # transport-neutral DTOs, enums, dependency contract
  runtime.py    # one child process, one turn, bidirectional dispatch
```

Pi Worker package:

```text
workers/pi-worker/src/
  project-agent-protocol.ts  # JSONL validation and pending-call bridge
  project-agent.ts           # Pi Agent Core loop and read-only tool proxies
```

No generic RPC library, event store, state machine, or tool framework is introduced.

## 3. Protocol

Every line is one UTF-8 JSON object with these common fields:

```json
{
  "schema": "arcvellum/project-agent-bridge/v1",
  "type": "tool.call",
  "message_id": "message-id",
  "turn_id": "turn-id",
  "payload": {}
}
```

Host to Pi:

- `turn.start`: session id, user prompt, bounded system prompt, allowed tool names, turn/tool limits.
- `tool.result`: result for one exact `request_id`.
- `turn.cancel`: graceful cancellation request.

Pi to host:

- `bridge.ready`: protocol readiness.
- `agent.event`: streamed, presentation-safe Agent activity.
- `tool.call`: one typed request with `request_id`, tool name, and arguments.
- `turn.complete`: terminal status and visible answer.
- `bridge.error`: terminal protocol or runtime failure.

Limits:

- One process handles one turn and exits.
- A frame is at most 256 KiB.
- A tool result is at most 64 KiB after JSON serialization.
- Unknown message types, duplicate pending request ids, mismatched tool names, and late results fail closed.
- Cancellation rejects every pending tool promise and reaps the child process.

## 4. Initial capability surface

D2 exposes only `project_overview`. D4 may add `project_search` and `creation_observe` after the D3 review. The Node process receives names only and carries no project implementation.

The composition contract names three read models:

```python
ProjectAgentDependencies(
    project_overview=...,
    project_search=...,
    creation_observe=...,
)
```

Each callable is supplied by the Studio composition root and returns JSON-compatible data. Routers are not imported as services, and the Agent process never reads project files directly.

## 5. Lifecycle and recovery

1. Python starts the Pi process with hidden-window subprocess utilities.
2. Pi emits `bridge.ready`.
3. Python sends one `turn.start` envelope.
4. Pi streams `agent.event` and may emit `tool.call`.
5. Python dispatches only an allowed tool and returns `tool.result`.
6. Pi emits exactly one terminal envelope and exits.
7. Python waits for process exit and force-kills only after a bounded grace period.

The production session/job layer will persist user messages, visible replies, and action receipts. The child process itself is disposable. Approval waits will persist the call and terminate the process rather than retaining a dormant Node process.

## 6. Safety boundary

- Top-level Agent tools call existing Application Services.
- The first implementation is read-only.
- Formal prose remains owned by the main creative Worker.
- Project text and tool results are untrusted model context.
- Write tools, when added, require preview/commit, idempotency, a domain revision, and an existing mutation receipt.
- Disabling the feature leaves Advisor, Autopilot, Reader, Archive, Style, Creative Live, Orrery, and Delivery unchanged.

## 7. D2 verification gate

Targeted tests must prove:

- protocol accepts valid frames and rejects malformed, oversized, or unknown frames;
- a scripted Pi model calls `project_overview`, receives its result, continues, and returns visible text;
- tool timeout and cancellation reject pending calls;
- Python dispatches one allowed call and returns one result;
- Python rejects undeclared tools and malformed output;
- timeout/cancellation always terminate and reap the child process;
- no formal project file is written.

Real-provider verification is a separate opt-in smoke test because it consumes user credentials and quota. D4 remains blocked until that smoke test and the D3 architecture review pass.

## 8. Implementation order

1. Land transport-neutral contracts.
2. Land and test the in-process Pi bridge with a faux provider.
3. Add the dedicated `project-agent` process mode without changing the existing task/repair/conversation path.
4. Add and test the Python subprocess runtime.
5. Record the D3 findings before adding session APIs, write tools, or frontend code.

