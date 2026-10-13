export interface StylePreset {
  preset_id: string; title: string; literary_intent: string; narrative_modes: string[];
  reference_ids: string[]; stylometry_version_id: string; active: boolean;
  combine: "append" | "replace"; usage: "guide" | "observe";
}
export interface StyleReference {
  unit_id: string; text: string; source_digest: string; source_kind: string;
  source_title: string; source_url: string; narrative_modes: string[]; technique_axes: string[];
}
export interface StylePresetCatalog {
  revision: number; enabled: boolean; default_preset_id: string; presets: StylePreset[];
  reference_catalog?: { references: StyleReference[] };
}
