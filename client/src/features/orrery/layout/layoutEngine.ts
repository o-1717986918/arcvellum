import type { SpatialGrammar, SpatialLayout, SpatialNarrativeNode, WorldPoint } from "@/types/spatial";
import { curveProfilePoint } from "@/features/orrery/layout/curveProfiles";

const PRIMARY = new Set(["chapter", "scene"]);
const NARRATIVE_TYPES = new Set(["chapter", "scene"]);
// A primary node needs enough room for both its physical glyph and a short
// label at the opening camera scale.  This is deliberately larger than the
// global-map cadence: the overview can zoom out, while a working segment must
// remain inspectable without immediately reaching for the zoom wheel.
const CHAPTER_STEP = 4.25;
const SCENE_STEP = 1.2;
const CHAPTER_CLUSTER_GAP = 5.45;

interface LayoutContext {
  primary: SpatialNarrativeNode[];
  scenes: SpatialNarrativeNode[];
  chapters: SpatialNarrativeNode[];
  primaryRank: Map<string, number>;
  sceneRank: Map<string, number>;
  chapterRank: Map<string, number>;
  sceneClusters: Map<string, SceneCluster>;
  sceneClusterCount: number;
  rhythm: Map<string, NarrativeBeat>;
  temporalAxis: Map<string, number>;
}

interface SceneCluster {
  id: string;
  rank: number;
  localRank: number;
  size: number;
}

interface NarrativeBeat {
  entry: number;
  peak: number;
  exit: number;
  detail: number;
  timelineStart: number;
  timelineEnd: number;
  gapBefore: number;
}

/**
 * Positions are deliberately semantic and stable rather than a generic force
 * graph. The book is allowed to grow at its leading edge, while the established
 * portion retains its spatial memory. Small deterministic offsets create depth
 * and relieve local collisions without making a revision reshuffle the stage.
 */
export function buildSpatialLayout(grammar: SpatialGrammar, revision: string, nodes: SpatialNarrativeNode[], layoutSeed = revision): SpatialLayout {
  const primary = nodes.filter((node) => PRIMARY.has(node.type)).sort(compareNarrativeNodes);
  const context = buildContext(primary);
  const points = new Map<string, WorldPoint>();
  const seeded = seedFrom(layoutSeed);

  context.primary.forEach((node, index) => points.set(node.node_id, primaryPoint(grammar, node, index, context)));
  nodes.filter((node) => !PRIMARY.has(node.type)).forEach((node) => {
    const parent = node.parent_id ? points.get(node.parent_id) : undefined;
    points.set(node.node_id, satellitePoint(grammar, parent || semanticAnchor(node, context), node, seeded));
  });

  relaxLocalCollisions(points, nodes, seeded);
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
  const rhythm = smoothNarrativeBeats(primary);
  return {
    primary,
    scenes,
    chapters,
    primaryRank: new Map(primary.map((node, index) => [node.node_id, index])),
    sceneRank: new Map(scenes.map((node, index) => [node.node_id, index])),
    chapterRank: new Map(chapters.map((node, index) => [node.node_id, index])),
    sceneClusters,
    sceneClusterCount: new Set([...sceneClusters.values()].map((cluster) => cluster.id)).size,
    rhythm,
    temporalAxis: buildTemporalAxis(primary, rhythm, sceneClusters),
  };
}

function primaryPoint(grammar: SpatialGrammar, node: SpatialNarrativeNode, fallbackIndex: number, context: LayoutContext): WorldPoint {
  const isChapter = node.type === "chapter";
  const rank = isChapter ? context.chapterRank.get(node.node_id) ?? fallbackIndex : context.sceneRank.get(node.node_id) ?? fallbackIndex;
  const cluster = isChapter ? undefined : context.sceneClusters.get(node.node_id);
  const visualRank = cluster?.rank ?? rank;
  const visualCount = isChapter ? context.chapters.length : cluster ? context.sceneClusterCount : context.primary.length;
  // Every primary projection owns a stable ordinal. The old implementation
  // multiplied chapter ordinals into a high-frequency sine/cosine wave. Long
  // books therefore curled back across themselves and then had to be squeezed
  // into one viewport. A primary route now advances monotonically; only the
  // explicit `braid`, `loop`, and `constellation` grammars may introduce a
  // recurrent spatial rhythm.
  const timeline = rank + 1;
  const phase = timeline * 0.34;
  const axis = context.temporalAxis.get(node.node_id) ?? narrativeAxis(timeline);
  const beat = context.rhythm.get(node.node_id) || narrativeBeat(node, rank, context.primary.length);
  const contour = bookContour(visualRank, visualCount);
  const lift = rhythmLift(beat);
  const depth = narrativeDepth(timeline) + (isChapter ? 0.38 : 0) + lift * 0.22;
  // This is a forward-moving cadence, not a repeating map ornament. It gives
  // a long scene sequence room to inhale and release without ever folding the
  // reading order back over itself.
  const cadence = cluster
    ? Math.sin(cluster.localRank * 1.16 + cluster.rank * 0.43) * 0.15 + Math.sin(cluster.rank * 0.57 + 0.7) * 0.2
    : Math.sin(phase * 0.88) * 0.31 + Math.sin(phase * 0.31 + 0.7) * 0.19;
  const rise = narrativeRise(timeline) + contour * 0.58 + lift + cadence;
  const arc = Math.sin(phase * 0.82);
  const swell = Math.cos(phase * 0.96);

  return curveProfilePoint(grammar, {
    axis, phase, depth, rise, arc, swell, cadence, lift,
    visualRank, visualCount, rank, cluster,
  });
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

function narrativeBeat(node: SpatialNarrativeNode, index: number, count: number): NarrativeBeat {
  const raw = node.rhythm;
  if (raw) {
    return {
      entry: clampBeat(raw.entry, 2),
      peak: clampBeat(raw.peak, 3),
      exit: clampBeat(raw.exit, 2),
      detail: detailWeight(raw.detail_level),
      timelineStart: positiveNumber(raw.timeline_start),
      timelineEnd: positiveNumber(raw.timeline_end),
      gapBefore: positiveNumber(raw.spatial_time_gap_before),
    };
  }
  // Legacy projects may not have an explicit rhythm plan yet. Give them one
  // gentle, non-repeating book contour without claiming it is editorial data.
  const fallbackPeak = 2.55 + bookContour(index, count) * 0.72;
  return { entry: 2.25, peak: fallbackPeak, exit: 2.15, detail: 0, timelineStart: 0, timelineEnd: 0, gapBefore: 0 };
}

function smoothNarrativeBeats(nodes: SpatialNarrativeNode[]): Map<string, NarrativeBeat> {
  const raw = nodes.map((node, index) => narrativeBeat(node, index, nodes.length));
  const weights = [1, 2, 4, 2, 1];
  return new Map(nodes.map((node, index) => {
    const samples = weights.map((weight, offset) => ({
      weight,
      beat: raw[Math.max(0, Math.min(raw.length - 1, index + offset - 2))],
    }));
    const total = samples.reduce((sum, item) => sum + item.weight, 0);
    const average = (field: keyof NarrativeBeat) => samples.reduce((sum, item) => sum + Number(item.beat[field]) * item.weight, 0) / total;
    return [node.node_id, {
      entry: average("entry"),
      peak: average("peak"),
      exit: average("exit"),
      detail: average("detail"),
      // Time is semantic rather than aesthetic data. Preserve this node's own
      // temporal boundary while its visual rhythm is smoothed with neighbours.
      timelineStart: raw[index].timelineStart,
      timelineEnd: raw[index].timelineEnd,
      gapBefore: raw[index].gapBefore,
    }];
  }));
}

function buildTemporalAxis(nodes: SpatialNarrativeNode[], rhythm: Map<string, NarrativeBeat>, sceneClusters: Map<string, SceneCluster>): Map<string, number> {
  const axis = new Map<string, number>();
  let position = -4.8;
  nodes.forEach((node, index) => {
    if (index) {
      const previous = rhythm.get(nodes[index - 1].node_id);
      const current = rhythm.get(node.node_id);
      const cluster = sceneClusters.get(node.node_id);
      const previousCluster = sceneClusters.get(nodes[index - 1].node_id);
      const baseStep = node.type === "chapter"
        ? CHAPTER_STEP
        : cluster && previousCluster && cluster.id !== previousCluster.id
          ? CHAPTER_CLUSTER_GAP
          : SCENE_STEP;
      position += baseStep * temporalSpacing(previous, current);
    }
    axis.set(node.node_id, position);
  });
  return axis;
}

function buildSceneClusters(scenes: SpatialNarrativeNode[]): Map<string, SceneCluster> {
  const groups = new Map<string, SpatialNarrativeNode[]>();
  for (const scene of scenes) {
    // Older projects without a chapter field remain one continuous route.
    // Canonical scene contracts carry chapter_id, which creates the real
    // book-scale visual clusters used by detailed views.
    const chapterId = String(scene.metrics.chapter_id || "__unassigned__");
    const group = groups.get(chapterId) || [];
    group.push(scene);
    groups.set(chapterId, group);
  }
  const result = new Map<string, SceneCluster>();
  [...groups.entries()].forEach(([id, group], rank) => {
    group.forEach((scene, localRank) => {
      result.set(scene.node_id, { id, rank, localRank, size: group.length });
    });
  });
  return result;
}

function temporalSpacing(previous?: NarrativeBeat, current?: NarrativeBeat): number {
  if (!current) return 1;
  if (current.gapBefore > 0) return clampSpacing(current.gapBefore);
  if (!previous || !current.timelineStart || !previous.timelineEnd) return 1;
  const temporalGap = current.timelineStart - previous.timelineEnd;
  // Flashbacks and overlapping time still advance in reading order; they get
  // a compact bridge rather than folding the narrative river backwards.
  if (temporalGap <= 0) return 0.76;
  // Logarithmic scaling keeps a multi-year jump meaningful without letting
  // one gap consume the whole canvas.
  return clampSpacing(1 + Math.log2(temporalGap) * 0.26);
}

function clampSpacing(value: number): number {
  return Math.max(0.76, Math.min(3.2, value));
}

function clampBeat(value: number | undefined, fallback: number): number {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? Math.max(1, Math.min(5, numeric)) : fallback;
}

function positiveNumber(value: number | undefined): number {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? Math.max(0, numeric) : 0;
}

function detailWeight(value: string | undefined): number {
  return ({ summary: -0.11, lean: -0.05, standard: 0, expanded: 0.07, set_piece: 0.14 } as Record<string, number>)[String(value || "standard")] || 0;
}

function rhythmLift(beat: NarrativeBeat): number {
  const tension = (beat.peak - 3) * 0.28;
  const handoff = (beat.exit - beat.entry) * 0.075;
  return tension + handoff + beat.detail;
}

function bookContour(index: number, count: number): number {
  if (count <= 2) return 0;
  const progress = index / Math.max(1, count - 1);
  // A low-frequency macro contour gives a full work a visible inhale, crest,
  // release and aftercurrent. It is bounded to one route along x rather than
  // a polar orbit, so rhythm can reshape the book without making it loop.
  return Math.sin(progress * Math.PI) * 0.62 + Math.sin(progress * Math.PI * 2) * 0.14 - 0.34;
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
  const magnitude = role.radius + (identity % 4) * role.spread;
  const elevation = role.elevation + (identity % 3) * 0.32;
  const depth = grammar === "strata" ? Math.cos(angle) * magnitude * 0.45 : Math.sin(angle) * magnitude;
  return {
    x: anchor.x + Math.cos(angle) * magnitude,
    y: Math.max(-0.35, anchor.y + elevation),
    z: anchor.z + depth + role.depthBias,
  };
}

function satelliteProfile(type: string): { radius: number; spread: number; elevation: number; depthBias: number } {
  if (type === "character") return { radius: 3.8, spread: 0.72, elevation: 1.35, depthBias: 0.95 };
  if (type === "canon") return { radius: 2.8, spread: 0.56, elevation: -1.48, depthBias: -2.35 };
  if (type === "task" || type === "review") return { radius: 3.1, spread: 0.62, elevation: 3.15, depthBias: 1.38 };
  if (type === "branch") return { radius: 4.25, spread: 0.88, elevation: 1.8, depthBias: 0.82 };
  if (type === "promise" || type === "reader-question") return { radius: 3.45, spread: 0.72, elevation: 2.02, depthBias: 0.52 };
  return { radius: 2.2, spread: 0.5, elevation: 1.25, depthBias: 0.35 };
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
  const type = node.type === "chapter" ? 3 : node.type === "scene" ? 2.7 : node.type === "canon" ? 2.3 : 1.2;
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
