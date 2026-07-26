import type { SpatialNarrativeNode } from "@/types/spatial";

const AMBIENT_STATUSES = new Set(["current", "blocked", "alternative", "queued"]);

export function hasAmbientNodeMotion(nodes: SpatialNarrativeNode[]): boolean {
  return nodes.some((node) => AMBIENT_STATUSES.has(node.status));
}

export function ambientNodeOffset(
  node: SpatialNarrativeNode,
  time: number,
): { x: number; y: number } {
  if (!AMBIENT_STATUSES.has(node.status)) return { x: 0, y: 0 };
  const phase = (hashNode(node.node_id, 71) % 360) * (Math.PI / 180);
  const amplitude = node.status === "current"
    ? 3.4
    : node.status === "blocked"
      ? 2.5
      : node.status === "queued"
        ? 2.1
        : 1.45;
  const speed = node.status === "current" ? 1.25 : 0.74;
  return {
    x: Math.sin(time * speed + phase) * amplitude,
    y: Math.cos(time * speed * 0.82 + phase) * amplitude * 0.58,
  };
}

function hashNode(value: string, salt: number): number {
  let state = 2166136261 ^ salt;
  for (const character of value) state = Math.imul(state ^ character.charCodeAt(0), 16777619);
  return state >>> 0;
}
