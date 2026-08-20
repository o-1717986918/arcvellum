import type { ApiTransport } from "@/services/api";
import { featureTransport } from "@/services/featureTransport";
import type {
  DeliveryResponse,
  LibraryResponse,
  ProjectProgress,
  ReaderManifest,
  ReaderUnitResponse,
} from "@/types/api";

export interface ReaderState {
  position: { unit_id: string; scroll_ratio: number };
  bookmarks: Array<{ unit_id: string }>;
}

export function createDeliveryClient(transport: ApiTransport = featureTransport) {
  const q = transport.query;
  return {
    library: (projectRoot: string) => transport.request<LibraryResponse>(`/project/library?${q({ project_root: projectRoot })}`),
    delivery: (projectRoot: string) => transport.request<DeliveryResponse>(`/project/delivery?${q({ project_root: projectRoot })}`),
    readerManifest: (projectRoot: string) => transport.request<ReaderManifest>(`/reader/manifest?${q({ project_root: projectRoot })}`),
    progress: (projectRoot: string) => transport.request<ProjectProgress>(`/project/progress?${q({ project_root: projectRoot })}`),
    readerUnit: (projectRoot: string, unitId: string) => transport.request<ReaderUnitResponse>(
      `/reader/units/${encodeURIComponent(unitId)}?${q({ project_root: projectRoot })}`,
    ),
    readerState: (projectRoot: string) => transport.request<ReaderState>(`/reader/state?${q({ project_root: projectRoot })}`),
    saveReaderPosition: (projectRoot: string, unitId: string, scrollRatio: number) => transport.request(
      "/reader/position",
      { method: "PUT", body: JSON.stringify({ project_root: projectRoot, unit_id: unitId, scroll_ratio: scrollRatio }) },
    ),
    setBookmark: (projectRoot: string, unitId: string, enabled: boolean) => transport.request(
      "/reader/bookmark",
      { method: "PUT", body: JSON.stringify({ project_root: projectRoot, unit_id: unitId, enabled }) },
    ),
    search: (projectRoot: string, text: string) => transport.request<{ items: Record<string, unknown>[] }>(
      `/reader/search?${q({ project_root: projectRoot, q: text })}`,
    ),
    downloadUrl: (projectRoot: string, path: string) => `/project/delivery/download?${q({ project_root: projectRoot, path })}`,
    download: (projectRoot: string, path: string) => transport.authorizedFetch(
      `/project/delivery/download?${q({ project_root: projectRoot, path })}`,
    ),
  };
}

export const deliveryClient = createDeliveryClient();
