# ArcVellum Pi Worker

ArcVellum's bounded literary-task worker, built on Pi Agent Core and Pi AI.

The Worker is an embedded execution component, not a coding agent. It receives
one sandboxed Studio task at a time and has no shell, arbitrary filesystem,
Git, browser, skill loader, extension loader, or subagent tools. ArcVellum
Studio remains authoritative for task selection, sandbox creation,
deterministic preflight, approvals, writeback, workflow gates, and promotion.

The Worker may only:

- read the current task projection and explicitly authorized source files;
- write files listed in the task's `expected_outputs` contract;
- run local existence, format, and model-owned semantic output validation;
- complete the task or report a blocker;
- emit bounded lifecycle, tool, provider, and reasoning-budget events.

## Development

Requires Node.js 22.19 or newer.

```powershell
npm.cmd ci
npm.cmd run check
```

The release build bundles the Worker and its used dependencies into one
JavaScript artifact, then stages that artifact with a pinned Node runtime and
third-party notices under the desktop application resources. The Pi research
fork and a loose `node_modules` tree are not bundled.

Local semantic validation consumes the task package's declared
`semantic_output_contract`; it does not copy literary gates or synthesize
missing judgments. Studio deterministic preflight remains authoritative.
