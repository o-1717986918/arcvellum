export type BootstrapStatus = "ready" | "loading" | "waiting" | "degraded" | "blocked" | "deferred" | "failed";

export interface BootstrapStep {
  id: string;
  label: string;
  status: BootstrapStatus;
  blocking: boolean;
  detail: string;
  recovery_action: string;
}

export interface ProjectSummary {
  path: string;
  title: string;
  work_type: string;
  target_length: number;
  status: string;
  genre: string;
  premise: string;
  direction_count: number;
  last_opened?: string;
}

export interface BootstrapSnapshot {
  ok: boolean;
  schema: string;
  phase: "starting" | "ready" | "degraded" | "blocked";
  ready: boolean;
  can_enter_workspace: boolean;
  degraded: boolean;
  progress: { completed: number; total: number };
  steps: BootstrapStep[];
  notices: string[];
  project: ProjectSummary | null;
  project_count: number;
  model_catalog: ModelCatalog | null;
  model_warmup: { status: BootstrapStatus; attempted_at: string; loaded_at: string; error: string };
}

export interface ModelItem {
  id: string;
  qualified_id: string;
  name: string;
  context: number;
}

export interface ProviderItem {
  id: string;
  name: string;
  connected: boolean;
  default_model: string;
  auth_methods: Array<{ type: string; label: string }>;
  models: ModelItem[];
  model_count: number;
}

export interface ModelCatalog {
  runner?: string;
  version?: string;
  selected_model?: string;
  selected_models?: Record<"worker" | "advisor" | "steward", string>;
  providers: ProviderItem[];
  connected_provider_count?: number;
  available_model_count?: number;
}

export interface ProjectsResponse {
  ok: boolean;
  current_project: string;
  projects: ProjectSummary[];
}

export interface LibrarySection {
  id?: string;
  key?: string;
  title?: string;
  label?: string;
  count?: number;
  items?: unknown[];
  [key: string]: unknown;
}

export interface LibraryResponse {
  ok: boolean;
  project?: Record<string, unknown>;
  summary?: Record<string, unknown>;
  sections: LibrarySection[] | Record<string, unknown>;
  manuscript?: Record<string, unknown> | unknown[];
  [key: string]: unknown;
}

export interface ReaderUnitSummary {
  unit_id: string;
  volume_id: string;
  chapter_id: string;
  scene_id: string;
  order: number;
  title: string;
  status: "promoted" | "chapter" | "exported" | "published";
  source_kind: "scene" | "chapter" | "release";
  source_revision: string;
  content_hash: string;
  chinese_content_chars: number;
  machine_nonspace_chars: number;
  coverage: string[];
  body_endpoint: string;
}

export interface ReaderManifest {
  ok: boolean;
  schema: "arcvellum/reader-manifest/v1";
  project_root: string;
  project_revision: string;
  generated_at: string;
  unit_count: number;
  total_chinese_content_chars: number;
  units: ReaderUnitSummary[];
  warnings: Array<{ code: string; chapter_id?: string; message: string }>;
  delta?: { added: string[]; removed: string[]; initial: boolean };
}

export interface ReaderUnitResponse {
  ok: boolean;
  schema: "arcvellum/reader-unit/v1";
  unit: ReaderUnitSummary;
  body: string;
}

export interface NarrativeNode {
  node_id: string;
  type: string;
  label: string;
  subtitle: string;
  status: "planned" | "queued" | "current" | "formal" | "memory" | "blocked" | "alternative";
  source_type: string;
  source_id: string;
  navigate: string;
  metrics: Record<string, number>;
  order: number;
}

export interface NarrativeEdge {
  edge_id: string;
  source: string;
  target: string;
  type: string;
  label: string;
}

export interface NarrativeProjection {
  ok: boolean;
  schema: "arcvellum/narrative-projection/v2";
  project_root: string;
  generated_at: string;
  revision: string;
  sequence: number;
  level: "book" | "chapter" | "scene";
  focus: string;
  summary: Record<string, number | boolean>;
  nodes: NarrativeNode[];
  edges: NarrativeEdge[];
  timeline: Array<{ node_id: string; label: string; status: string; order: number; formal_chars: number; word_target: number }>;
  delta: {
    initial: boolean;
    added_nodes: string[];
    removed_nodes: string[];
    updated_nodes: string[];
    added_edges: string[];
    removed_edges: string[];
    updated_edges: string[];
  };
  motion_events: Array<{ type: string; node_id: string; label: string }>;
  legend: Array<{ type: string; label: string; color: string }>;
  accessibility_summary: string;
}

export interface DashboardResponse {
  ok: boolean;
  project?: Record<string, unknown>;
  workflow_state?: Record<string, unknown>;
  current_task?: Record<string, unknown> | null;
  route_audits?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface DeliveryFile {
  path: string;
  name?: string;
  format?: string;
  size?: number;
  modified_at?: string;
}

export interface DeliveryResponse {
  ok: boolean;
  project_root: string;
  status: string;
  files: DeliveryFile[];
  blockers?: unknown[];
  [key: string]: unknown;
}

export interface ProjectProgressPart {
  id: "preparation" | "manuscript" | "integrity";
  label: string;
  weight: number;
  percent: number | null;
  actual?: number;
  target?: number | null;
  checks?: Array<{ id: string; label: string; complete: boolean }>;
  message?: string;
}

export interface ProjectProgress {
  ok: boolean;
  schema: "arcvellum/project-progress/v1";
  status: "calibrated" | "waiting_calibration";
  overall_percent: number | null;
  target_chinese_content_chars: number;
  formal_chinese_content_chars: number;
  parts: ProjectProgressPart[];
  source_revisions: Record<string, string>;
  revision: string;
}

export interface AgentObservableEvent {
  sequence: number;
  at: string;
  event: string;
  stage: string;
  message: string;
  task_id: string;
  route: string;
}

export interface AgentObservability {
  ok: boolean;
  schema: "arcvellum/agent-observability/v1";
  project_root: string;
  status: "active" | "idle";
  active_task: {
    role: string;
    runtime: string;
    route: string;
    task_id: string;
    status: string;
    stage: string;
    message: string;
    tasks_completed: number;
    failures: number;
  } | null;
  sessions: Array<{ session_id: string; role: string; runtime: string; status: string; route: string; event_count: number; started_at: string }>;
  recent_events: AgentObservableEvent[];
  revision: string;
}

export interface AdvisorAction {
  type: "open_view" | "record_direction" | "run_next_task" | "prepare_next_task" | "start_autopilot" | "pause_autopilot" | "resume_autopilot" | "request_revision";
  label: string;
  target?: "overview" | "reader" | "library" | "quality" | "delivery" | "settings";
  message?: string;
  route?: string;
}

export interface AdvisorAnswer {
  schema?: string;
  message: string;
  answer?: string;
  evidence: Array<{ statement: string; citation: string }>;
  uncertainties: string[];
  suggested_actions: AdvisorAction[];
  project_unchanged?: boolean;
  snapshot_stale_at_start?: boolean;
}

export interface AdvisorMessage {
  sequence?: number;
  role: "user" | "advisor";
  at?: string;
  payload: Partial<AdvisorAnswer> & { question?: string };
}

export interface AdvisorSession {
  session_id: string;
  project_root: string;
  title: string;
  messages: AdvisorMessage[];
}

export type AutopilotMode = "collaborative" | "supervised_auto" | "full_auto";

export interface DelegationPolicy {
  schema: string;
  version: string;
  mode: AutopilotMode;
  delegated_routes: string[];
  delegated_decisions: string[];
  limits: {
    max_tasks: number;
    max_runtime_hours: number;
    max_consecutive_revisions: number;
    max_failures_per_task: number;
    max_cost: number;
  };
  release_policy: "require_user" | "delegated";
  expires_at: string;
}

export interface AutopilotRun {
  run_id: string;
  project_root: string;
  mode: AutopilotMode;
  runtime: string;
  status: "running" | "paused" | "blocked" | "complete" | "cancelled" | "failed";
  current_route: string;
  current_task_id: string;
  tasks_completed: number;
  failures: number;
  consecutive_revisions: number;
  estimated_cost: number;
  last_error: string;
  stop_reason: string;
  created_at: string;
  started_at: string;
  updated_at: string;
}

export interface AutopilotStatus {
  ok: boolean;
  schema: string;
  policy: DelegationPolicy;
  run: AutopilotRun | null;
  decisions?: Array<Record<string, unknown>>;
}
