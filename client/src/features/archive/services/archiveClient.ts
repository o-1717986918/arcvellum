import { api, query } from "@/services/api";
import type {
  ArchiveAssetDetail,
  ArchiveAssetGroup,
  ArchiveCandidate,
  ArchiveCreationOption,
  ArchiveCreationPayload,
  ArchiveCreationPreview,
  ArchiveHistory,
  ArchiveRecord,
  ArchiveStructuredDocument,
  RecycleEntry,
} from "../types";

export interface ArchiveWorkspacePayload {
  groups: ArchiveAssetGroup[];
  candidates: ArchiveCandidate[];
  recycleEntries: RecycleEntry[];
  creationOptions: ArchiveCreationOption[];
}

export async function fetchArchiveWorkspace(
  projectRoot: string,
): Promise<ArchiveWorkspacePayload> {
  const suffix = query({ project_root: projectRoot });
  const [tree, candidateList, recycle, creation] = await Promise.all([
    api<{ groups?: ArchiveAssetGroup[]; items?: ArchiveRecord[] }>(
      `/archive/tree?${suffix}`,
    ),
    api<{ items?: ArchiveCandidate[] }>(`/archive/candidates?${suffix}`),
    api<{ items?: RecycleEntry[] }>(`/archive/recycle-bin?${suffix}`),
    api<{ items?: ArchiveCreationOption[] }>(
      `/archive/creation/options?${suffix}`,
    ),
  ]);
  return {
    groups: tree.groups || [],
    candidates: candidateList.items || [],
    recycleEntries: recycle.items || [],
    creationOptions: creation.items || [],
  };
}

export async function fetchArchiveAsset(
  projectRoot: string,
  assetId: string,
): Promise<{ asset: ArchiveAssetDetail; history: ArchiveHistory }> {
  const encoded = encodeURIComponent(assetId);
  const suffix = query({ project_root: projectRoot });
  const [detail, history] = await Promise.all([
    api<{ asset: ArchiveAssetDetail }>(`/archive/assets/${encoded}?${suffix}`),
    api<ArchiveHistory>(`/archive/assets/${encoded}/history?${suffix}`),
  ]);
  return { asset: detail.asset, history };
}

export function fetchArchiveCandidate(
  projectRoot: string,
  candidateId: string,
): Promise<{ candidate: ArchiveCandidate }> {
  return api(
    `/archive/candidates/${encodeURIComponent(candidateId)}?${query({ project_root: projectRoot })}`,
  );
}

export async function previewArchiveEdit(
  projectRoot: string,
  assetId: string,
  content: string,
): Promise<{
  validation: Record<string, unknown>;
  impact: Record<string, unknown>;
}> {
  const endpoint = `/archive/assets/${encodeURIComponent(assetId)}`;
  const body = JSON.stringify({ project_root: projectRoot, content });
  const [validation, impact] = await Promise.all([
    api<{ validation: Record<string, unknown> }>(`${endpoint}/validate`, {
      method: "POST",
      body,
    }),
    api<{ impact: Record<string, unknown> }>(`${endpoint}/impact`, {
      method: "POST",
      body,
    }),
  ]);
  return { validation: validation.validation, impact: impact.impact };
}

export function commitArchiveEdit(
  projectRoot: string,
  assetId: string,
  payload: {
    baseRevision: string;
    content: string;
    reason: string;
    expectedImpacts: string[];
  },
): Promise<{ receipt: Record<string, unknown> }> {
  return api(`/archive/assets/${encodeURIComponent(assetId)}/commit`, {
    method: "POST",
    body: JSON.stringify({
      project_root: projectRoot,
      base_revision: payload.baseRevision,
      content: payload.content,
      semantic_review: "waived",
      reason: payload.reason,
      expected_impacts: payload.expectedImpacts,
    }),
  });
}

export function previewArchiveCreation(
  projectRoot: string,
  payload: ArchiveCreationPayload,
): Promise<{ preview: ArchiveCreationPreview }> {
  return api("/archive/creation/preview", {
    method: "POST",
    body: JSON.stringify({ project_root: projectRoot, ...payload }),
  });
}

export function commitArchiveCreation(
  projectRoot: string,
  payload: ArchiveCreationPayload,
  previewDigest: string,
): Promise<{ asset_id: string; receipt: ArchiveRecord }> {
  return api("/archive/creation/commit", {
    method: "POST",
    body: JSON.stringify({
      project_root: projectRoot,
      ...payload,
      preview_digest: previewDigest,
    }),
  });
}

export function fetchStructuredDocument(
  projectRoot: string,
  assetId: string,
  content: string,
): Promise<ArchiveStructuredDocument> {
  return api<ArchiveStructuredDocument>(
    `/archive/assets/${encodeURIComponent(assetId)}/structure`,
    {
      method: "POST",
      body: JSON.stringify({ project_root: projectRoot, content }),
    },
  );
}

export function renderStructuredDocument(
  projectRoot: string,
  assetId: string,
  content: string,
  sourceRevision: string,
  fields: Record<string, unknown>,
): Promise<{
  content: string;
  validation: Record<string, unknown>;
  structure: ArchiveStructuredDocument;
}> {
  return api(`/archive/assets/${encodeURIComponent(assetId)}/render-structured`, {
    method: "POST",
    body: JSON.stringify({
      project_root: projectRoot,
      content,
      source_revision: sourceRevision,
      fields,
    }),
  });
}

export async function refreshArchiveMutation(
  projectRoot: string,
  assetId: string,
): Promise<{ history: ArchiveHistory; groups: ArchiveAssetGroup[] }> {
  const suffix = query({ project_root: projectRoot });
  const encoded = encodeURIComponent(assetId);
  const [history, tree] = await Promise.all([
    api<ArchiveHistory>(`/archive/assets/${encoded}/history?${suffix}`),
    api<{ groups?: ArchiveAssetGroup[] }>(`/archive/tree?${suffix}`),
  ]);
  return { history, groups: tree.groups || [] };
}
