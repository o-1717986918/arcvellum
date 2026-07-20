# Formal Host Operating Constitution

This document is the authority layer for platform agents that use this Skill as a project operating system.

## Authority Order

1. `task-next` chooses the next formal task for a registered route. Do not choose a lower-level command from memory when this loop is available.
2. `task-open` is the executable task package. Read its prompt asset, source artifacts, expected outputs, validation gates, and forbidden shortcuts before acting.
3. `.agent_tasks.md` files are live work for the current platform agent. They are not completed just because a CLI command wrote them.
4. `task-submit` records the artifact the platform agent produced.
5. `task-complete` validates expected outputs and writes the route event. A task is not complete before this succeeds or an exact failure is recorded.
6. `route-audit` is the formal pass/fail ledger for route readiness.
7. `workflow-dashboard` is a read-only cockpit. It summarizes state; it does not advance work.
8. `workflow-state` is a navigation summary. It helps find the next open step but does not replace `route-audit`.
9. Low-level commands such as `context`, `simulate-scene`, `compose-scene`, `generate-scene`, `agent-review-scene`, `state-evolve`, `canon-evolve`, `chapter-workspace`, and `export-package` are route internals unless the current task package explicitly tells the platform agent to run them.

Bare `lew --help` is intentionally small and state-machine-first. `help-all` is a maintainer/debug map, not the ordinary operating menu for formal project work.

## Formal Host Duties

- The platform agent must probe documented commands before declaring them unavailable.
- The platform agent must read sidecars and create completion markers after expected artifacts are checked.
- Creative body prose, revisions, final text, branch decisions, semantic reviews, style prompts, and LLM-authored JSON belong to the main platform agent. Subagents may gather evidence, summarize, count, lint, or check schema, but they must not ghostwrite final body text.
- Debug flags are not operating instructions. Formal hosts must not use bypass flags to skip review, approval, composition, branch selection, or export readiness.
- Formal hosts must not set `LEW_MAINTAINER_MODE=1`; that switch is reserved for explicit repository maintenance and regression tests.
- Every persistent fact remains candidate-only until the relevant review/approval/promotion route accepts it.

## Scene-Development Non-Negotiables

Formal scene development is per scene. Each scene must travel through the CLI-mediated chain: context and trace, roleplay sidecar, branch sidecar and formal branch selection, composition, prose generation task, exact-candidate AgentReview, promotion, promoted draft, static review, state-evolve, and canon-evolve when the scene declares durable world facts or cannot rule them out.

`generate-scene` writes a prompt manifest and sidecar. It does not mean prose has been written. `agent-review-scene` writes a review task. It does not mean an outside reviewer handled it. `canon-evolve` writes a candidate patch/no-change task. It does not apply canon.

## Canon Writeback Rule

Every formal candidate manifest should declare one of:

- `canon_change=true`: the scene created durable cross-scene world facts; run `canon-evolve`.
- `canon_change=false` with `no_canon_change_reason`: the scene did not create durable world facts.
- `canon_change="unknown"`: run `canon-evolve`; do not silently skip.

Canon patches live under `canon/patches/` as candidate material. Applying them is a separate review/approval decision. Use `canon-backlog` to inspect unapplied durable-world-fact work; use `canon-apply` only after approval to write the change into the durable canon change ledger. `canon-evolve` alone does not complete canon writeback.

## Rhythm And Bridge Rule

Every formal scene composition should carry `narrative_rhythm` and `scene_bridge`. The goal is not decorative pacing jargon; it is to prevent every scene from becoming the same flat summary.

Generation and review should check:

- scene function, such as main-plot movement, relationship change, misdirection, payoff, new question, changed choice, expanded cost, or reader-recognition shift,
- opening pressure from the previous context,
- the scene turn or meaningful change,
- what to slow down and what to pass quickly,
- dialogue/action/reflection/description ratio and narrative distance,
- reader effect, reader questions, and promise/payoff handling,
- texture variety across nearby scenes,
- paragraph function diversity,
- the outgoing hook or continuity handshake for the next scene.

If a scene reads as an average-speed summary with no entrance pressure, no turn, and no outgoing hook, it is not ready even if the prose is grammatical.
