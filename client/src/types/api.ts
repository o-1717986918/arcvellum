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

export interface AdvisorAction {
  type: "open_view" | "record_direction" | "prepare_next_task" | "pause_autopilot" | "request_revision";
  label: string;
  target?: "overview" | "library" | "delivery" | "settings";
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
  updated_at: string;
}

export interface AutopilotStatus {
  ok: boolean;
  schema: string;
  policy: DelegationPolicy;
  run: AutopilotRun | null;
  decisions?: Array<Record<string, unknown>>;
}
