import type { SpatialNarrativeNode, WorldPoint } from "@/types/spatial";

const FIXED_TYPES = new Set(["project", "chapter", "scene"]);
const MINIMUM = 1.18;

/** Only nearby, higher-priority objects can displace a satellite. No size cutoff. */
export function relaxLocalCollisions(points: Map<string, WorldPoint>, nodes: SpatialNarrativeNode[], seed: number): void {
  const ordered = nodes.filter((node) => points.has(node.node_id))
    .sort((a, b) => visualWeight(b) - visualWeight(a) || a.node_id.localeCompare(b.node_id));
  for (let pass = 0; pass < 4; pass++) {
    const cells = new Map<string, WorldPoint[]>();
    for (const node of ordered) {
      const point = points.get(node.node_id)!;
      if (!FIXED_TYPES.has(node.type)) separate(point, cells, seed + pass);
      const key = cellKey(point);
      const bucket = cells.get(key) || [];
      bucket.push(point);
      cells.set(key, bucket);
    }
  }
}

function separate(point: WorldPoint, cells: Map<string, WorldPoint[]>, seed: number): void {
  const x = Math.floor((point.x + point.z * 0.17) / MINIMUM);
  const y = Math.floor((point.y * 0.84 + point.z * 0.38) / MINIMUM);
  for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
    for (const fixed of cells.get(`${x + dx}:${y + dy}`) || []) {
      const px = point.x - fixed.x, py = point.y - fixed.y, pz = point.z - fixed.z;
      const distance = Math.hypot(px + pz * 0.17, py * 0.84 + pz * 0.38);
      if (distance >= MINIMUM) continue;
      const angle = distance > 0.02 ? Math.atan2(py + pz * 0.38, px + pz * 0.17) : seed * 2.399963;
      const push = (MINIMUM - distance) * 0.6;
      point.x += Math.cos(angle) * push;
      point.y += Math.sin(angle) * push * 0.72;
      point.z += Math.sin(angle + 0.72) * push * 0.38;
    }
  }
}

function cellKey(point: WorldPoint): string {
  return `${Math.floor((point.x + point.z * 0.17) / MINIMUM)}:${Math.floor((point.y * 0.84 + point.z * 0.38) / MINIMUM)}`;
}

function visualWeight(node: SpatialNarrativeNode): number {
  const type = node.type === "project" ? 4 : node.type === "chapter" ? 3 : node.type === "scene" ? 2.7 : node.type === "canon" ? 2.3 : 1.2;
  // Importance is also status-derived. Both control emphasis, not geometry;
  // a current/blocked transition must not reorder collision priority.
  return type;
}
