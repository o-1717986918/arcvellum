import type { SpatialNarrativeNode } from "@/types/spatial";

export type OrreryHeatLens = "" | "rhythm" | "tension" | "promise" | "review";
export interface ScreenAnchor { x: number; y: number; visible: boolean; scale?: number }
export interface ScreenRect { left: number; top: number; right: number; bottom: number }

export function viewBookmarkLabel(
  nodes: SpatialNarrativeNode[],
  level: string,
  focus: string,
  grammarLabel: string,
): string {
  if (level === "book" || !focus || focus === "book") return `全书 · ${grammarLabel}`;
  const focusNode = nodes.find((node) => node.node_id === focus || node.source_id === focus);
  const levelLabel = ({ chapter: "章节", scene: "场景", character: "人物" } as Record<string, string>)[level] || "焦点";
  return `${levelLabel} · ${focusNode?.label || focus}`;
}

export function viewBookmarkMeta(level: string, grammar: string): string {
  const levelLabel = ({ book: "全书", chapter: "章节", scene: "场景", character: "人物" } as Record<string, string>)[level] || "焦点";
  const grammarLabel = ({
    braid: "编织",
    constellation: "星簇",
    loop: "回环",
    spine: "脊柱",
    stage: "舞台",
    strata: "层室",
  } as Record<string, string>)[grammar] || grammar;
  return `${levelLabel} · ${grammarLabel}`;
}

export function narrativePath(nodes: SpatialNarrativeNode[], level: string): SpatialNarrativeNode[] {
  const preferred = level === "book" ? "chapter" : "scene";
  const route = nodes.filter((node) => node.type === preferred);
  const fallback = nodes.filter((node) => node.type === "chapter" || node.type === "scene");
  return (route.length ? route : fallback)
    .sort((left, right) => left.order - right.order || left.node_id.localeCompare(right.node_id));
}

export function nodesInScreenRect(
  nodes: SpatialNarrativeNode[],
  anchors: Record<string, ScreenAnchor>,
  rect: ScreenRect,
): SpatialNarrativeNode[] {
  const bounds = normalizeRect(rect);
  return nodes
    .filter((node) => {
      const anchor = anchors[node.node_id];
      return Boolean(anchor?.visible)
        && anchor.x >= bounds.left
        && anchor.x <= bounds.right
        && anchor.y >= bounds.top
        && anchor.y <= bounds.bottom;
    })
    .sort((left, right) => left.order - right.order || left.node_id.localeCompare(right.node_id));
}

export function heatScore(node: SpatialNarrativeNode, lens: OrreryHeatLens): number {
  if (!lens) return 0;
  if (lens === "rhythm") {
    const peak = finite(node.rhythm?.peak, finite(node.metrics.rhythm_peak, 0));
    const detail = detailWeight(String(node.rhythm?.detail_level || node.metrics.detail_level || ""));
    return clamp01(peak / 5 * 0.82 + detail);
  }
  if (lens === "tension") {
    const peak = finite(node.rhythm?.peak, finite(node.metrics.tension, finite(node.metrics.tension_score, 0)));
    const entry = finite(node.rhythm?.entry, 0);
    const exit = finite(node.rhythm?.exit, 0);
    const movement = Math.abs(peak - entry) + Math.abs(peak - exit);
    return clamp01(peak / 5 * 0.78 + movement / 10 * 0.22);
  }
  if (lens === "promise") {
    if (node.type === "promise") return 1;
    if (node.type === "reader-question") return 0.82;
    return clamp01(
      finite(node.metrics.promise_count, 0) * 0.24
      + finite(node.metrics.reader_question_count, 0) * 0.18
      + finite(node.metrics.payoff_count, 0) * 0.2,
    );
  }
  if (node.type === "review") return 1;
  if (node.status === "blocked") return 0.94;
  return clamp01(
    finite(node.metrics.review_issue_count, 0) * 0.18
    + finite(node.metrics.repair_count, 0) * 0.16
    + finite(node.metrics.risk, 0) / 5,
  );
}

export function heatLabel(lens: OrreryHeatLens): string {
  return {
    "": "关闭",
    rhythm: "叙事呼吸",
    tension: "张力变化",
    promise: "承诺债务",
    review: "审查风险",
  }[lens];
}

function normalizeRect(rect: ScreenRect): ScreenRect {
  return {
    left: Math.min(rect.left, rect.right),
    top: Math.min(rect.top, rect.bottom),
    right: Math.max(rect.left, rect.right),
    bottom: Math.max(rect.top, rect.bottom),
  };
}

function finite(value: unknown, fallback: number): number {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function detailWeight(value: string): number {
  return ({ summary: 0, lean: 0.03, standard: 0.07, expanded: 0.12, set_piece: 0.18 } as Record<string, number>)[value] || 0;
}
