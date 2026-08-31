import type { ApiTransport, EventStreamConnection } from "@/services/api";
import { featureTransport } from "@/services/featureTransport";
import type {
  ArtifactRevision,
  ArtifactRevisionSummary,
  CreativeLiveEvent,
  CreativeLiveSnapshot,
  CreativeSession,
} from "../types";

export function createCreativeLiveClient(transport: ApiTransport = featureTransport) {
  const q = transport.query;
  return {
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
    revisions: (projectRoot: string, artifactId: string) => transport.request<{ revisions: ArtifactRevisionSummary[] }>(
      `/creative-live/artifacts/${encodeURIComponent(artifactId)}/revisions?${q({ project_root: projectRoot })}`,
    ),
    revision: (projectRoot: string, artifactId: string, revisionId: string) => transport.request<{ revision: ArtifactRevision }>(
      `/creative-live/artifacts/${encodeURIComponent(artifactId)}/revisions/${encodeURIComponent(revisionId)}?${q({ project_root: projectRoot })}`,
    ),
  };
}

export const creativeLiveClient = createCreativeLiveClient();
