export type StyleRecord = Record<string, unknown>;

export interface StyleRights extends StyleRecord {
  status: "declared" | "missing" | string;
  mode?: string;
  declaration?: string;
  modes?: string[];
}

export interface StyleSource extends StyleRecord {
  source_id: string;
  filename: string;
  content_sha256: string;
  character_count: number;
  chunk_count: number;
  imported_at?: string;
}

export interface StyleWork extends StyleRecord {
  work_id: string;
  title: string;
  year?: string;
  notes?: string;
  sources: StyleSource[];
  source_count: number;
}

export interface StyleAuthor extends StyleRecord {
  author_id: string;
  name: string;
  rights: StyleRights;
  works: StyleWork[];
  work_count: number;
  profile_count: number;
  style_skill_count?: number;
  updated_at?: string;
}

export interface StyleEvaluation extends StyleRecord {
  overall_score?: number;
  risk_level?: string;
  style_quality_status?: string;
  leakage_risk_status?: string;
}

export interface StyleVersion extends StyleRecord {
  style_id: string;
  version_id: string;
  planned_version_id?: string;
  author_id: string;
  profile_id: string;
  display_name?: string;
  state: string;
  source_count: number;
  rights?: StyleRights;
  prompt_quality?: StyleRecord;
  evaluations?: StyleEvaluation[];
  accepted_evaluation_count: number;
  review_status: string;
  content_hash: string;
  planned_content_hash?: string;
  built?: boolean;
  mounted?: boolean;
  build_status?: string;
  blocking_reasons?: string[];
}

export interface StyleMount extends StyleRecord {
  style_id?: string;
  version_id?: string;
  author?: string;
  author_id?: string;
  profile_id?: string;
  scope?: string;
  priority?: string;
  readiness?: string;
  review_status?: string;
  content_hash?: string;
  integrity?: string | StyleRecord;
}

export interface StyleJourneyStage extends StyleRecord {
  id: string;
  label: string;
  status: "ready" | "waiting" | string;
  count: number;
}

export interface StyleAtelierSummary extends StyleRecord {
  author_count: number;
  work_count: number;
  source_count: number;
  source_character_count: number;
  profile_count: number;
  evaluated_count: number;
  reviewed_count: number;
  built_count: number;
  mounted_count: number;
}

export interface StyleAtelierWorkbench extends StyleRecord {
  schema: "arcvellum/style-atelier-workbench/v1";
  revision: string;
  authors: StyleAuthor[];
  versions: StyleVersion[];
  active_mount: StyleMount;
  summary: StyleAtelierSummary;
  journey: StyleJourneyStage[];
  issues: string[];
}

export interface StyleVersionDetail extends StyleRecord {
  schema: "arcvellum/style-profile-version-detail/v1";
  style_id: string;
  version_id: string;
  content_hash: string;
  author_id: string;
  profile_id: string;
  compiler_version?: string;
  state: string;
  integrity?: StyleRecord;
  source_evidence?: StyleRecord[];
  prompt_quality?: StyleRecord;
  evaluation?: StyleEvaluation;
  review?: StyleRecord;
  priority?: StyleRecord;
  copy_boundary?: string;
  artifacts?: Array<{ name: string; sha256: string }>;
}

export type StyleRightsMode =
  | "public-domain"
  | "authorized"
  | "user-owned"
  | "craft-only";

export interface StyleTransactionReceipt extends StyleRecord {
  schema: "arcvellum/style-author-transaction/v1";
  transaction_id: string;
  operation: "create-author" | "create-work" | "import-source";
  status: "committed";
  subject: {
    author_id: string;
    work_id?: string;
    source_id?: string;
  };
  evidence?: StyleRecord;
}

export interface StyleAuthorCreatePayload {
  author_id: string;
  name: string;
  rights_mode: StyleRightsMode;
  rights_declaration: string;
}

export interface StyleWorkCreatePayload {
  author_id: string;
  work_id: string;
  title: string;
  year?: string;
  notes?: string;
}

export interface StyleSourceCreatePayload {
  author_id: string;
  work_id: string;
  filename: string;
  media_type: "text/plain" | "text/markdown";
  content: string;
  rights_mode: StyleRightsMode;
  rights_declaration: string;
}

export interface StyleSourceSelection {
  work_id: string;
  source_id: string;
}

export interface StyleCompilePayload {
  project_root: string;
  author_id: string;
  profile_id: string;
  display_name: string;
  training_sources: StyleSourceSelection[];
  holdout_sources: StyleSourceSelection[];
  runtime: string;
}

export interface StyleAdvancePayload {
  project_root: string;
  author_id: string;
  profile_id: string;
  runtime: string;
}

export type StyleBuildPayload = StyleAdvancePayload;

export interface StyleTaskDescriptor extends StyleRecord {
  task_id: string;
  current_state: string;
  status: string;
}

export interface StyleWorkerJob extends StyleRecord {
  schema?: string;
  job_id: string;
  status: string;
  created_at?: string;
  updated_at?: string;
  started_at?: string;
  finished_at?: string;
  request?: StyleRecord;
  result?: StyleRecord;
  error?: string;
  revision?: number;
}

export interface StyleTaskLaunch extends StyleRecord {
  schema: string;
  status: string;
  task?: StyleTaskDescriptor;
  session?: {
    session_id: string;
    author_id: string;
    profile_id: string;
    status: string;
  };
  style_id?: string;
  version_id?: string;
  content_hash?: string;
  job: StyleWorkerJob | null;
}

export interface StyleWorkerEvent extends StyleRecord {
  sequence?: number;
  event: string;
  at?: string;
  data: StyleRecord;
}

export interface StyleMountIdentity extends StyleRecord {
  style_id?: string;
  version_id?: string;
  content_hash?: string;
  prompt_sha256?: string;
  digest?: string;
}

export interface StyleVersionComparisonRow extends StyleRecord {
  field: string;
  label: string;
  before: string | number;
  after: string | number;
  changed: boolean;
}

export interface StyleMountImpactEntry extends StyleRecord {
  scene_id: string;
  stages: string[];
  artifact_count: number;
  recorded_versions: string[];
  reason: string;
}

export interface StyleMountImpact extends StyleRecord {
  status: string;
  mount_changes: boolean;
  affected_scene_count: number;
  affected_artifact_count: number;
  historical_artifact_count: number;
  inspected_artifact_count: number;
  entries: StyleMountImpactEntry[];
  invalidated_stages: string[];
  historical_prose: "preserved";
  revision: string;
}

export interface StyleMountPreview extends StyleRecord {
  schema: "arcvellum/style-mount-preview/v1";
  status: "already-mounted" | "confirmation-required";
  revision: string;
  current: StyleMountIdentity;
  target: StyleMountIdentity;
  comparison: {
    status: string;
    changes: StyleVersionComparisonRow[];
    evidence: StyleVersionComparisonRow[];
  };
  impact: StyleMountImpact;
  requires_confirmation: boolean;
}

export interface StyleMountTransaction extends StyleRecord {
  schema: "arcvellum/style-mount-transaction/v1";
  status: "mounted" | "already-mounted";
  style_id: string;
  version_id: string;
  content_hash: string;
  preview_revision: string;
  active_mount: StyleMount;
  impact: StyleMountImpact;
}

export interface StyleMountPayload {
  project_root: string;
  style_id: string;
  version_id: string;
  content_hash: string;
  scope: "project";
  priority: "highest";
  preview_revision?: string;
}
