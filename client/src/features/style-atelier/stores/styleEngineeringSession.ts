import { ref, shallowRef } from "vue";
import type { EventStreamConnection } from "@/services/api";
import {
  approveStyleWriteback,
  observeStyleWorker,
  rejectStyleWriteback,
  retryStyleWorker,
  stopStyleWorker,
} from "../services/styleAtelierClient";
import type {
  StyleTaskDescriptor,
  StyleTaskLaunch,
  StyleWorkerEvent,
  StyleWorkerJob,
} from "../types";

interface StyleEngineeringSessionOptions {
  refreshWorkbench: () => Promise<void>;
  refreshObservability: () => Promise<void>;
  setError: (message: string) => void;
  setNotice: (message: string) => void;
}

export function useStyleEngineeringSession(options: StyleEngineeringSessionOptions) {
  const busy = ref(false);
  const job = shallowRef<StyleWorkerJob | null>(null);
  const task = shallowRef<StyleTaskDescriptor | null>(null);
  const events = ref<StyleWorkerEvent[]>([]);
  const streamError = ref("");
  const authorId = ref("");
  const profileId = ref("");
  let stream: EventStreamConnection | null = null;
  let finalizedJobKey = "";

  async function launch(operation: () => Promise<StyleTaskLaunch>): Promise<void> {
    busy.value = true;
    streamError.value = "";
    options.setError("");
    options.setNotice("");
    try {
      const result = await operation();
      task.value = result.task || null;
      if (!result.job) {
        job.value = null;
        options.setNotice(result.status === "ready"
          ? "这份文风已经完成全部正式工程步骤。"
          : "当前文风任务没有产生可执行工作。");
        await options.refreshWorkbench();
        return;
      }
      follow(result.job);
    } catch (cause) {
      options.setError(messageFor(cause, "文风工程任务没有成功启动。"));
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  function follow(nextJob: StyleWorkerJob): void {
    dispose();
    finalizedJobKey = "";
    job.value = nextJob;
    events.value = [];
    streamError.value = "";
    if (!isActiveJobStatus(nextJob.status)) {
      void finalize(nextJob);
      return;
    }
    stream = observeStyleWorker(
      nextJob.job_id,
      handleEvent,
      (cause) => {
        streamError.value = messageFor(cause, "文风任务的实时连接暂时中断，系统会自动重连。");
      },
    );
  }

  function handleEvent(event: string, data: Record<string, unknown>): void {
    if (event === "worker") {
      const nextJob = data as unknown as StyleWorkerJob;
      job.value = nextJob;
      if (!isActiveJobStatus(nextJob.status)) void finalize(nextJob);
      return;
    }
    const envelope = data as unknown as Partial<StyleWorkerEvent>;
    const payload = envelope.data && typeof envelope.data === "object"
      ? envelope.data
      : data;
    events.value = [
      ...events.value.slice(-11),
      {
        sequence: Number(envelope.sequence || 0),
        event: String(envelope.event || event),
        at: String(envelope.at || new Date().toISOString()),
        data: payload as Record<string, unknown>,
      },
    ];
  }

  async function finalize(nextJob: StyleWorkerJob): Promise<void> {
    const finalizationKey = `${nextJob.job_id}:${nextJob.revision || 0}:${nextJob.status}`;
    if (finalizedJobKey === finalizationKey) return;
    finalizedJobKey = finalizationKey;
    dispose();
    job.value = nextJob;
    if (nextJob.status === "complete" || nextJob.status === "route_ready") {
      options.setNotice(nextJob.status === "route_ready"
        ? "这份文风已经完成全部正式工程步骤。"
        : "当前文风步骤已通过，工作台已经更新。");
    }
    try {
      await options.refreshWorkbench();
      await options.refreshObservability();
    } catch (cause) {
      streamError.value = messageFor(cause, "任务已结束，但工作台状态暂时没有刷新成功。");
    }
  }

  async function approveWriteback(): Promise<void> {
    const jobId = job.value?.job_id;
    if (!jobId) return;
    await runAction(
      async () => {
        const nextJob = await approveStyleWriteback(jobId);
        job.value = nextJob;
        await finalize(nextJob);
      },
      "候选成果没有写回正式文风工程。",
    );
  }

  async function rejectWriteback(reason: string): Promise<void> {
    const jobId = job.value?.job_id;
    if (!jobId) return;
    await runAction(
      async () => {
        const nextJob = await rejectStyleWriteback(jobId, reason);
        job.value = nextJob;
        await finalize(nextJob);
      },
      "暂时无法退回这份候选成果。",
    );
  }

  async function retry(): Promise<void> {
    const jobId = job.value?.job_id;
    if (!jobId) return;
    await runAction(
      async () => follow(await retryStyleWorker(jobId)),
      "文风任务没有成功重试。",
    );
  }

  async function stop(): Promise<void> {
    const jobId = job.value?.job_id;
    if (!jobId) return;
    await runAction(
      async () => {
        job.value = await stopStyleWorker(jobId);
      },
      "文风任务没有成功停止。",
    );
  }

  async function runAction(action: () => Promise<void>, fallback: string): Promise<void> {
    busy.value = true;
    try {
      await action();
    } catch (cause) {
      options.setError(messageFor(cause, fallback));
    } finally {
      busy.value = false;
    }
  }

  function dispose(): void {
    stream?.close();
    stream = null;
  }

  function reset(): void {
    dispose();
    job.value = null;
    task.value = null;
    events.value = [];
    streamError.value = "";
    authorId.value = "";
    profileId.value = "";
    finalizedJobKey = "";
  }

  return {
    busy,
    job,
    task,
    events,
    streamError,
    authorId,
    profileId,
    launch,
    approveWriteback,
    rejectWriteback,
    retry,
    stop,
    dispose,
    reset,
  };
}

function messageFor(cause: unknown, fallback: string): string {
  return cause instanceof Error && cause.message ? cause.message : fallback;
}

function isActiveJobStatus(status: string): boolean {
  return ["queued", "running", "stopping"].includes(status);
}
