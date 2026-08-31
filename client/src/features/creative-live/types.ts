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
