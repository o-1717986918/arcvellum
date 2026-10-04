import { bootstrapDesktopSession, type ApiTransport } from "@/services/api";
import { featureTransport } from "@/services/featureTransport";
import type { BootstrapSnapshot, ModelCatalog } from "@/types/api";

export type ThinkingLevel = "off" | "minimal" | "low" | "medium" | "high" | "xhigh" | "max";
export type ThinkingRole = "creative" | "project";
export interface ThinkingPreferences { creative: ThinkingLevel; project: ThinkingLevel }
interface ThinkingResponse { ok: boolean; preferences: ThinkingPreferences }
export interface ScenePerformancePreferences { enabled: boolean; max_actor_calls: number }
interface ScenePerformanceResponse { ok: boolean; preferences: ScenePerformancePreferences }
export interface ToneExperimentPreferences {
  enabled: boolean; rule_count: number; rule_source: string; source_commit: string;
  prompt_layer_id: string; audit_directory: string;
}
interface ToneExperimentResponse { ok: boolean; preferences: ToneExperimentPreferences }
export interface PromptLayerSummary {
  layer_id: string; responsibility: string; purpose: string; source: string; version: string;
  digest: string; editable: boolean; default_text: string; effective_text: string; owner: string;
  usage_status: "active" | "formal-route" | "opt-in" | "historical" | "experimental"; flow_stage: string;
}
export interface PromptFlowNode { id: string; label: string; count?: number; layer_id?: string; children?: PromptFlowNode[] }
export interface PromptCatalog { schema: string; layers: PromptLayerSummary[];
  formal_assets: Array<Record<string, unknown>>; flow_tree: PromptFlowNode[] }
export interface PromptHistory { layer_id: string; scope: string; versions: Array<{ version: number; text: string; created_at: string }> }
export interface PromptPreview { schema: string; digest: string; layers: Array<Record<string, unknown>>;
  texts: Record<string, string>; assembled_template: string | null; assembly_kind: string }

export function createSettingsClient(
  transport: ApiTransport = featureTransport,
  bootstrapSession?: () => Promise<void>,
) {
  return {
    bootstrapDesktopSession: () => (bootstrapSession ? bootstrapSession() : bootstrapDesktopSession()),
    bootstrap: () => transport.request<BootstrapSnapshot>("/application/bootstrap"),
    observeBootstrap: (onSnapshot: (snapshot: BootstrapSnapshot) => void) => transport.connect(
      "/application/bootstrap/stream?interval_seconds=1",
      (event, data) => { if (event === "application.bootstrap") onSnapshot(data as unknown as BootstrapSnapshot); },
    ),
    applicationInfo: () => transport.request<Record<string, any>>("/application/info"),
    legalDocuments: <T>() => transport.request<T>("/application/legal"),
    modelCatalog: () => transport.request<ModelCatalog & { ok: boolean }>("/model-connections/pi-worker/catalog"),
    saveProviderCredential: (payload: Record<string, unknown>) => transport.request<any>(
      "/model-connections/pi-worker/credential",
      { method: "PUT", body: JSON.stringify(payload) },
    ),
    selectModel: (model: string, role: string) => transport.request<any>(
      "/model-connections/pi-worker/model",
      { method: "PUT", body: JSON.stringify({ model, role }) },
    ),
    disconnectProvider: (providerId: string) => transport.request(
      `/model-connections/pi-worker/credential/${encodeURIComponent(providerId)}`,
      { method: "DELETE" },
    ),
    thinkingPreferences: () => transport.request<ThinkingResponse>("/model-connections/pi-worker/thinking"),
    saveThinkingPreference: (role: ThinkingRole, level: ThinkingLevel) => transport.request<ThinkingResponse>(
      "/model-connections/pi-worker/thinking",
      { method: "PUT", body: JSON.stringify({ role, level }) },
    ),
    scenePerformancePreferences: () => transport.request<ScenePerformanceResponse>("/model-connections/pi-worker/scene-performance"),
    toneExperimentPreferences: () => transport.request<ToneExperimentResponse>("/experiments/less-ai-tone"),
    saveToneExperimentPreferences: (enabled: boolean) => transport.request<ToneExperimentResponse>(
      "/experiments/less-ai-tone", { method: "PUT", body: JSON.stringify({ enabled }) },
    ),
    saveScenePerformancePreferences: (preferences: ScenePerformancePreferences) => transport.request<ScenePerformanceResponse>(
      "/model-connections/pi-worker/scene-performance",
      { method: "PUT", body: JSON.stringify(preferences) },
    ),
    promptCatalog: (projectRoot = "") => transport.request<PromptCatalog>(
      `/prompts/catalog?project_root=${encodeURIComponent(projectRoot)}`,
    ),
    promptHistory: (layerId: string, scope: "global" | "project", projectRoot = "") => transport.request<PromptHistory>(
      `/prompts/layers/${encodeURIComponent(layerId)}/history?scope=${scope}&project_root=${encodeURIComponent(projectRoot)}`,
    ),
    savePromptLayer: (layerId: string, payload: { scope: "global" | "project"; project_root: string; text: string; expected_digest?: string }) => transport.request(
      `/prompts/layers/${encodeURIComponent(layerId)}`,
      { method: "PUT", body: JSON.stringify(payload) },
    ),
    activatePromptVersion: (layerId: string, payload: { scope: "global" | "project"; project_root: string; version: number; expected_digest?: string }) => transport.request(
      `/prompts/layers/${encodeURIComponent(layerId)}/activate`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
    resetPromptLayer: (layerId: string, payload: { scope: "global" | "project"; project_root: string; expected_digest?: string }) => transport.request(
      `/prompts/layers/${encodeURIComponent(layerId)}/reset`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
    previewPromptLayers: (layerIds: string[], projectRoot = "") => transport.request<PromptPreview>(
      "/prompts/preview", { method: "POST", body: JSON.stringify({ layer_ids: layerIds, project_root: projectRoot }) },
    ),
    exportDiagnostics: () => transport.authorizedFetch("/application/diagnostics/export", { method: "POST" }),
  };
}

export const settingsClient = createSettingsClient();
