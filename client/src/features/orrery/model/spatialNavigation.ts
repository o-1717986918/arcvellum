import type { SpatialNarrativeNode, WorldPoint } from "@/types/spatial";

export type SpatialDirection = "left" | "right" | "up" | "down";

export interface MinimapPoint {
  node_id: string;
  x: number;
  y: number;
  type: string;
  status: string;
}

export interface OffscreenBeacon {
  node: SpatialNarrativeNode;
  x: number;
  y: number;
  angle: number;
}

const SEARCH_TYPE_LABELS: Record<string, string> = {
  chapter: "章节",
  scene: "场景",
  character: "人物",
  branch: "分支",
  review: "审查",
  canon: "设定",
  promise: "承诺",
  "reader-question": "问题",
  task: "任务",
};

export function searchNarrativeNodes(
  nodes: SpatialNarrativeNode[],
  query: string,
  limit = 12,
): SpatialNarrativeNode[] {
  const needle = normalize(query);
  if (!needle) return [];
  return nodes
    .map((node) => ({ node, score: searchScore(node, needle) }))
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score
      || left.node.order - right.node.order
      || left.node.node_id.localeCompare(right.node.node_id))
    .slice(0, Math.max(1, limit))
    .map((item) => item.node);
}

export function nextSpatialNode(
  nodes: SpatialNarrativeNode[],
  points: Map<string, WorldPoint>,
  currentNodeId: string,
  direction: SpatialDirection,
): SpatialNarrativeNode | null {
  const candidates = nodes.filter((node) => points.has(node.node_id));
  if (!candidates.length) return null;
  const current = candidates.find((node) => node.node_id === currentNodeId)
    || candidates.find((node) => node.status === "current" || node.status === "blocked")
    || candidates.sort(nodeOrder)[0];
  const origin = points.get(current.node_id);
  if (!origin) return current;

  const axis = directionAxis(direction);
  let best: { node: SpatialNarrativeNode; score: number } | null = null;
  for (const node of candidates) {
    if (node.node_id === current.node_id) continue;
    const point = points.get(node.node_id);
    if (!point) continue;
    const dx = point.x - origin.x;
    const dy = point.y - origin.y;
    const distance = Math.hypot(dx, dy);
    if (distance < 0.001) continue;
    const forward = (dx * axis.x + dy * axis.y) / distance;
    if (forward < 0.24) continue;
    const cross = Math.abs(dx * axis.y - dy * axis.x) / distance;
    const score = distance * (1 + cross * 1.7) / Math.max(0.22, forward);
    if (!best || score < best.score || (score === best.score && nodeOrder(node, best.node) < 0)) {
      best = { node, score };
    }
  }
  return best?.node || current;
}

export function minimapPoints(
  nodes: SpatialNarrativeNode[],
  points: Map<string, WorldPoint>,
  width: number,
  height: number,
  padding = 8,
): MinimapPoint[] {
  const entries = nodes
    .filter((node) => node.type === "chapter" || node.type === "scene")
    .map((node) => ({ node, point: points.get(node.node_id) }))
    .filter((item): item is { node: SpatialNarrativeNode; point: WorldPoint } => Boolean(item.point));
  if (!entries.length) return [];
  const minX = Math.min(...entries.map((item) => item.point.x));
  const maxX = Math.max(...entries.map((item) => item.point.x));
  const minY = Math.min(...entries.map((item) => item.point.y));
  const maxY = Math.max(...entries.map((item) => item.point.y));
  const spanX = Math.max(1, maxX - minX);
  const spanY = Math.max(1, maxY - minY);
  const scale = Math.min((width - padding * 2) / spanX, (height - padding * 2) / spanY);
  const offsetX = (width - spanX * scale) / 2;
  const offsetY = (height - spanY * scale) / 2;
  return entries.map(({ node, point }) => ({
    node_id: node.node_id,
    x: offsetX + (point.x - minX) * scale,
    y: offsetY + (point.y - minY) * scale,
    type: node.type,
    status: node.status,
  }));
}

export function offscreenBeacons(
  nodes: SpatialNarrativeNode[],
  anchors: Record<string, { x: number; y: number; visible: boolean }>,
  width: number,
  height: number,
  limit = 7,
): OffscreenBeacon[] {
  if (width <= 0 || height <= 0) return [];
  const center = { x: width / 2, y: height / 2 };
  const marginX = 34;
  const marginTop = 64;
  const marginBottom = 82;
  return nodes
    .filter((node) => {
      const anchor = anchors[node.node_id];
      return Boolean(anchor && !anchor.visible)
        && (node.type === "chapter" || node.type === "scene" || (node.type === "task" && (node.status === "current" || node.status === "blocked")));
    })
    .sort((left, right) => beaconPriority(right) - beaconPriority(left) || nodeOrder(left, right))
    .slice(0, Math.max(1, limit))
    .map((node) => {
      const anchor = anchors[node.node_id]!;
      const dx = anchor.x - center.x;
      const dy = anchor.y - center.y;
      const scale = Math.min(
        dx === 0 ? Number.POSITIVE_INFINITY : (width / 2 - marginX) / Math.abs(dx),
        dy === 0 ? Number.POSITIVE_INFINITY : (height / 2 - Math.max(marginTop, marginBottom)) / Math.abs(dy),
      );
      const boundedScale = Number.isFinite(scale) ? Math.max(0, Math.min(1, scale)) : 0;
      return {
        node,
        x: Math.max(marginX, Math.min(width - marginX, center.x + dx * boundedScale)),
        y: Math.max(marginTop, Math.min(height - marginBottom, center.y + dy * boundedScale)),
        angle: Math.atan2(dy, dx) * 180 / Math.PI,
      };
    });
}

function searchScore(node: SpatialNarrativeNode, needle: string): number {
  const label = normalize(node.label);
  const subtitle = normalize(node.subtitle);
  const source = normalize(node.source_id);
  const type = normalize(SEARCH_TYPE_LABELS[node.type] || node.type);
  if (label === needle || source === needle) return 1_000 + node.importance * 10;
  if (label.startsWith(needle)) return 720 + node.importance * 10;
  if (label.includes(needle)) return 560 + node.importance * 10;
  if (subtitle.includes(needle)) return 320 + node.importance * 10;
  if (source.includes(needle)) return 240 + node.importance * 10;
  if (type.includes(needle)) return 120 + node.importance * 10;
  return 0;
}

function normalize(value: unknown): string {
  return String(value || "").trim().toLocaleLowerCase("zh-CN").replace(/\s+/g, "");
}

function directionAxis(direction: SpatialDirection): { x: number; y: number } {
  if (direction === "left") return { x: -1, y: 0 };
  if (direction === "right") return { x: 1, y: 0 };
  if (direction === "up") return { x: 0, y: -1 };
  return { x: 0, y: 1 };
}

function nodeOrder(left: SpatialNarrativeNode, right: SpatialNarrativeNode): number {
  return left.order - right.order || left.node_id.localeCompare(right.node_id);
}

function beaconPriority(node: SpatialNarrativeNode): number {
  const status = node.status === "current" ? 1_000 : node.status === "blocked" ? 800 : node.status === "formal" ? 200 : 0;
  const type = node.type === "chapter" ? 120 : node.type === "scene" ? 80 : 0;
  return status + type + node.importance * 100;
}
