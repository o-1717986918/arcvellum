import type { SpatialNarrativeNode } from "@/types/spatial";

const CHAPTER_STEP = 10.8;
export const SCENE_STEP = 1.55;
export const CHAPTER_CLUSTER_GAP = 10.8;

export interface SceneCluster {
  id: string;
  rank: number;
  localRank: number;
  size: number;
}

export interface NarrativeBeat {
  entry: number;
  peak: number;
  exit: number;
  detail: number;
  timelineStart: number;
  timelineEnd: number;
  gapBefore: number;
}

export function narrativeBeat(node: SpatialNarrativeNode, index: number, count: number): NarrativeBeat {
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
  const fallbackPeak = 2.55 + bookContour(index, count) * 0.72;
  return { entry: 2.25, peak: fallbackPeak, exit: 2.15, detail: 0, timelineStart: 0, timelineEnd: 0, gapBefore: 0 };
}

export function smoothNarrativeBeats(nodes: SpatialNarrativeNode[]): Map<string, NarrativeBeat> {
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
      timelineStart: raw[index].timelineStart,
      timelineEnd: raw[index].timelineEnd,
      gapBefore: raw[index].gapBefore,
    }];
  }));
}

export function buildTemporalAxis(
  nodes: SpatialNarrativeNode[],
  rhythm: Map<string, NarrativeBeat>,
  sceneClusters: Map<string, SceneCluster>,
): Map<string, number> {
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

export function buildSceneClusters(scenes: SpatialNarrativeNode[]): Map<string, SceneCluster> {
  const groups = new Map<string, SpatialNarrativeNode[]>();
  for (const scene of scenes) {
    const chapterId = normalizeChapterId(String(scene.metrics.chapter_id || ""));
    if (!chapterId) continue;
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

export function chapterIdentity(node: SpatialNarrativeNode): string {
  return normalizeChapterId(String(node.metrics.chapter_id || node.source_id || node.node_id));
}

export function rhythmLift(beat: NarrativeBeat): number {
  const tension = (beat.peak - 3) * 0.28;
  const handoff = (beat.exit - beat.entry) * 0.075;
  return tension + handoff + beat.detail;
}

export function bookContour(index: number, count: number): number {
  if (count <= 2) return 0;
  const progress = index / Math.max(1, count - 1);
  return Math.sin(progress * Math.PI) * 0.62 + Math.sin(progress * Math.PI * 2) * 0.14 - 0.34;
}

function normalizeChapterId(value: string): string {
  return value.trim().replace(/^chapter:/, "");
}

function temporalSpacing(previous?: NarrativeBeat, current?: NarrativeBeat): number {
  if (!current) return 1;
  if (current.gapBefore > 0) return clampSpacing(current.gapBefore);
  if (!previous || !current.timelineStart || !previous.timelineEnd) return 1;
  const temporalGap = current.timelineStart - previous.timelineEnd;
  if (temporalGap <= 0) return 0.76;
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
