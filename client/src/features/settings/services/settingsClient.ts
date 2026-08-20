import { bootstrapDesktopSession, type ApiTransport } from "@/services/api";
import { featureTransport } from "@/services/featureTransport";
import type { BootstrapSnapshot, ModelCatalog } from "@/types/api";

export interface PiModel {
  qualified_id: string;
  name: string;
}

export interface PiProvider {
  id: string;
  name: string;
  connected: boolean;
  models?: PiModel[];
}

export interface PiCatalog extends Record<string, unknown> {
  providers: PiProvider[];
  selected_model: string;
  selected_models?: Record<string, string>;
}

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
    modelCatalog: () => transport.request<ModelCatalog & { ok: boolean }>("/model-connections/opencode/catalog"),
    saveProviderCredential: (payload: Record<string, unknown>) => transport.request<any>(
      "/model-connections/opencode/credential",
      { method: "PUT", body: JSON.stringify(payload) },
    ),
    saveCustomProvider: (payload: Record<string, unknown>) => transport.request<any>(
      "/model-connections/opencode/custom",
      { method: "PUT", body: JSON.stringify(payload) },
    ),
    selectModel: (model: string, role: string) => transport.request<any>(
      "/model-connections/opencode/model",
      { method: "PUT", body: JSON.stringify({ model, role }) },
    ),
    disconnectProvider: (providerId: string) => transport.request(
      `/model-connections/opencode/credential/${encodeURIComponent(providerId)}`,
      { method: "DELETE" },
    ),
    exportDiagnostics: () => transport.authorizedFetch("/application/diagnostics/export", { method: "POST" }),
    piCatalog: () => transport.request<PiCatalog>("/model-connections/pi-worker/catalog"),
    savePiCredential: (payload: Record<string, unknown>) => transport.request<PiCatalog>(
      "/model-connections/pi-worker/credential",
      { method: "PUT", body: JSON.stringify(payload) },
    ),
    selectPiModel: (payload: Record<string, unknown>) => transport.request<PiCatalog>(
      "/model-connections/pi-worker/model",
      { method: "PUT", body: JSON.stringify(payload) },
    ),
    disconnectPiProvider: (providerId: string) => transport.request<PiCatalog>(
      `/model-connections/pi-worker/credential/${encodeURIComponent(providerId)}`,
      { method: "DELETE" },
    ),
  };
}

export const settingsClient = createSettingsClient();
