import type { ApiTransport } from "@/services/api";
import { featureTransport } from "@/services/featureTransport";
import type { DemoBundleSummary, ProjectSummary, ProjectsResponse } from "@/types/api";

export interface ProjectLocationCheck {
  valid: boolean;
  conflicts: string[];
  warnings?: string[];
}

export function createProjectsClient(transport: ApiTransport = featureTransport) {
  return {
    list: () => transport.request<ProjectsResponse>("/projects"),
    create: (payload: Record<string, unknown>) => transport.request<{ ok: boolean; project: ProjectSummary }>(
      "/projects/create",
      { method: "POST", body: JSON.stringify(payload) },
    ),
    open: (projectRoot: string) => transport.request<{ ok: boolean; project: ProjectSummary }>(
      "/projects/open",
      { method: "POST", body: JSON.stringify({ project_root: projectRoot }) },
    ),
    defaultLocation: () => transport.request<{ projects_root: string }>("/projects/default-location"),
    setDefaultLocation: (projectsRoot: string) => transport.request<{ projects_root: string }>(
      "/projects/default-location",
      { method: "PUT", body: JSON.stringify({ projects_root: projectsRoot }) },
    ),
    validateLocation: (payload: Record<string, unknown>) => transport.request<ProjectLocationCheck>(
      "/projects/validate-location",
      { method: "POST", body: JSON.stringify(payload) },
    ),
    demos: () => transport.request<{ ok: boolean; items: DemoBundleSummary[] }>("/projects/demos"),
    installDemo: (bundleId: string, restoreAs = "") => transport.request<{ ok: boolean; project: ProjectSummary; status: string }>(
      "/projects/demos/install",
      { method: "POST", body: JSON.stringify({ bundle_id: bundleId, restore_as: restoreAs }) },
    ),
    cloneDemo: (payload: { project_root: string; title?: string; folder_name?: string; parent_directory?: string }) =>
      transport.request<{ ok: boolean; project: ProjectSummary }>(
        "/projects/demos/clone",
        { method: "POST", body: JSON.stringify(payload) },
      ),
    addDirection: (projectRoot: string, message: string) => transport.request<Record<string, unknown>>(
      "/projects/directions",
      { method: "POST", body: JSON.stringify({ project_root: projectRoot, message }) },
    ),
  };
}

export const projectsClient = createProjectsClient();
