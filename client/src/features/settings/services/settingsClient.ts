import { bootstrapDesktopSession, type ApiTransport } from "@/services/api";
import { featureTransport } from "@/services/featureTransport";
import type { BootstrapSnapshot, ModelCatalog } from "@/types/api";

export type ThinkingLevel = "off" | "minimal" | "low" | "medium" | "high" | "xhigh" | "max";
export type ThinkingRole = "creative" | "project";
export interface ThinkingPreferences { creative: ThinkingLevel; project: ThinkingLevel }
interface ThinkingResponse { ok: boolean; preferences: ThinkingPreferences }
export interface ScenePerformancePreferences { enabled: boolean; max_actor_calls: number }
interface ScenePerformanceResponse { ok: boolean; preferences: ScenePerformancePreferences }

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
    saveScenePerformancePreferences: (preferences: ScenePerformancePreferences) => transport.request<ScenePerformanceResponse>(
      "/model-connections/pi-worker/scene-performance",
      { method: "PUT", body: JSON.stringify(preferences) },
    ),
    exportDiagnostics: () => transport.authorizedFetch("/application/diagnostics/export", { method: "POST" }),
  };
}

export const settingsClient = createSettingsClient();
