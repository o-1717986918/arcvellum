export const RELATION_FAMILIES = [
  "narrative-spine",
  "chapter-scene",
  "scene-branch",
  "scene-review",
  "scene-reader-question",
  "scene-promise-payoff",
  "character-scene",
  "evidence-claim",
  "canon-state-impact",
  "workflow-control",
  "context-association",
] as const;

export const RELATION_LOD_MODES = ["aggregate", "individual", "emphasized"] as const;
export const RELATION_FOCUS_STATES = ["global", "internal", "attached", "context"] as const;

export type RelationFamily = (typeof RELATION_FAMILIES)[number];
export type RelationLodMode = (typeof RELATION_LOD_MODES)[number];
export type RelationFocusState = (typeof RELATION_FOCUS_STATES)[number];

export interface RelationVisibilityProfile {
  family: RelationFamily;
  label: string;
  edge_count: number;
  focused_edge_count: number;
  far_mode: RelationLodMode;
  mid_mode: RelationLodMode;
  near_mode: RelationLodMode;
  aggregate_anchor: string;
  base_weight: number;
  focus_weight: number;
}

export function parseRelationVisibilityProfile(value: unknown): RelationVisibilityProfile {
  const source = isRecord(value) ? value : {};
  return {
    family: member(source.family, RELATION_FAMILIES, "context-association"),
    label: String(source.label || "").trim(),
    edge_count: nonNegativeNumber(source.edge_count),
    focused_edge_count: nonNegativeNumber(source.focused_edge_count),
    far_mode: member(source.far_mode, RELATION_LOD_MODES, "aggregate"),
    mid_mode: member(source.mid_mode, RELATION_LOD_MODES, "individual"),
    near_mode: member(source.near_mode, RELATION_LOD_MODES, "emphasized"),
    aggregate_anchor: String(source.aggregate_anchor || "chapter-centroid").trim(),
    base_weight: nonNegativeNumber(source.base_weight),
    focus_weight: nonNegativeNumber(source.focus_weight),
  };
}

function member<T extends string>(value: unknown, values: readonly T[], fallback: T): T {
  return typeof value === "string" && values.includes(value as T) ? value as T : fallback;
}

function nonNegativeNumber(value: unknown): number {
  const number = Number(value || 0);
  return Number.isFinite(number) ? Math.max(0, number) : 0;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
