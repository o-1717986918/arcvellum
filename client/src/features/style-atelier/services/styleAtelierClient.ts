import {
  api,
  connectEventStream,
  query,
  type EventStreamConnection,
} from "@/services/api";
import type {
  StyleAdvancePayload,
  StyleAuthorCreatePayload,
  StyleAtelierWorkbench,
  StyleBuildPayload,
  StyleCompilePayload,
  StyleMountPayload,
  StyleMountPreview,
  StyleMountTransaction,
  StyleSourceCreatePayload,
  StyleTaskLaunch,
  StyleTransactionReceipt,
  StyleVersionDetail,
  StyleWorkerJob,
  StyleWorkCreatePayload,
} from "../types";

export function fetchStyleWorkbench(
  projectRoot: string,
): Promise<StyleAtelierWorkbench> {
  return api(`/style-lab/workbench?${query({ project_root: projectRoot })}`);
}

export function fetchStyleVersionDetail(
  projectRoot: string,
  styleId: string,
  versionId: string,
): Promise<StyleVersionDetail> {
  const suffix = query({ project_root: projectRoot });
  return api(
    `/style-lab/versions/${encodeURIComponent(styleId)}/${encodeURIComponent(versionId)}?${suffix}`,
  );
}

export function createStyleAuthor(
  payload: StyleAuthorCreatePayload,
): Promise<StyleTransactionReceipt> {
  return postStyleTransaction("/style-lab/authors", payload);
}

export function createStyleWork(
  payload: StyleWorkCreatePayload,
): Promise<StyleTransactionReceipt> {
  return postStyleTransaction("/style-lab/works", payload);
}

export function importStyleSource(
  payload: StyleSourceCreatePayload,
): Promise<StyleTransactionReceipt> {
  return postStyleTransaction("/style-lab/sources", payload);
}

function postStyleTransaction(
  path: string,
  payload: StyleAuthorCreatePayload | StyleWorkCreatePayload | StyleSourceCreatePayload,
): Promise<StyleTransactionReceipt> {
  return api(path, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function compileStyleProfile(
  payload: StyleCompilePayload,
): Promise<StyleTaskLaunch> {
  return postStyleTask("/style-lab/compile", payload);
}

export function advanceStyleProfile(
  payload: StyleAdvancePayload,
): Promise<StyleTaskLaunch> {
  return postStyleTask("/style-lab/advance", payload);
}

export function buildStyleProfile(
  payload: StyleBuildPayload,
): Promise<StyleTaskLaunch> {
  return postStyleTask("/style-lab/build", payload);
}

export function approveStyleWriteback(jobId: string): Promise<StyleWorkerJob> {
  return api(`/worker/jobs/${encodeURIComponent(jobId)}/writeback`, {
    method: "POST",
    body: JSON.stringify({ decision: "approve", reason: "" }),
  });
}

export function rejectStyleWriteback(jobId: string, reason: string): Promise<StyleWorkerJob> {
  return api(`/worker/jobs/${encodeURIComponent(jobId)}/writeback`, {
    method: "POST",
    body: JSON.stringify({ decision: "reject", reason }),
  });
}

export function retryStyleWorker(jobId: string): Promise<StyleWorkerJob> {
  return api(`/worker/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: "POST",
    body: JSON.stringify({ runtime: "", resume: true }),
  });
}

export function stopStyleWorker(jobId: string): Promise<StyleWorkerJob> {
  return api(`/worker/jobs/${encodeURIComponent(jobId)}/stop`, { method: "POST" });
}

export function previewStyleMount(
  payload: StyleMountPayload,
): Promise<StyleMountPreview> {
  return api("/style-lab/mount-preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function mountStyleVersion(
  payload: StyleMountPayload,
): Promise<StyleMountTransaction> {
  return api("/style-lab/mount", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function observeStyleWorker(
  jobId: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  onError?: (cause: unknown) => void,
): EventStreamConnection {
  return connectEventStream(
    `/worker/jobs/${encodeURIComponent(jobId)}/stream`,
    onEvent,
    onError,
  );
}

function postStyleTask(
  path: string,
  payload: StyleCompilePayload | StyleAdvancePayload | StyleBuildPayload,
): Promise<StyleTaskLaunch> {
  return api(path, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
