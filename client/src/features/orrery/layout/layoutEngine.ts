import type { SpatialGrammar, SpatialLayout, SpatialNarrativeNode, WorldPoint } from "@/types/spatial";
import { applyValidatedLayoutHints } from "@/features/orrery/layout/layoutHints";
import {
  buildSceneClusters,
  chapterIdentity,
  type SceneCluster,
} from "@/features/orrery/layout/narrativeTiming";

const PRIMARY = new Set(["chapter", "scene"]);
const NARRATIVE_TYPES = new Set(["project", "chapter", "scene"]);
// A primary node needs enough room for both its physical glyph and a short
// label at the opening camera scale.  This is deliberately larger than the
// global-map cadence: the overview can zoom out, while a working segment must
// remain inspectable without immediately reaching for the zoom wheel.

interface LayoutContext {
  primary: SpatialNarrativeNode[];
  scenes: SpatialNarrativeNode[];
  chapters: SpatialNarrativeNode[];
  primaryRank: Map<string, number>;
  sceneRank: Map<string, number>;
  chapterRank: Map<string, number>;
  sceneClusters: Map<string, SceneCluster>;
  chapterClusterRanks: Map<string, number>;
  sceneClusterCount: number;
}

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));


/**
 * The primary geometry is the production port of the independent Orrery demo:
 * a project nucleus, count-aware chapter constellations, golden-angle scene
 * orbits and typed satellites. Only bounded satellite collision relief and
 * validated project hints may alter that reference arrangement.
 */
export function buildSpatialLayout(
  grammar: SpatialGrammar,
  revision: string,
  nodes: SpatialNarrativeNode[],
  layoutSeed = revision,
  layoutHints: Record<string, unknown> = {},
): SpatialLayout {
  const primary = nodes.filter((node) => PRIMARY.has(node.type)).sort(compareNarrativeNodes);
  const context = buildContext(primary);
  const points = new Map<string, WorldPoint>();
  const seeded = seedFrom(layoutSeed);

  nodes.filter((node) => (node.creative_kind || node.type) === "project")
    .forEach((node) => points.set(node.node_id, { x: 0, y: 0, z: 0 }));

  // Chapter nuclei are the fixed celestial architecture. Scenes then orbit
  // their own chapter nucleus instead of being laid on one generic rail.
  context.chapters.forEach((node, index) => points.set(node.node_id, primaryPoint(grammar, node, index, context)));
  context.scenes.forEach((node, index) => points.set(node.node_id, primaryPoint(grammar, node, index, context)));
  nodes
    .filter((node) => !PRIMARY.has(node.type) && (node.creative_kind || node.type) !== "project")
    .forEach((node, index) => {
      const parent = relatedAnchor(node, points) || (node.parent_id ? points.get(node.parent_id) : undefined);
      points.set(node.node_id, satellitePoint(grammar, parent || semanticAnchor(node, context), node, index));
    });


  // The extracted Orrery demo treats a braid as one continuous procession,
  // rather than preserving chapter-local satellites. Keep that exact spatial
  // grammar in production so switching constructs is visually equivalent.
  if (grammar === "braid") {
    const center = demoAxis(context.primary.length / 2, 8);
    context.primary.forEach((node, index) => {
      points.set(node.node_id, {
        x: demoAxis(index, 8) - center,
        y: Math.sin(index * 0.9) * 10,
        z: Math.cos(index * 0.9) * 13,
      });
    });
  }

  relaxLocalCollisions(points, nodes, seeded);
  applyValidatedLayoutHints(points, nodes, layoutHints);
  const coordinates = [...points.values()];
  const min = {
    x: Math.min(...coordinates.map((point) => point.x), -4),
    y: Math.min(...coordinates.map((point) => point.y), 0),
    z: Math.min(...coordinates.map((point) => point.z), -4),
  };
  const max = {
    x: Math.max(...coordinates.map((point) => point.x), 4),
    y: Math.max(...coordinates.map((point) => point.y), 2),
    z: Math.max(...coordinates.map((point) => point.z), 4),
  };
  const radius = Math.max(8, Math.hypot(max.x - min.x, max.y - min.y, max.z - min.z) * 0.55);
  return { grammar, revision, points, bounds: { min, max, radius } };
}

function buildContext(primary: SpatialNarrativeNode[]): LayoutContext {
  const scenes = primary.filter((node) => node.type === "scene");
  const chapters = primary.filter((node) => node.type === "chapter");
  const sceneClusters = buildSceneClusters(scenes);
  const chapterRanks = new Map(chapters.map((node, index) => [chapterIdentity(node), index]));
  const chapterClusterRanks = new Map<string, number>();
  for (const cluster of sceneClusters.values()) {
    if (chapterClusterRanks.has(cluster.id)) continue;
    chapterClusterRanks.set(cluster.id, chapterRanks.get(cluster.id) ?? cluster.rank);
  }
  return {
    primary,
    scenes,
    chapters,
    primaryRank: new Map(primary.map((node, index) => [node.node_id, index])),
    sceneRank: new Map(scenes.map((node, index) => [node.node_id, index])),
    chapterRank: new Map(chapters.map((node, index) => [node.node_id, index])),
    sceneClusters,
    chapterClusterRanks,
    sceneClusterCount: Math.max(chapters.length, new Set([...sceneClusters.values()].map((cluster) => cluster.id)).size),
  };
}

function primaryPoint(grammar: SpatialGrammar, node: SpatialNarrativeNode, fallbackIndex: number, context: LayoutContext): WorldPoint {
  const isChapter = node.type === "chapter";
  const rank = isChapter ? context.chapterRank.get(node.node_id) ?? fallbackIndex : context.sceneRank.get(node.node_id) ?? fallbackIndex;
  const cluster = isChapter ? undefined : context.sceneClusters.get(node.node_id);
  if (cluster) return demoScenePoint(grammar, cluster, rank, context);
  return demoChapterPoint(grammar, rank, Math.max(1, context.chapters.length));
}

function demoScenePoint(
  grammar: SpatialGrammar,
  cluster: SceneCluster,
  sceneRank: number,
  context: LayoutContext,
): WorldPoint {
  const nucleusRank = context.chapterClusterRanks.get(cluster.id) ?? cluster.rank;
  const nucleus = demoChapterPoint(grammar, nucleusRank, Math.max(1, context.sceneClusterCount));
  const angle = cluster.localRank * GOLDEN_ANGLE + sceneRank * 0.61;
  const radius = 7 + cluster.localRank * 2.3;
  if (grammar === "strata") {
    return {
      x: nucleus.x + Math.cos(angle) * radius,
      y: -2,
      z: nucleus.z + Math.sin(angle) * 3,
    };
  }
  return {
    x: nucleus.x + Math.cos(angle) * radius,
    y: nucleus.y + Math.sin(angle * 0.82) * 3.8,
    z: nucleus.z + Math.sin(angle) * radius * 0.86,
  };
}

function demoChapterPoint(grammar: SpatialGrammar, rank: number, count: number): WorldPoint {
  // This is the reference demo's literal chapter geometry. Chapter count is
  // intentionally part of the composition, so a growing book rebalances the
  // constellation instead of preserving a lopsided historical arrangement.
  const demoCentered = rank - 1;
  if (grammar === "constellation") {
    const angle = rank / Math.max(1, count) * Math.PI * 2 + 0.3;
    return {
      x: Math.cos(angle) * 25,
      y: demoCentered * 8.2,
      z: Math.sin(angle) * 25,
    };
  }
  if (grammar === "spine") return { x: demoAxis(demoCentered, 25), y: 5, z: Math.sin(rank * 1.2) * 3 };
  if (grammar === "braid") return { x: demoAxis(demoCentered, 23), y: Math.sin(rank * Math.PI) * 10 + 5, z: Math.cos(rank * Math.PI) * 12 };
  if (grammar === "strata") return { x: demoAxis(demoCentered, 24), y: 14, z: rank % 2 ? 8 : -8 };
  if (grammar === "loop") {
    const angle = rank / Math.max(1, count) * Math.PI * 2;
    return { x: Math.cos(angle) * 28, y: Math.sin(angle) * 7, z: Math.sin(angle) * 28 };
  }
  return { x: demoAxis(demoCentered, 25), y: rank % 2 ? 9 : -6, z: rank % 2 ? -10 : 10 };
}

/** The reference demo is exact across the working horizon. Beyond 24 anchors,
 * retain its direction and order while compressing only the distant tail so a
 * thousand-node projection stays inside the production navigation world. */
function demoAxis(rank: number, stride: number, tailStride = 2.5): number {
  const sign = rank < 0 ? -1 : 1;
  const absolute = Math.abs(rank);
  if (absolute <= 24) return rank * stride;
  return sign * (24 * stride + (absolute - 24) * tailStride);
}

function semanticAnchor(node: SpatialNarrativeNode, context: LayoutContext): WorldPoint {
  const hash = hashNode(node.cluster_id || node.node_id, 177);
  const chapterCount = Math.max(1, context.chapters.length);
  const spine = demoChapterPoint("spine", hash % chapterCount, chapterCount);
  if (node.type === "character") return { x: spine.x - 3.4 + (hash % 3) * 3.4, y: 3.8, z: spine.z + 0.8 };
  if (node.type === "canon") return { x: spine.x, y: -0.15, z: spine.z - 2.2 };
  if (node.type === "task" || node.type === "review") return { x: spine.x + 1.3, y: 4.55, z: spine.z + 1.6 };
  if (node.type === "branch") return { x: spine.x + 4.8, y: 2.6, z: spine.z + 0.9 };
  if (node.type === "promise" || node.type === "reader-question") return { x: spine.x - 4.4, y: 2.7, z: spine.z + 0.6 };
  const nearest = context.primary[hash % Math.max(1, context.primary.length)];
  return nearest ? context.primaryRank.has(nearest.node_id)
    ? demoChapterPoint("spine", context.primaryRank.get(nearest.node_id) || 0, Math.max(1, context.primary.length))
    : spine : spine;
}

function satellitePoint(grammar: SpatialGrammar, anchor: WorldPoint, node: SpatialNarrativeNode, index: number): WorldPoint {
  const angle = index * GOLDEN_ANGLE + (node.type === "character" ? 0.8 : 2.1);
  const magnitude = node.type === "character" ? 13 : 9;
  const elevation = node.type === "character" ? 10 : -8;
  const depth = grammar === "strata" ? Math.sin(angle) * magnitude * 0.36 : Math.sin(angle) * magnitude;
  return {
    x: anchor.x + Math.cos(angle) * magnitude,
    y: anchor.y + elevation + (index % 3) * 2,
    z: anchor.z + depth,
  };
}

function relatedAnchor(node: SpatialNarrativeNode, points: Map<string, WorldPoint>): WorldPoint | undefined {
  if ((node.creative_kind || node.type) !== "character") return undefined;
  const sceneIds = Array.isArray(node.metrics.scene_ids) ? node.metrics.scene_ids.map(String) : [];
  const related = sceneIds.map((sceneId) => points.get(`scene:${sceneId}`)).filter((point): point is WorldPoint => Boolean(point));
  if (!related.length) return undefined;
  return {
    x: related.reduce((sum, point) => sum + point.x, 0) / related.length,
    y: related.reduce((sum, point) => sum + point.y, 0) / related.length,
    z: related.reduce((sum, point) => sum + point.z, 0) / related.length,
  };
}

function relaxLocalCollisions(points: Map<string, WorldPoint>, nodes: SpatialNarrativeNode[], seed: number): void {
  // A bounded, deterministic local relaxation. It deliberately moves only the
  // lighter object in a close pair, so a newly added satellite cannot make the
  // established narrative spine migrate across the entire stage.
  const ordered = nodes
    .filter((node) => points.has(node.node_id))
    .sort((left, right) => visualWeight(right) - visualWeight(left) || left.node_id.localeCompare(right.node_id));
  const cap = Math.min(620, ordered.length);
  for (let pass = 0; pass < 4; pass += 1) {
    for (let first = 0; first < cap; first += 1) {
      const fixed = ordered[first];
      const fixedPoint = points.get(fixed.node_id)!;
      for (let second = first + 1; second < cap; second += 1) {
        const moving = ordered[second];
        const point = points.get(moving.node_id)!;
        const dx = point.x - fixedPoint.x;
        const dy = point.y - fixedPoint.y;
        const dz = point.z - fixedPoint.z;
        const projectedDistance = Math.hypot(dx + dz * 0.17, dy * 0.84 + dz * 0.38);
        // The backbone stays on its designed spline. Only satellites may yield
        // when space becomes tight; label LOD handles primary density.
        if (NARRATIVE_TYPES.has(moving.type)) continue;
        const minimum = 1.18;
        if (projectedDistance >= minimum) continue;
        const angle = projectedDistance > 0.02 ? Math.atan2(dy + dz * 0.38, dx + dz * 0.17) : pseudo(seed + hashNode(moving.node_id, pass + 61)) * Math.PI * 2;
        const push = (minimum - projectedDistance) * 0.6;
        point.x += Math.cos(angle) * push;
        point.y += Math.sin(angle) * push * 0.72;
        point.z += Math.sin(angle + 0.72) * push * 0.38;
      }
    }
  }
}

function visualWeight(node: SpatialNarrativeNode): number {
  const type = node.type === "project" ? 4 : node.type === "chapter" ? 3 : node.type === "scene" ? 2.7 : node.type === "canon" ? 2.3 : 1.2;
  const status = node.status === "current" ? 0.9 : node.status === "blocked" ? 0.7 : node.status === "formal" ? 0.25 : 0;
  return type + status + node.importance;
}

function compareNarrativeNodes(left: SpatialNarrativeNode, right: SpatialNarrativeNode): number {
  const order = stableTimelineIndex(left, 0) - stableTimelineIndex(right, 0);
  if (order) return order;
  if (left.type !== right.type) return left.type === "chapter" ? -1 : 1;
  return left.node_id.localeCompare(right.node_id);
}

function stableTimelineIndex(node: SpatialNarrativeNode, fallback: number): number {
  const order = Number(node.order);
  if (Number.isFinite(order) && order > 0) return Math.round(order);
  const numeric = node.node_id.match(/(\d+)(?!.*\d)/)?.[1];
  return numeric ? Number(numeric) : fallback + 1;
}

function hashNode(value: string, salt: number): number {
  let state = 2166136261 ^ salt;
  for (const character of value) state = Math.imul(state ^ character.charCodeAt(0), 16777619);
  return state >>> 0;
}

function seedFrom(value: string): number {
  let state = 2166136261;
  for (const character of value) state = Math.imul(state ^ character.charCodeAt(0), 16777619);
  return state >>> 0;
}

function pseudo(seed: number): number {
  let value = seed >>> 0;
  value ^= value << 13;
  value ^= value >>> 17;
  value ^= value << 5;
  return (value >>> 0) / 4294967296;
}
