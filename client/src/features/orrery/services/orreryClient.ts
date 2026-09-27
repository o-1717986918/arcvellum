import type { ApiTransport } from "@/services/api";
import { featureTransport } from "@/services/featureTransport";
import type { SpatialNarrativeProjection, SpatialNarrativeProjectionPatch, SpatialNodeDetail } from "@/types/spatial";

export interface OrreryViewQuery {
  projectRoot: string;
  level?: string;
  focus?: string;
  grammar?: string;
}

export function createOrreryClient(transport: ApiTransport = featureTransport) {
  const params = (view: OrreryViewQuery) => transport.query({
    project_root: view.projectRoot,
    level: view.level,
    focus: view.focus,
    grammar: view.grammar,
  });
  return {
    spatialProjection: (view: OrreryViewQuery) => transport.request<SpatialNarrativeProjection>(`/narrative/projection/v4?${params(view)}`),
    observeSpatialProjection: (
      view: OrreryViewQuery,
      onProjection: (value: SpatialNarrativeProjection) => void,
      onPatch: (value: SpatialNarrativeProjectionPatch) => void,
      onError?: (cause: unknown) => void,
    ) => transport.connect(
      `/narrative/stream/v4?${params(view)}&interval_seconds=2`,
      (event, data) => {
        if (event === "narrative.v4.patch") onPatch(data as unknown as SpatialNarrativeProjectionPatch);
        if (event === "narrative.v4.projection") onProjection(data as unknown as SpatialNarrativeProjection);
      },
      onError,
    ),
    nodeDetail: (endpoint: string, view: OrreryViewQuery) => transport.request<SpatialNodeDetail>(
      `${endpoint}?${params(view)}`,
    ),
  };
}

export const orreryClient = createOrreryClient();
