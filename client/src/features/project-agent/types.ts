export type ProjectAgentRole = "user" | "assistant" | "tool";

export interface ProjectAgentMessage {
  sequence?: number;
  role: ProjectAgentRole;
  at?: string;
  payload: {
    text?: string;
    turn_id?: string;
    job_id?: string;
    [key: string]: unknown;
  };
}

export interface ProjectAgentSessionSummary {
  session_id: string;
  project_root: string;
  title: string;
  session_kind: "project-agent";
  created_at: string;
  updated_at: string;
}

export interface ProjectAgentSession extends ProjectAgentSessionSummary {
  snapshot_digest: string;
  session_summary?: string;
  pinned_user_preferences?: string[];
  messages: ProjectAgentMessage[];
}

export interface ProjectAgentTurnStart {
  session_id: string;
  turn_id: string;
  job_id: string;
  status: "queued" | string;
}

export interface ProjectAgentJob {
  job_id: string;
  status: string;
  error?: string;
  result?: {
    answer?: string;
    status?: string;
    tool_calls?: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface ProjectAgentStreamEvent {
  event: string;
  data: Record<string, unknown>;
  cursor: number;
}

export interface ProjectAgentToolActivity {
  key: string;
  name: string;
  label: string;
  status: "running" | "complete" | "failed";
}

export interface ProjectAgentTurnActivity {
  jobId: string;
  turnId: string;
  status: "queued" | "running" | "complete" | "failed";
  statusLabel: string;
  reasoning: string;
  tools: ProjectAgentToolActivity[];
  inputTokens: number;
  outputTokens: number;
  startedAt: number;
}

export const PROJECT_AGENT_TOOL_LABELS: Record<string, string> = {
  project_overview: "查看作品进度",
  project_search: "查找作品资料",
  creation_observe: "观察创作现场",
};
