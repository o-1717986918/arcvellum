import type { ApiTransport, EventStreamConnection } from "@/services/api";
import { featureTransport } from "@/services/featureTransport";
import type { ScenePromptInspection } from "../scenePromptTypes";
import type {
  ArtifactRevision,
  ArtifactRevisionSummary,
  CreativeLiveEvent,
  CreatorPersonaState,
  CreativeLiveSnapshot,
  CreativeSession,
  SceneRehearsalDetail,
  SceneRehearsalSummary,
  SceneMaterialInspection,
} from "../types";

export function createCreativeLiveClient(transport: ApiTransport = featureTransport) {
  const q = transport.query;
  return {
    prompts: (projectRoot: string, transactionId: string) => transport.request<ScenePromptInspection>(
      `/creative-live/scene-prompts/${encodeURIComponent(transactionId)}?${q({ project_root: projectRoot })}`,
    ),
    persona: (root: string) => transport.request<CreatorPersonaState>(`/creative-live/persona?${q({ project_root: root })}`),
    savePersona: (root: string, version: number, text: string, reason: string) => transport.request<CreatorPersonaState>("/creative-live/persona", {
      method: "PUT", body: JSON.stringify({ project_root: root, expected_version: version, text, reason }),
    }),
    configuration: (root: string) => transport.request<{ revision: number; overrides: Record<string, boolean>; effective: Record<string, boolean> }>(`/creative-live/config?${q({ project_root: root })}`),
    saveConfiguration: (root: string, revision: number, overrides: Record<string, boolean>) => transport.request<{ revision: number; overrides: Record<string, boolean> }>("/creative-live/config", {
      method: "PUT", body: JSON.stringify({ project_root: root, expected_revision: revision, overrides }),
    }),
    snapshot: (projectRoot: string) => transport.request<CreativeLiveSnapshot>(
      `/creative-live?${q({ project_root: projectRoot })}`,
    ),
    observe: (
      projectRoot: string,
      onSnapshot: (snapshot: CreativeLiveSnapshot) => void,
      onEvent: (event: CreativeLiveEvent) => void,
      onError?: (cause: unknown) => void,
    ): EventStreamConnection => transport.connect(
      `/creative-live/stream?${q({ project_root: projectRoot })}`,
      (event, data) => {
        if (event === "creative.snapshot") onSnapshot(data as unknown as CreativeLiveSnapshot);
        if (event === "creative.event") onEvent(data as unknown as CreativeLiveEvent);
      },
      onError,
    ),
    session: (projectRoot: string, sessionId: string) => transport.request<{ session: CreativeSession }>(
      `/creative-live/sessions/${encodeURIComponent(sessionId)}?${q({ project_root: projectRoot })}`,
    ),
    rehearsals: (projectRoot: string) => transport.request<{ scenes: SceneRehearsalSummary[] }>(
      `/creative-live/scene-rehearsals?${q({ project_root: projectRoot })}`,
    ),
    rehearsal: (projectRoot: string, transactionId: string) => transport.request<{ scene: SceneRehearsalDetail }>(
      `/creative-live/scene-rehearsals/${encodeURIComponent(transactionId)}?${q({ project_root: projectRoot })}`,
    ),
    materials: (projectRoot: string, transactionId: string) => transport.request<{ inspection: SceneMaterialInspection }>(
      `/creative-live/scene-materials/${encodeURIComponent(transactionId)}?${q({ project_root: projectRoot })}`,
    ),
    revisions: (projectRoot: string, artifactId: string) => transport.request<{ revisions: ArtifactRevisionSummary[] }>(
      `/creative-live/artifacts/${encodeURIComponent(artifactId)}/revisions?${q({ project_root: projectRoot })}`,
    ),
    revision: (projectRoot: string, artifactId: string, revisionId: string) => transport.request<{ revision: ArtifactRevision }>(
      `/creative-live/artifacts/${encodeURIComponent(artifactId)}/revisions/${encodeURIComponent(revisionId)}?${q({ project_root: projectRoot })}`,
    ),
  };
}

export const creativeLiveClient = createCreativeLiveClient();
