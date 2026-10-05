export interface CorpusSource {
  source_id: string; work_id: string; text: string; split: "train" | "holdout";
  topic: string; genre: string; markdown: boolean;
  origin: string; revision: string;
}
export interface MetricTarget { id: string; unit: string; min: number; max: number; enabled: boolean }
export interface CreatorControls {
  schema: "stylometric-creator-controls/v1"; profile_sha256: string;
  dependency_parse_hash: string | null; targets: MetricTarget[];
}
export interface MetricRow {
  id: string; label: string; unit: string; group: string; observed: number | null;
  floor: number; ceiling: number | null; available: boolean; suggested: { min: number; max: number };
  source_range: { p25: number | null; p75: number | null };
}
export interface ProfileSummary { profile_id: string; title: string; created_at: string }
export interface StyloProfile extends ProfileSummary {
  schema: string; profile_json: string; controls: CreatorControls; inspection: Record<string, unknown>;
  source_declarations: Omit<CorpusSource, "text">[];
  dependency_json?: string; intent?: string;
}
export interface VersionSummary {
  version_id: string; profile_id: string; title: string; content_sha256: string; user_edited: boolean;
}
export interface StyloVersion extends VersionSummary {
  fragment_text: string; controls_json: string; dependency_json: string; compiled_json: string; intent: string;
}
export interface CreatorMount {
  enabled: boolean; revision: number; version_id: string; profile_id: string;
  combine: "append" | "replace"; usage: "guide" | "observe"; fragment_text: string;
  content_sha256: string; compiler_version: string;
}
export interface StyloWorkbench {
  schema: string; profiles: ProfileSummary[]; versions: VersionSummary[]; mount: CreatorMount;
  capabilities: { lab_version: string; dependency: string; ltp_generation: boolean; r_stylo: boolean };
  style_context: { author_directive: string; formal: string };
}
export interface StyloCompiled { schema: string; fragment_text: string; artifact_sha256: string; [key: string]: unknown }
export interface StyloMeasurement {
  schema: string; text_sha256: string; measurement: { axes: Record<string, number>; [key: string]: unknown };
  extended: Record<string, unknown>; diagnostics: Record<string, unknown>; dependency_status: string;
  targets?: { id: string; label: string; unit: string; enabled: boolean; observed: number | null;
    min: number; max: number; distance: number | null; in_range: boolean | null }[];
}
export interface StyloJob {
  job_id: string; title: string; status: string; phase: string; attempt: number; error: string;
  result: StyloProfile | { kind: "single-text"; result: StyloMeasurement } | null;
}
export interface FragmentRequest {
  project_root: string; profile_id: string; controls_json: string; title: string;
  intent: string; dependency_json: string;
}
export interface ParameterImport {
  profile_json: string; parameters_json: string; dependency_json: string; title: string; intent: string;
}
