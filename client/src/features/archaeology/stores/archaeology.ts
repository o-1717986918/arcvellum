import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import type { EventStreamConnection } from "@/services/api";
import { friendlyError, useAppStore } from "@/stores/app";
import {
  approveArchaeologyWriteback,
  fetchArchaeologyCatalog,
  fetchArchaeologyOptions,
  fetchArchaeologyWorkbench,
  importArchaeologySource,
  observeArchaeologyWorker,
  rejectArchaeologyWriteback,
  retryArchaeologyWorker,
  runArchaeologyTask,
  stopArchaeologyWorker,
} from "../services/archaeologyClient";
import type {
  ArchaeologyCatalog,
  ArchaeologyImportForm,
  ArchaeologyOptions,
  ArchaeologyWorkbench,
  ArchaeologyWorkerEvent,
  ArchaeologyWorkerJob,
} from "../types";

export const useArchaeologyStore = defineStore("archaeology", () => {
  const app = useAppStore();
  const options = shallowRef<ArchaeologyOptions | null>(null);
  const catalog = shallowRef<ArchaeologyCatalog | null>(null);
  const workbench = shallowRef<ArchaeologyWorkbench | null>(null);
  const selectedWorkId = ref("");
  const loadedProjectRoot = ref("");
  const busy = ref(false);
  const importing = ref(false);
  const workerBusy = ref(false);
  const error = ref("");
  const notice = ref("");
  const job = shallowRef<ArchaeologyWorkerJob | null>(null);
  const events = ref<ArchaeologyWorkerEvent[]>([]);
  const streamError = ref("");
  let stream: EventStreamConnection | null = null;
  let finalizedJobKey = "";

  const projectRoot = computed(() => app.currentProjectPath);
  const imports = computed(() => catalog.value?.imports || []);
  const selectedImport = computed(
    () => imports.value.find((item) => item.work_id === selectedWorkId.value) || imports.value[0] || null,
  );
  const routeReady = computed(() => workbench.value?.status.status === "ready");
  const activeJob = computed(() => isActiveJobStatus(job.value?.status || ""));

  async function load(): Promise<void> {
    stopStream();
    if (!projectRoot.value) {
      reset();
      return;
    }
    busy.value = true;
    error.value = "";
    try {
      if (loadedProjectRoot.value && loadedProjectRoot.value !== projectRoot.value) resetSelections();
      loadedProjectRoot.value = projectRoot.value;
      const [nextOptions, nextCatalog] = await Promise.all([
        options.value ? Promise.resolve(options.value) : fetchArchaeologyOptions(),
        fetchArchaeologyCatalog(projectRoot.value),
      ]);
      options.value = nextOptions;
      catalog.value = nextCatalog;
      stabilizeSelection();
      await loadSelectedWorkbench();
    } catch (cause) {
      error.value = friendlyError(cause, "作品考古工作台暂时没有读取成功。");
    } finally {
      busy.value = false;
    }
  }

  async function refresh(): Promise<void> {
    if (!projectRoot.value) return;
    catalog.value = await fetchArchaeologyCatalog(projectRoot.value);
    stabilizeSelection();
    await loadSelectedWorkbench();
  }

  async function selectWork(workId: string): Promise<void> {
    selectedWorkId.value = workId;
    await loadSelectedWorkbench();
  }

  async function importSource(file: File, form: ArchaeologyImportForm): Promise<void> {
    if (!projectRoot.value) return;
    importing.value = true;
    error.value = "";
    notice.value = "";
    try {
      const result = await importArchaeologySource(projectRoot.value, file, form);
      selectedWorkId.value = result.receipt.work_id;
      workbench.value = result.workbench;
      catalog.value = await fetchArchaeologyCatalog(projectRoot.value);
      notice.value = `《${result.workbench.title}》已经安全导入，可以开始逐层整理。`;
    } catch (cause) {
      error.value = friendlyError(cause, "这份作品没有成功导入。");
      throw cause;
    } finally {
      importing.value = false;
    }
  }

  async function runNextTask(): Promise<void> {
    if (!projectRoot.value || workerBusy.value || routeReady.value) return;
    workerBusy.value = true;
    error.value = "";
    notice.value = "";
    try {
      follow(await runArchaeologyTask(projectRoot.value));
    } catch (cause) {
      error.value = friendlyError(cause, "当前整理任务没有成功启动。");
    } finally {
      workerBusy.value = false;
    }
  }

  async function approveWriteback(): Promise<void> {
    await runWorkerAction(
      async (jobId) => finalize(await approveArchaeologyWriteback(jobId)),
      "候选成果没有写回项目。",
    );
  }

  async function rejectWriteback(): Promise<void> {
    await runWorkerAction(
      async (jobId) => finalize(await rejectArchaeologyWriteback(jobId)),
      "候选成果没有成功退回。",
    );
  }

  async function retry(): Promise<void> {
    await runWorkerAction(
      async (jobId) => follow(await retryArchaeologyWorker(jobId)),
      "当前任务没有成功重试。",
    );
  }

  async function stop(): Promise<void> {
    await runWorkerAction(
      async (jobId) => {
        job.value = await stopArchaeologyWorker(jobId);
      },
      "当前任务没有成功停止。",
    );
  }

  function follow(nextJob: ArchaeologyWorkerJob): void {
    stopStream();
    finalizedJobKey = "";
    job.value = nextJob;
    events.value = [];
    streamError.value = "";
    if (!isActiveJobStatus(nextJob.status)) {
      void finalize(nextJob);
      return;
    }
    stream = observeArchaeologyWorker(
      nextJob.job_id,
      handleWorkerEvent,
      (cause) => {
        streamError.value = friendlyError(cause, "实时连接暂时中断，系统会自动重连。");
      },
    );
  }

  function handleWorkerEvent(event: string, data: Record<string, unknown>): void {
    if (event === "worker") {
      const nextJob = data as unknown as ArchaeologyWorkerJob;
      job.value = nextJob;
      if (!isActiveJobStatus(nextJob.status)) void finalize(nextJob);
      return;
    }
    const envelope = data as Partial<ArchaeologyWorkerEvent>;
    const eventData = envelope.data && typeof envelope.data === "object"
      ? envelope.data
      : data;
    events.value = [
      ...events.value.slice(-9),
      {
        sequence: Number(envelope.sequence || 0),
        event: String(envelope.event || event),
        at: String(envelope.at || new Date().toISOString()),
        data: eventData as Record<string, unknown>,
      },
    ];
  }

  async function finalize(nextJob: ArchaeologyWorkerJob): Promise<void> {
    const key = `${nextJob.job_id}:${nextJob.revision || 0}:${nextJob.status}`;
    if (finalizedJobKey === key) return;
    finalizedJobKey = key;
    stopStream();
    job.value = nextJob;
    if (nextJob.status === "complete") notice.value = "本层整理已经通过，可以继续下一层。";
    if (nextJob.status === "route_ready") notice.value = "这部作品已经完成考古整理。";
    try {
      await refresh();
      await app.loadAgentObservability();
    } catch (cause) {
      streamError.value = friendlyError(cause, "任务已结束，但工作台还没有同步到最新状态。");
    }
  }

  async function runWorkerAction(
    action: (jobId: string) => Promise<void>,
    fallback: string,
  ): Promise<void> {
    const jobId = job.value?.job_id;
    if (!jobId || workerBusy.value) return;
    workerBusy.value = true;
    try {
      await action(jobId);
    } catch (cause) {
      error.value = friendlyError(cause, fallback);
    } finally {
      workerBusy.value = false;
    }
  }

  async function loadSelectedWorkbench(): Promise<void> {
    if (!projectRoot.value || !selectedWorkId.value) {
      workbench.value = null;
      return;
    }
    workbench.value = await fetchArchaeologyWorkbench(
      projectRoot.value,
      selectedWorkId.value,
    );
  }

  function stabilizeSelection(): void {
    if (!imports.value.some((item) => item.work_id === selectedWorkId.value)) {
      selectedWorkId.value = imports.value[0]?.work_id || "";
    }
  }

  function resetSelections(): void {
    selectedWorkId.value = "";
    workbench.value = null;
    job.value = null;
    events.value = [];
    finalizedJobKey = "";
  }

  function reset(): void {
    stopStream();
    options.value = null;
    catalog.value = null;
    loadedProjectRoot.value = "";
    error.value = "";
    notice.value = "";
    streamError.value = "";
    resetSelections();
  }

  function stopStream(): void {
    stream?.close();
    stream = null;
  }

  return {
    options,
    catalog,
    workbench,
    selectedWorkId,
    busy,
    importing,
    workerBusy,
    error,
    notice,
    job,
    events,
    streamError,
    projectRoot,
    imports,
    selectedImport,
    routeReady,
    activeJob,
    load,
    refresh,
    selectWork,
    importSource,
    runNextTask,
    approveWriteback,
    rejectWriteback,
    retry,
    stop,
    reset,
  };
});

function isActiveJobStatus(status: string): boolean {
  return ["queued", "running", "stopping"].includes(status);
}
