import type { NarrativeFocusLevel } from "@/features/orrery/model/focusScope";
import {
  RELATION_FAMILIES,
  type RelationFamily,
  type RelationLodMode,
  type RelationVisibilityProfile,
} from "@/features/orrery/model/relations";
import type { SpatialNarrativeProjection } from "@/types/spatial";

export interface RelationLensState {
  hidden: RelationFamily[];
  solo: RelationFamily | "";
}

export function relationModeForLevel(
  profile: RelationVisibilityProfile | undefined,
  level: NarrativeFocusLevel,
): RelationLodMode {
  if (!profile) return level === "book" ? "aggregate" : level === "chapter" ? "individual" : "emphasized";
  if (level === "book") return profile.far_mode;
  if (level === "chapter") return profile.mid_mode;
  return profile.near_mode;
}

export function applyRelationLens(
  projection: SpatialNarrativeProjection,
  state: RelationLensState,
): SpatialNarrativeProjection {
  const hidden = new Set(state.hidden);
  const visible = new Set<RelationFamily>(
    state.solo
      ? [state.solo]
      : RELATION_FAMILIES.filter((family) => !hidden.has(family)),
  );
  return {
    ...projection,
    relation_profiles: projection.relation_profiles
      .filter((profile) => visible.has(profile.family))
      .map((profile) => state.solo === profile.family
        ? { ...profile, far_mode: "emphasized", mid_mode: "emphasized", near_mode: "emphasized" }
        : profile),
    edges: projection.edges.filter((edge) => visible.has(edge.relation_family)),
  };
}
