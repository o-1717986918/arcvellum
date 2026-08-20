import type { ApiTransport } from "@/services/api";
import { featureTransport } from "@/services/featureTransport";
import type { NarrativeProjection } from "@/types/api";
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
    projection: (projectRoot: string, level: string, focus: string) => transport.request<NarrativeProjection>(
      `/narrative/projection?${transport.query({ project_root: projectRoot, level, focus })}`,
    ),
    observeProjection: (projectRoot: string, level: string, focus: string, onProjection: (value: NarrativeProjection) => void) => transport.connect(
      `/narrative/stream?${transport.query({ project_root: projectRoot, level, focus, interval_seconds: 2 })}`,
      (event, data) => { if (event === "narrative.projection") onProjection(data as unknown as NarrativeProjection); },
    ),
    spatialProjection: (view: OrreryViewQuery) => transport.request<SpatialNarrativeProjection>(`/narrative/projection/v3?${params(view)}`),
    observeSpatialProjection: (
      view: OrreryViewQuery,
      onProjection: (value: SpatialNarrativeProjection) => void,
      onPatch: (value: SpatialNarrativeProjectionPatch) => void,
      onError?: (cause: unknown) => void,
    ) => transport.connect(
      `/narrative/stream/v3?${params(view)}&interval_seconds=2`,
      (event, data) => {
        if (event === "narrative.v3.patch") onPatch(data as unknown as SpatialNarrativeProjectionPatch);
        if (event === "narrative.v3.projection") onProjection(data as unknown as SpatialNarrativeProjection);
      },
      onError,
    ),
    nodeDetail: (endpoint: string, view: OrreryViewQuery) => transport.request<SpatialNodeDetail>(
      `${endpoint}?${params(view)}`,
    ),
  };
}

export const orreryClient = createOrreryClient();
