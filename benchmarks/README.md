# ArcVellum Benchmarks

Benchmarks are measure-only development tools. They do not change task routing,
project files, quality gates, or runtime model selection.

## Narrative Projection

Run the backend projection benchmark:

```powershell
python scripts/narrative_projection_benchmark.py --repetitions 5
```

Write an explicit evidence snapshot:

```powershell
python scripts/narrative_projection_benchmark.py `
  --repetitions 5 `
  --output benchmarks/baselines/narrative-projection-v0.96.json
```

Run the client layout scale benchmark:

```powershell
npm.cmd run client:benchmark:narrative
```

The committed baseline records the machine and runtime that produced it. Tests
enforce semantic completeness, stable revisions, finite layouts, all six spatial
grammars, and a broad growth trend. They deliberately do not treat one
developer machine's milliseconds as a universal hardware threshold.
