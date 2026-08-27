import type { SpatialGrammar, SpatialLayout, SpatialNarrativeNode, WorldPoint } from "@/types/spatial";
import { curveProfilePoint } from "@/features/orrery/layout/curveProfiles";
import { applyValidatedLayoutHints } from "@/features/orrery/layout/layoutHints";
import {
  CHAPTER_CLUSTER_GAP,
  SCENE_STEP,
  bookContour,
  buildSceneClusters,
  buildTemporalAxis,
  chapterIdentity,
  narrativeBeat,
  rhythmLift,
  smoothNarrativeBeats,
  type NarrativeBeat,
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
  rhythm: Map<string, NarrativeBeat>;
  temporalAxis: Map<string, number>;
}


/**
 * Positions are deliberately semantic and stable rather than a generic force
 * graph. The book is allowed to grow at its leading edge, while the established
 * portion retains its spatial memory. Small deterministic offsets create depth
 * and relieve local collisions without making a revision reshuffle the stage.
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
    .forEach((node) => points.set(node.node_id, { x: 0, y: 0.4, z: 0 }));

  // Chapter nuclei are the fixed celestial architecture. Scenes then orbit
  // their own chapter nucleus instead of being laid on one generic rail.
  context.chapters.forEach((node, index) => points.set(node.node_id, primaryPoint(grammar, node, index, context)));
  context.scenes.forEach((node, index) => points.set(node.node_id, primaryPoint(grammar, node, index, context)));
  nodes.filter((node) => !PRIMARY.has(node.type)).forEach((node) => {
    if (points.has(node.node_id)) return;
    const parent = relatedAnchor(node, points) || (node.parent_id ? points.get(node.parent_id) : undefined);
    points.set(node.node_id, satellitePoint(grammar, parent || semanticAnchor(node, context), node, seeded));
  });

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
  const rhythm = smoothNarrativeBeats(primary);
  const temporalAxis = buildTemporalAxis(primary, rhythm, sceneClusters);
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
    rhythm,
    temporalAxis,
  };
}

function primaryPoint(grammar: SpatialGrammar, node: SpatialNarrativeNode, fallbackIndex: number, context: LayoutContext): WorldPoint {
  const isChapter = node.type === "chapter";
  const rank = isChapter ? context.chapterRank.get(node.node_id) ?? fallbackIndex : context.sceneRank.get(node.node_id) ?? fallbackIndex;
  const cluster = isChapter ? undefined : context.sceneClusters.get(node.node_id);
  if (cluster) return clusteredScenePoint(grammar, node, cluster, context);
  const visualRank = rank;
  const visualCount = isChapter ? context.chapters.length : context.primary.length;
  // Every primary projection owns a stable ordinal. The old implementation
  // multiplied chapter ordinals into a high-frequency sine/cosine wave. Long
  // books therefore curled back across themselves and then had to be squeezed
  // into one viewport. A primary route now advances monotonically; only the
  // explicit `braid`, `loop`, and `constellation` grammars may introduce a
  // recurrent spatial rhythm.
  const timeline = rank + 1;
  const phase = timeline * 0.34;
  // Scenes keep their chronological footprint, but each chapter shares one
  // local nucleus. The grammar can then fan the scenes around that nucleus in
  // depth instead of rendering them as a nearly flat queue.
  const axis = isChapter
    ? chapterAxis(rank)
    : context.temporalAxis.get(node.node_id) ?? narrativeAxis(timeline);
  const beat = context.rhythm.get(node.node_id) || narrativeBeat(node, rank, context.primary.length);
  const contour = bookContour(visualRank, visualCount);
  const lift = rhythmLift(beat);
  const depth = narrativeDepth(timeline) + (isChapter ? 0.38 : 0) + lift * 0.22;
  // This is a forward-moving cadence, not a repeating map ornament. It gives
  // a long scene sequence room to inhale and release without ever folding the
  // reading order back over itself.
  const cadence = Math.sin(phase * 0.88) * 0.31 + Math.sin(phase * 0.31 + 0.7) * 0.19;
  const rise = narrativeRise(timeline) + contour * 0.58 + lift + cadence;
  const arc = Math.sin(phase * 0.82);
  const swell = Math.cos(phase * 0.96);

  if (isChapter && grammar === "constellation") {
    return constellationNucleus(rank, Math.max(1, context.chapters.length), lift);
  }

  return curveProfilePoint(grammar, {
    axis, phase, depth, rise, arc, swell, cadence, lift,
    visualRank, visualCount, rank,
  });
}

function clusteredScenePoint(
  grammar: SpatialGrammar,
  node: SpatialNarrativeNode,
  cluster: SceneCluster,
  context: LayoutContext,
): WorldPoint {
  const nucleusRank = context.chapterClusterRanks.get(cluster.id) ?? cluster.rank;
  const count = Math.max(1, context.sceneClusterCount);
  const timeline = nucleusRank + 1;
  const phase = timeline * 0.34;
  const beat = context.rhythm.get(node.node_id) || narrativeBeat(node, nucleusRank, count);
  const contour = bookContour(nucleusRank, count);
  const lift = rhythmLift(beat);
  const depth = narrativeDepth(timeline) + 0.38 + lift * 0.22;
  const cadence = Math.sin(phase * 0.88) * 0.31 + Math.sin(phase * 0.31 + 0.7) * 0.19;
  const rise = narrativeRise(timeline) + contour * 0.58 + lift + cadence;
  const nucleus = grammar === "constellation"
    ? constellationNucleus(nucleusRank, count, lift)
    : curveProfilePoint(grammar, {
      axis: chapterAxis(nucleusRank),
      phase,
      depth,
      rise,
      arc: Math.sin(phase * 0.82),
      swell: Math.cos(phase * 0.96),
      cadence,
      lift,
      visualRank: nucleusRank,
      visualCount: count,
      rank: nucleusRank,
      });
  const local = chapterOrbitOffset(grammar, cluster, lift);
  return { x: nucleus.x + local.x, y: nucleus.y + local.y, z: nucleus.z + local.z };
}

function constellationNucleus(rank: number, count: number, lift: number): WorldPoint {
  // The visual-orrery experiment proved that a few legible celestial
  // latitudes communicate chapter families more clearly than a mathematically
  // uniform sphere. Generalise that idea without assuming a fixed volume
  // count: chapters advance around two or three offset latitude bands, while
  // every band remains readable from the recommended oblique camera.
  const bandCount = count < 6 ? 2 : 3;
  const perBand = Math.max(1, Math.ceil(count / bandCount));
  const band = Math.min(bandCount - 1, Math.floor(rank / perBand));
  const within = rank % perBand;
  const members = Math.min(perBand, count - band * perBand);
  const normalizedY = 0.58 - band * (1.16 / (bandCount - 1));
  const shellRadius = Math.max(38, Math.sqrt(Math.max(1, count)) * 8.8);
  const horizontalRadius = Math.sqrt(Math.max(0.08, 1 - normalizedY * normalizedY)) * shellRadius;
  const angle = (within / Math.max(1, members)) * Math.PI * 2 + band * 0.84 + 0.28;
  return {
    x: Math.cos(angle) * horizontalRadius,
    y: normalizedY * shellRadius * 0.82 + (within - (members - 1) / 2) * 0.42 + lift * 0.5,
    z: Math.sin(angle) * horizontalRadius,
  };
}

function chapterOrbitOffset(grammar: SpatialGrammar, cluster: SceneCluster, lift: number): WorldPoint {
  if (cluster.size <= 1) return { x: 0, y: lift * 0.12, z: 0 };
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const angle = cluster.localRank * goldenAngle + cluster.rank * 0.61;
  const radius = 2.25 + Math.sqrt(cluster.localRank + 0.72) * 1.42;
  const centered = cluster.localRank - (cluster.size - 1) / 2;
  const depthRatio = grammar === "strata" ? 0.48 : grammar === "stage" ? 0.66 : 0.86;
  return {
    x: Math.cos(angle) * radius + centered * 0.22,
    y: Math.sin(angle * 0.82) * 0.72 + lift * 0.18 + (cluster.localRank % 2 ? 0.12 : -0.12),
    z: Math.sin(angle) * radius * depthRatio + Math.cos(centered * 0.94) * 0.34,
  };
}

function chapterAxis(rank: number): number {
  return rank * CHAPTER_CLUSTER_GAP - 4.8;
}

function narrativeAxis(timeline: number): number {
  // Linear spacing preserves a legible local cadence as a project grows.
  // It depends only on the entity ordinal, so adding a later chapter leaves
  // every established position untouched.
  return (Math.max(1, timeline) - 1) * SCENE_STEP - 4.8;
}

function narrativeDepth(timeline: number): number {
  const index = Math.max(0, timeline - 1);
  return 8.6 - index * 0.052 - index * index * 0.00011;
}

function narrativeRise(timeline: number): number {
  const index = Math.max(0, timeline - 1);
  return -index * 0.0065 - index * index * 0.000015;
}

function semanticAnchor(node: SpatialNarrativeNode, context: LayoutContext): WorldPoint {
  const hash = hashNode(node.cluster_id || node.node_id, 177);
  const timeline = 1 + (hash % 128);
  const spine = { x: narrativeAxis(timeline), y: 1.1, z: narrativeDepth(timeline) };
  if (node.type === "character") return { x: spine.x - 3.4 + (hash % 3) * 3.4, y: 3.8, z: spine.z + 0.8 };
  if (node.type === "canon") return { x: spine.x, y: -0.15, z: spine.z - 2.2 };
  if (node.type === "task" || node.type === "review") return { x: spine.x + 1.3, y: 4.55, z: spine.z + 1.6 };
  if (node.type === "branch") return { x: spine.x + 4.8, y: 2.6, z: spine.z + 0.9 };
  if (node.type === "promise" || node.type === "reader-question") return { x: spine.x - 4.4, y: 2.7, z: spine.z + 0.6 };
  const nearest = context.primary[hash % Math.max(1, context.primary.length)];
  return nearest ? { x: narrativeAxis((context.primaryRank.get(nearest.node_id) || 0) + 1), y: 2.1, z: narrativeDepth((context.primaryRank.get(nearest.node_id) || 0) + 1) } : spine;
}

function satellitePoint(grammar: SpatialGrammar, anchor: WorldPoint, node: SpatialNarrativeNode, seed: number): WorldPoint {
  const identity = hashNode(node.node_id, 29);
  const angle = pseudo(seed + identity) * Math.PI * 2;
  const role = satelliteProfile(node.type);
  const hierarchy = Math.max(0, Number(node.hierarchy_depth || 0));
  const magnitude = role.radius + (identity % 4) * role.spread + Math.max(0, hierarchy - 1) * 0.34;
  const elevation = role.elevation + (identity % 3) * 0.32;
  const depth = grammar === "strata" ? Math.cos(angle) * magnitude * 0.45 : Math.sin(angle) * magnitude;
  return {
    x: anchor.x + Math.cos(angle) * magnitude,
    y: Math.max(-0.35, anchor.y + elevation),
    z: anchor.z + depth + role.depthBias,
  };
}

function satelliteProfile(type: string): { radius: number; spread: number; elevation: number; depthBias: number } {
  if (type === "story-architecture") return { radius: 5.8, spread: 0.36, elevation: 2.4, depthBias: -0.8 };
  if (type === "word-budget") return { radius: 5.2, spread: 0.34, elevation: -2.5, depthBias: -0.5 };
  if (type === "style") return { radius: 5.6, spread: 0.44, elevation: 1.2, depthBias: 2.1 };
  if (type === "world" || type === "location" || type === "organization") return { radius: 6.2, spread: 0.72, elevation: -1.25, depthBias: -2.5 };
  if (type === "character") return { radius: 3.8, spread: 0.72, elevation: 1.35, depthBias: 0.95 };
  if (type === "canon") return { radius: 2.8, spread: 0.56, elevation: -1.48, depthBias: -2.35 };
  if (type === "task" || type === "review") return { radius: 3.1, spread: 0.62, elevation: 3.15, depthBias: 1.38 };
  if (type === "branch") return { radius: 4.25, spread: 0.88, elevation: 1.8, depthBias: 0.82 };
  if (type === "promise" || type === "reader-question") return { radius: 3.45, spread: 0.72, elevation: 2.02, depthBias: 0.52 };
  if (type === "draft" || type === "formal-prose") return { radius: 2.35, spread: 0.38, elevation: -1.85, depthBias: 0.2 };
  if (type === "human-decision") return { radius: 4.4, spread: 0.5, elevation: 3.25, depthBias: 1.4 };
  return { radius: 2.2, spread: 0.5, elevation: 1.25, depthBias: 0.35 };
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
