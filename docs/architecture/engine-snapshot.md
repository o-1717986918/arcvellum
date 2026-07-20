# Embedded Engine Snapshot

## Current Snapshot

- Studio baseline: `0.2.1`
- Embedded engine package: `literary_engineering_studio_engine`
- Embedded engine version: `0.100.0`
- Ownership: this repository contains and ships the authoritative Studio copy.
- Runtime relationship to the original Skill repository: none.

## Synchronization Rule

The embedded engine is not refreshed by copying another repository over this directory. A future synchronization is an explicit source review:

1. record the source repository revision and the current Studio revision;
2. compare task registry, route gates, schemas, prompt assets, export behavior, and tests;
3. select individual compatible changes;
4. preserve Studio-only restrictions against direct model providers and bypass flags;
5. update the engine version and this snapshot record;
6. run the Studio suite, engine Prompt Registry validation, and one standalone project smoke test;
7. commit the reviewed synchronization as a dedicated change.

Do not add a Git submodule, runtime path discovery, environment-variable link, or package dependency on the original Skill. Studio must remain independently installable and reproducible.
