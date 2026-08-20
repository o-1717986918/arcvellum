import type { ApiTransport, EventStreamConnection } from "@/services/api";
import { featureTransport } from "@/services/featureTransport";
import type {
  AgentObservability,
  AutopilotRun,
  AutopilotStatus,
  DashboardResponse,
  DelegationPolicy,
  HumanChoiceReceipt,
} from "@/types/api";

export interface WorkspaceSnapshot {
  project_root?: string;
  revision?: string;
  source_revisions?: Record<string, string>;
  dashboard: DashboardResponse;
  library: import("@/types/api").LibraryResponse;
  delivery: import("@/types/api").DeliveryResponse;
  reader_manifest: import("@/types/api").ReaderManifest;
  project_progress: import("@/types/api").ProjectProgress;
  autopilot_status: AutopilotStatus;
  agent_observability: AgentObservability;
}

export interface WorkflowChoice {
  id?: string;
  choice_id?: string;
  [key: string]: unknown;
}

export function createWorkflowClient(transport: ApiTransport = featureTransport) {
  const q = transport.query;
  return {
    dashboard: (projectRoot: string) => transport.request<DashboardResponse>(
      `/workflow/dashboard?${q({ project_root: projectRoot })}`,
    ),
    workspace: (projectRoot: string) => transport.request<WorkspaceSnapshot>(
      `/project/workspace?${q({ project_root: projectRoot })}`,
    ),
    observeWorkspace: (projectRoot: string, onSnapshot: (snapshot: WorkspaceSnapshot) => void) => transport.connect(
      `/project/workspace/stream?${q({ project_root: projectRoot, interval_seconds: 2 })}`,
      (event, data) => { if (event === "workspace.snapshot") onSnapshot(data as unknown as WorkspaceSnapshot); },
    ),
    observability: (projectRoot: string) => transport.request<AgentObservability>(
      `/agent-observability?${q({ project_root: projectRoot })}`,
    ),
    observeAgents: (projectRoot: string, onSnapshot: (snapshot: AgentObservability) => void) => transport.connect(
      `/agent-observability/stream?${q({ project_root: projectRoot, interval_seconds: 1 })}`,
      (event, data) => { if (event === "agent.observability") onSnapshot(data as unknown as AgentObservability); },
    ),
    autopilotStatus: (projectRoot: string) => transport.request<AutopilotStatus>(
      `/autopilot/status?${q({ project_root: projectRoot })}`,
    ),
    saveAutopilotPolicy: (projectRoot: string, policy: DelegationPolicy) => transport.request<{ policy: DelegationPolicy; run?: AutopilotRun }>(
      "/autopilot/policy",
      { method: "PUT", body: JSON.stringify({ project_root: projectRoot, policy }) },
    ),
    startAutopilot: (payload: Record<string, unknown>) => transport.request<{ run: AutopilotRun }>(
      "/autopilot/start",
      { method: "POST", body: JSON.stringify(payload) },
    ),
    pauseAutopilot: (runId: string, reason: string) => transport.request<{ run: AutopilotRun }>(
      `/autopilot/runs/${encodeURIComponent(runId)}/pause`,
      { method: "POST", body: JSON.stringify({ reason }) },
    ),
    resumeAutopilot: (runId: string, payload?: Record<string, unknown>) => transport.request<{ run: AutopilotRun }>(
      `/autopilot/runs/${encodeURIComponent(runId)}/resume`,
      { method: "POST", ...(payload ? { body: JSON.stringify(payload) } : {}) },
    ),
    observeAutopilot: (
      runId: string,
      onEvent: (event: string, data: Record<string, unknown>) => void,
    ): EventStreamConnection => transport.connect(
      `/autopilot/runs/${encodeURIComponent(runId)}/stream`,
      onEvent,
    ),
    runWorker: (projectRoot: string, route: string, runtime: string, extra: Record<string, unknown> = {}) => transport.request<Record<string, unknown>>(
      "/worker/run",
      { method: "POST", body: JSON.stringify({ project_root: projectRoot, route, runtime, ...extra }) },
    ),
    choices: (projectRoot: string, route?: string) => transport.request<{ items?: WorkflowChoice[]; choices?: WorkflowChoice[] }>(
      `/workflow/current-choice?${q({ project_root: projectRoot, route })}`,
    ),
    submitChoice: (payload: Record<string, unknown>) => transport.request<HumanChoiceReceipt>(
      "/workflow/human-choice",
      { method: "POST", body: JSON.stringify(payload) },
    ),
  };
}

export const workflowClient = createWorkflowClient();
