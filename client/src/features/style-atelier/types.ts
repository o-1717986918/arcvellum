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
