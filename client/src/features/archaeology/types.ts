export type ArchaeologyModeId =
  | "continuation"
  | "rewrite"
  | "adaptation"
  | "analysis";

export type ArchaeologyRecord = Record<string, unknown>;

export interface ArchaeologyMode {
  id: ArchaeologyModeId;
  label: string;
  intent: string;
}

export interface ArchaeologyOptions {
  schema: string;
  modes: ArchaeologyMode[];
  supported_extensions: string[];
  max_source_bytes: number;
}

export interface ArchaeologyState {
  status: string;
  current_step: string;
  next_action: string;
  message: string;
  chunk_id: string;
}

export interface ArchaeologyJourneyStage {
  id: string;
  label: string;
  status: "complete" | "active" | "waiting";
  count: number;
}

export interface ArchaeologyCatalogItem {
  work_id: string;
  title: string;
  mode: ArchaeologyMode;
  source_count: number;
  chunk_count: number;
  status: ArchaeologyState;
  recovery: ArchaeologyRecovery;
}

export interface ArchaeologyRecovery {
  interrupted: boolean;
  staging_detected: boolean;
  backup_detected: boolean;
  resume_supported: boolean;
}

export interface ArchaeologyRecoveryNotice {
  work_id: string;
  kind: "staging" | "backup";
  message: string;
}

export interface ArchaeologyCatalog {
  schema: string;
  count: number;
  imports: ArchaeologyCatalogItem[];
  recovery: ArchaeologyRecoveryNotice[];
  revision: string;
}

export interface ArchaeologySource {
  source_id: string;
  title: string;
  filename: string;
  media_type: string;
  extraction_method: string;
  content_sha256: string;
  character_count: number;
}

export interface ArchaeologyChunk {
  chunk_id: string;
  title: string;
  kind: string;
  evidence_count: number;
}

export interface ArchaeologySegmentation {
  segment_count: number;
  chunk_count: number;
  chunks: ArchaeologyChunk[];
}

export interface ArchaeologyEntityGroup {
  entity_id: string;
  display_name: string;
  entity_type: string;
  aliases: string[];
  resolution: string;
  confidence: number | null;
  unknowns: string[];
  occurrence_count: number;
}

export interface ArchaeologyEntities {
  occurrence_count: number;
  resolved_count: number;
  groups: ArchaeologyEntityGroup[];
}

export interface ArchaeologyConflict {
  index: number;
  kind: string;
  summary: string;
  evidence_refs: string[];
  disposition: string;
  rationale: string;
}

export interface ArchaeologyConflicts {
  count: number;
  unresolved_count: number;
  items: ArchaeologyConflict[];
}

export interface ArchaeologyDomainReview {
  domain: string;
  status: string;
  blockers: string[];
  warnings: string[];
}

export interface ArchaeologyReconstructedAsset {
  candidate_id: string;
  asset_type: string;
  confidence: number | null;
  recommendation: string;
  decision: string;
  evidence_count: number;
  unresolved_count: number;
}

export interface ArchaeologyReconstruction {
  summary: ArchaeologyRecord;
  status: string;
  domains: ArchaeologyDomainReview[];
  assets: ArchaeologyReconstructedAsset[];
}

export interface ArchaeologyPromotionItem {
  candidate_id: string;
  asset_type: string;
  status: string;
}

export interface ArchaeologyPromotionQueue {
  status: string;
  ready_count: number;
  deferred_count: number;
  items: ArchaeologyPromotionItem[];
}

export interface ArchaeologyEvidence {
  revision: string;
  reference_count: number;
  aggregate_revision: string;
}

export interface ArchaeologyWorkbench {
  schema: string;
  work_id: string;
  title: string;
  mode: ArchaeologyMode;
  status: ArchaeologyState;
  journey: ArchaeologyJourneyStage[];
  sources: ArchaeologySource[];
  segmentation: ArchaeologySegmentation;
  entities: ArchaeologyEntities;
  conflicts: ArchaeologyConflicts;
  reconstruction: ArchaeologyReconstruction;
  promotion_queue: ArchaeologyPromotionQueue;
  evidence: ArchaeologyEvidence;
  recovery: ArchaeologyRecovery;
  revision: string;
}

export interface ArchaeologyImportForm {
  title: string;
  work_id: string;
  mode: ArchaeologyModeId;
  rights_declaration: string;
  chunk_size: number;
  overwrite: boolean;
}

export interface ArchaeologyImportResponse {
  receipt: {
    schema: string;
    work_id: string;
    mode: ArchaeologyModeId;
    source_count: number;
    chunk_count: number;
    status: string;
    next_action: string;
  };
  workbench: ArchaeologyWorkbench;
}

export interface ArchaeologyWorkerJob extends ArchaeologyRecord {
  job_id: string;
  status: string;
  revision?: number;
  error?: string;
  result?: ArchaeologyRecord;
}

export interface ArchaeologyWorkerEvent extends ArchaeologyRecord {
  sequence: number;
  event: string;
  at: string;
  data: ArchaeologyRecord;
}
