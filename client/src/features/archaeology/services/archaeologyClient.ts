import {
  api,
  connectEventStream,
  query,
  type EventStreamConnection,
} from "@/services/api";
import type {
  ArchaeologyCatalog,
  ArchaeologyImportForm,
  ArchaeologyImportResponse,
  ArchaeologyOptions,
  ArchaeologyWorkbench,
  ArchaeologyWorkerJob,
} from "../types";

export function fetchArchaeologyOptions(): Promise<ArchaeologyOptions> {
  return api("/archaeology/options");
}

export function fetchArchaeologyCatalog(
  projectRoot: string,
): Promise<ArchaeologyCatalog> {
  return api(`/archaeology/imports?${query({ project_root: projectRoot })}`);
}

export function fetchArchaeologyWorkbench(
  projectRoot: string,
  workId: string,
): Promise<ArchaeologyWorkbench> {
  return api(
    `/archaeology/workbench/${encodeURIComponent(workId)}?${query({ project_root: projectRoot })}`,
  );
}

export async function importArchaeologySource(
  projectRoot: string,
  file: File,
  form: ArchaeologyImportForm,
): Promise<ArchaeologyImportResponse> {
  const contentBase64 = await fileToBase64(file);
  return api("/archaeology/imports", {
    method: "POST",
    body: JSON.stringify({
      project_root: projectRoot,
      filename: file.name,
      content_base64: contentBase64,
      ...form,
    }),
  });
}

export function runArchaeologyTask(
  projectRoot: string,
): Promise<ArchaeologyWorkerJob> {
  return api("/worker/run", {
    method: "POST",
    body: JSON.stringify({
      project_root: projectRoot,
      route: "source-ingest",
      runtime: "opencode",
    }),
  });
}

export function observeArchaeologyWorker(
  jobId: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  onError: (cause: unknown) => void,
): EventStreamConnection {
  return connectEventStream(
    `/worker/jobs/${encodeURIComponent(jobId)}/stream`,
    onEvent,
    onError,
  );
}

export function approveArchaeologyWriteback(
  jobId: string,
): Promise<ArchaeologyWorkerJob> {
  return workerAction(jobId, "writeback", {
    decision: "approve",
    reason: "用户确认将当前考古候选写回项目候选区。",
  });
}

export function rejectArchaeologyWriteback(
  jobId: string,
): Promise<ArchaeologyWorkerJob> {
  return workerAction(jobId, "writeback", {
    decision: "reject",
    reason: "用户退回当前考古候选，正式项目保持不变。",
  });
}

export function retryArchaeologyWorker(
  jobId: string,
): Promise<ArchaeologyWorkerJob> {
  return workerAction(jobId, "retry", { resume: true });
}

export function stopArchaeologyWorker(
  jobId: string,
): Promise<ArchaeologyWorkerJob> {
  return workerAction(jobId, "stop", {});
}

function workerAction(
  jobId: string,
  action: string,
  body: Record<string, unknown>,
): Promise<ArchaeologyWorkerJob> {
  return api(`/worker/jobs/${encodeURIComponent(jobId)}/${action}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("没有读到这个文件，请重新选择。"));
    reader.onload = () => {
      const value = String(reader.result || "");
      const separator = value.indexOf(",");
      if (separator < 0) {
        reject(new Error("文件内容没有正确编码，请重新选择。"));
        return;
      }
      resolve(value.slice(separator + 1));
    };
    reader.readAsDataURL(file);
  });
}
