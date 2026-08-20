import type { ApiTransport } from "@/services/api";
import { featureTransport } from "@/services/featureTransport";
import type { QualityProfile } from "../types";

export function createQualityClient(transport: ApiTransport = featureTransport) {
  return {
    profile: (projectRoot: string) => transport.request<{ profile: QualityProfile }>(
      `/project/creative-quality?${transport.query({ project_root: projectRoot })}`,
    ),
    preview: (projectRoot: string, text: string, profile: QualityProfile, scope: string) => transport.request<Record<string, unknown>>(
      "/project/creative-quality/preview",
      { method: "POST", body: JSON.stringify({ project_root: projectRoot, text, profile, scope }) },
    ),
    saveProfile: (projectRoot: string, profile: QualityProfile) => transport.request<{ profile: QualityProfile }>(
      "/project/creative-quality",
      { method: "PUT", body: JSON.stringify({ project_root: projectRoot, profile }) },
    ),
    rhythmPlan: <T>(projectRoot: string) => transport.request<{ plan: T }>(
      `/project/rhythm-plan?${transport.query({ project_root: projectRoot })}`,
    ),
    saveRhythmPlan: <T>(projectRoot: string, entries: unknown[], bookProfile: unknown) => transport.request<{ plan: T }>(
      "/project/rhythm-plan",
      { method: "PUT", body: JSON.stringify({ project_root: projectRoot, entries, book_profile: bookProfile }) },
    ),
  };
}

export const qualityClient = createQualityClient();
