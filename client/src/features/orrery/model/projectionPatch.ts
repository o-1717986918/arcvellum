import type {
  SpatialNarrativeProjection,
  SpatialNarrativeProjectionPatch,
  SpatialProjectionCollectionPatch,
} from "@/types/spatial";

export function applySpatialProjectionPatch(
  previous: SpatialNarrativeProjection,
  patch: SpatialNarrativeProjectionPatch,
): SpatialNarrativeProjection {
  if (patch.schema !== "arcvellum/narrative-projection-patch/v1") {
    throw new Error("unsupported narrative projection patch");
  }
  const previousRevision = previous.projection_revision || previous.revision;
  if (previousRevision !== patch.base_revision) {
    throw new Error("narrative projection patch base revision mismatch");
  }
  if (!patch.target_revision) {
    throw new Error("narrative projection patch target revision is missing");
  }
  const base = { ...previous } as Record<string, unknown>;
  patch.meta_remove.forEach((key) => delete base[key]);
  return {
    ...base,
    ...patch.meta,
    ok: true,
    schema: patch.projection_schema || previous.schema,
    revision: patch.target_revision,
    projection_revision: patch.target_revision,
    sequence: patch.sequence,
    nodes: applyCollection(previous.nodes, patch.nodes, (item) => item.node_id),
    edges: applyCollection(previous.edges, patch.edges, (item) => item.edge_id),
    delta: patch.delta,
    motion_events: patch.motion_events,
  } as SpatialNarrativeProjection;
}

function applyCollection<T>(
  previous: T[],
  patch: SpatialProjectionCollectionPatch<T>,
  identity: (item: T) => string,
): T[] {
  const items = new Map(previous.map((item) => [identity(item), item]));
  patch.remove.forEach((id) => items.delete(id));
  patch.upsert.forEach((item) => items.set(identity(item), item));
  const requested = patch.order.filter((id) => items.has(id));
  const order = requested.length ? requested : [...items.keys()];
  const known = new Set(order);
  items.forEach((_item, id) => {
    if (!known.has(id)) order.push(id);
  });
  return order.map((id) => items.get(id)!);
}
