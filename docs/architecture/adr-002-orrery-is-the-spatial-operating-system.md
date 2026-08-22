# ADR-002: The Orrery Is ArcVellum's Spatial Operating System

Status: accepted

## Decision

ArcVellum exposes one project-wide creative constellation. Book, chapter, scene,
character, world, style, branch, review, decision and formal-prose views are
semantic focus states of the same graph, not separately fetched graphs.

The constellation is a read model. The CLI workflow state machine and compiled
creative execution plan remain the only authorities for project mutation. A
node action must be represented by a typed action descriptor and dispatched to
an existing application command, human-choice endpoint or workspace. The
client must not infer a new writing workflow from visual state.

Mechanical receipts, task sidecars, shell commands and internal gate bookkeeping
are represented as activity and lifecycle evidence. They are not first-class
creative nodes. Literary objects and meaningful creative decisions remain
visible and interactive.

## Interaction Contract

- Every visible node supports inspect and focus.
- Mutating actions declare their risk, confirmation policy and command target.
- Formal prose, canon and promotion actions continue through deterministic gates.
- Workbenches may float, dock or become full screen without creating a second
  navigation or project-state model.
- Settings, model connections, help, legal and application information remain
  independent system pages.

## Consequences

The backend owns hierarchy, lifecycle, action availability and stable identity.
The frontend owns 2.5D placement, semantic zoom, animation and window geometry.
Projection v4 therefore returns the whole creative graph for every focus level;
focus changes emphasis and camera intent, not graph membership.

