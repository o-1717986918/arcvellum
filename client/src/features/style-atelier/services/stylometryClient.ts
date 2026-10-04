import { api, query } from "@/services/api";
import type { CorpusSource, CreatorControls, CreatorMount, FragmentRequest, MetricRow,
  StyloCompiled, StyloJob, StyloMeasurement, StyloProfile, StyloVersion, StyloWorkbench } from "../stylometryTypes";

function post<T>(path: string, payload: unknown): Promise<T> {
  return api(`/stylometry/${path}`, { method: "POST", body: JSON.stringify(payload) });
}
export const stylometryClient = {
  workbench: (root: string) => api<StyloWorkbench>(`/stylometry/workbench?${query({ project_root: root })}`),
  profile: (root: string, id: string) => api<StyloProfile>(`/stylometry/profiles/${encodeURIComponent(id)}?${query({ project_root: root })}`),
  version: (root: string, id: string) => api<StyloVersion>(`/stylometry/versions/${encodeURIComponent(id)}?${query({ project_root: root })}`),
  parameters: (root: string, profileId: string, dependencyJson = "") => post<{ controls: CreatorControls; metrics: MetricRow[] }>(
    "parameters", { project_root: root, profile_id: profileId, dependency_json: dependencyJson }),
  compile: (payload: FragmentRequest) => post<StyloCompiled>("compile", payload),
  save: (payload: FragmentRequest & { fragment_override: string | null }) => post<StyloVersion>("versions", payload),
  mount: (root: string, versionId: string, enabled: boolean, revision: number, combine: string, usage: string) => post<CreatorMount>(
    "mount", { project_root: root, version_id: versionId, enabled, expected_revision: revision, combine, usage }),
  measure: (root: string, text: string, versionId = "", candidateJson = "") => post<StyloMeasurement>(
    "measure", { project_root: root, text, version_id: versionId, candidate_json: candidateJson }),
  launch: (root: string, title: string, sources: CorpusSource[]) => post<StyloJob>("jobs", { project_root: root, title, sources }),
  jobs: (root: string) => api<{ jobs: StyloJob[] }>(`/stylometry/jobs?${query({ project_root: root })}`),
  job: (root: string, id: string) => api<StyloJob>(`/stylometry/jobs/${encodeURIComponent(id)}?${query({ project_root: root })}`),
  jobAction: (root: string, id: string, action: "cancel" | "resume") => post<StyloJob>(`jobs/${encodeURIComponent(id)}/${action}`, { project_root: root }),
};
