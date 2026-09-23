export type CreativeLiveChannel = "activity" | "transcript" | "artifact" | "review" | "usage" | "control";

export type ArtifactIdentity =
  | "streaming_preview"
  | "candidate_written"
  | "deterministic_preflight_passed"
  | "semantic_review_passed"
  | "promoted"
  | "state_and_canon_applied"
  | "validation_failed"
  | "revision_streaming"
  | "revision_written"
  | "superseded"
  | "rejected";

export interface CreativeArtifactRef {
  artifact_id: string;
  path: string;
  kind: string;
  format: string;
  identity: ArtifactIdentity;
  revision: number;
  digest: string;
  characters: number;
}

export interface CreativeLiveEvent {
  schema: string;
  event_id: string;
  sequence: number;
  event: string;
  channel: CreativeLiveChannel;
  visibility: "user" | "advanced" | "diagnostic" | "restricted";
  durability: "ephemeral" | "durable";
  at: string;
  project_id: string;
  run_id: string;
  session_id: string;
  task_id: string;
  route: string;
  attempt_id: string;
  artifact: CreativeArtifactRef | null;
  data: Record<string, unknown>;
}

export interface CreativeArtifact extends CreativeArtifactRef {
  content: string;
  updated_at: string;
  source_event: string;
  truncated?: boolean;
}

export interface CreativeSession {
  session_id: string;
  role: string;
  runtime: string;
  status: string;
  route: string;
  task_id: string;
  transcript: string;
  tools: Array<{ event: string; tool?: string; status?: string; at?: string }>;
  updated_at?: string;
  last_event?: string;
  model?: string;
  started_at?: string;
  finished_at?: string;
  context_ledger_id?: string;
  context_ledger_digest?: string;
  context?: CreativeContextSummary | null;
}

export interface CreativeContextEntry {
  title: string;
  purpose: string;
  partition: string;
  character_count: number;
  included: boolean;
  truncated: boolean;
  visibility: string;
}

export interface CreativeContextSummary {
  available: boolean;
  digest: string;
  entry_count: number;
  included_count?: number;
  character_count?: number;
  entries: CreativeContextEntry[];
}

export interface CreativeActivity {
  event_id: string;
  event: string;
  channel: CreativeLiveChannel;
  at: string;
  task_id: string;
  route: string;
  title?: string;
  message?: string;
}

export interface CreativeReview {
  event_id: string;
  event: string;
  at: string;
  task_id: string;
  route: string;
  title?: string;
  message?: string;
  status?: string;
  findings?: unknown[];
  artifact_id?: string;
}

export interface SceneTransactionSummary {
  transaction_id: string;
  scene_id: string;
  status: string;
  mode: string;
  risk: "low" | "standard" | "high";
  objective: string;
  scene_function: string;
  body_hanzi: number;
  warning_count: number;
  hard_issue_count: number;
  review_decision: string;
  review_summary: string;
  revision_attempts: number;
  requires_input: boolean;
  message: string;
  version: number;
}

export interface StyleProvenance {
  source: "lean-runtime" | "formal-manifest";
  scene_id: string;
  style_version_id: string;
  selection_status: string;
  selector_version: string;
  selection_digest: string;
  reference_ids: string[];
  technique_axes: string[];
  expression_plan_digest: string;
  voice_digest: string;
}

export interface CreativeLiveSnapshot {
  ok: boolean;
  schema: string;
  project_id: string;
  revision: string;
  status: "active" | "blocked" | "paused" | "idle";
  controller: Record<string, unknown> | null;
  active_task: Record<string, unknown> | null;
  artifacts: CreativeArtifact[];
  sessions: CreativeSession[];
  activity: CreativeActivity[];
  reviews: CreativeReview[];
  usage: { total_tokens: number; cost_usd: number; updates: number };
  active_scene_transaction: SceneTransactionSummary | null;
  scene_transactions: SceneTransactionSummary[];
  style_provenance: StyleProvenance | null;
  events: CreativeLiveEvent[];
  cursor: number;
}

export interface ArtifactRevisionSummary {
  revision_id: string;
  artifact_id: string;
  event_id: string;
  at: string;
  identity: ArtifactIdentity;
  digest: string;
  characters: number;
  finding_refs: string[];
}

export interface ArtifactRevision extends ArtifactRevisionSummary {
  content: string;
  diff: string;
}
