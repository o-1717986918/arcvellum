import type { ApiTransport } from "@/services/api";
import { featureTransport } from "@/services/featureTransport";
import type { AdvisorAnswer, AdvisorSession } from "@/types/api";

export interface AdvisorInboxSettings {
  mode: string;
  quiet_start: string;
  quiet_end: string;
}

export interface AdvisorSurface {
  personas: { selected_persona: string; items: Record<string, unknown>[] };
  inbox: {
    items: Record<string, unknown>[];
    unread_count: number;
    notification_count?: number;
    settings?: AdvisorInboxSettings;
  };
}

export function createAdvisorClient(transport: ApiTransport = featureTransport) {
  const q = transport.query;
  return {
    async surface(projectRoot: string): Promise<AdvisorSurface> {
      const [personas, inbox] = await Promise.all([
        transport.request<AdvisorSurface["personas"]>(`/advisor/personas?${q({ project_root: projectRoot })}`),
        transport.request<AdvisorSurface["inbox"]>(`/advisor/inbox?${q({ project_root: projectRoot })}`),
      ]);
      return { personas, inbox };
    },
    observeInbox: (projectRoot: string, onInbox: (value: AdvisorSurface["inbox"]) => void) => transport.connect(
      `/advisor/inbox/stream?${q({ project_root: projectRoot, interval_seconds: 8 })}`,
      (event, data) => { if (event === "advisor.inbox") onInbox(data as unknown as AdvisorSurface["inbox"]); },
    ),
    selectPersona: (projectRoot: string, personaId: string) => transport.request<AdvisorSurface["personas"]>(
      "/advisor/personas/selection",
      { method: "PUT", body: JSON.stringify({ project_root: projectRoot, persona_id: personaId }) },
    ),
    saveCustomPersona: (payload: Record<string, unknown>) => transport.request<{ persona: Record<string, unknown> }>(
      "/advisor/personas/custom",
      { method: "PUT", body: JSON.stringify(payload) },
    ),
    saveInboxSettings: (projectRoot: string, settings: AdvisorInboxSettings) => transport.request<{ settings: AdvisorInboxSettings }>(
      "/advisor/inbox/settings",
      { method: "PUT", body: JSON.stringify({ project_root: projectRoot, ...settings }) },
    ),
    markNotice: (itemId: string) => transport.request(
      `/advisor/inbox/${encodeURIComponent(itemId)}`,
      { method: "PATCH", body: JSON.stringify({ read: true }) },
    ),
    sessions: (projectRoot: string) => transport.request<{ items: Array<Pick<AdvisorSession, "session_id">> }>(
      `/advisor/sessions?${q({ project_root: projectRoot })}`,
    ),
    session: (sessionId: string) => transport.request<AdvisorSession>(`/advisor/sessions/${encodeURIComponent(sessionId)}`),
    createSession: (projectRoot: string, title: string) => transport.request<AdvisorSession>(
      "/advisor/sessions",
      { method: "POST", body: JSON.stringify({ project_root: projectRoot, title }) },
    ),
    ask: (
      sessionId: string,
      question: string,
      context: Record<string, unknown>,
      signal: AbortSignal,
      onEvent: (event: string, data: Record<string, unknown>) => void,
    ) => transport.stream(
      `/advisor/sessions/${encodeURIComponent(sessionId)}/ask/stream`,
      { method: "POST", signal, body: JSON.stringify({ question, timeout: 240, context }) },
      onEvent,
    ),
  };
}

export type AdvisorStreamAnswer = AdvisorAnswer;
export type AdvisorClient = ReturnType<typeof createAdvisorClient>;
export const advisorClient = createAdvisorClient();
