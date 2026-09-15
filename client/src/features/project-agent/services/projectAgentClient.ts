import type { ApiTransport } from "@/services/api";
import { featureTransport } from "@/services/featureTransport";
import type {
  ProjectAgentJob,
  ProjectAgentSession,
  ProjectAgentSessionSummary,
  ProjectAgentStreamEvent,
  ProjectAgentTurnStart,
} from "@/features/project-agent/types";

export interface ProjectAgentClient {
  listSessions(projectRoot: string): Promise<{ items: ProjectAgentSessionSummary[] }>;
  createSession(projectRoot: string, title: string): Promise<ProjectAgentSession>;
  readSession(sessionId: string): Promise<ProjectAgentSession>;
  startTurn(sessionId: string, message: string): Promise<ProjectAgentTurnStart>;
  readJob(jobId: string): Promise<ProjectAgentJob>;
  stopJob(jobId: string): Promise<{ job_id: string; status: string; stopped: boolean }>;
  observeJob(
    jobId: string,
    signal: AbortSignal,
    onEvent: (value: ProjectAgentStreamEvent) => void,
  ): Promise<void>;
}

export function createProjectAgentClient(transport: ApiTransport = featureTransport): ProjectAgentClient {
  const q = transport.query;
  return {
    listSessions: (projectRoot) => transport.request<{ items: ProjectAgentSessionSummary[] }>(
      `/project-agent/sessions?${q({ project_root: projectRoot, limit: 30 })}`,
    ),
    createSession: (projectRoot, title) => transport.request<ProjectAgentSession>(
      "/project-agent/sessions",
      { method: "POST", body: JSON.stringify({ project_root: projectRoot, title }) },
    ),
    readSession: (sessionId) => transport.request<ProjectAgentSession>(
      `/project-agent/sessions/${encodeURIComponent(sessionId)}`,
    ),
    startTurn: (sessionId, message) => transport.request<ProjectAgentTurnStart>(
      `/project-agent/sessions/${encodeURIComponent(sessionId)}/turns`,
      { method: "POST", body: JSON.stringify({ message, timeout: 240 }) },
    ),
    readJob: (jobId) => transport.request<ProjectAgentJob>(
      `/project-agent/jobs/${encodeURIComponent(jobId)}`,
    ),
    stopJob: (jobId) => transport.request<{ job_id: string; status: string; stopped: boolean }>(
      `/project-agent/jobs/${encodeURIComponent(jobId)}/stop`,
      { method: "POST" },
    ),
    observeJob: (jobId, signal, onEvent) => observeDurableEvents(transport, jobId, signal, onEvent),
  };
}

async function observeDurableEvents(
  transport: ApiTransport,
  jobId: string,
  signal: AbortSignal,
  onEvent: (value: ProjectAgentStreamEvent) => void,
): Promise<void> {
  let cursor = 0;
  let retryDelay = 350;
  let consecutiveFailures = 0;
  while (!signal.aborted) {
    try {
      const response = await transport.authorizedFetch(
        `/project-agent/jobs/${encodeURIComponent(jobId)}/events?${transport.query({ after: cursor })}`,
        { method: "GET", signal, headers: cursor ? { "Last-Event-ID": String(cursor) } : undefined },
      );
      if (!response.ok || !response.body) throw new Error(`项目 Agent 事件连接失败（${response.status}）`);
      const terminal = await consumeEventStream(response.body, signal, (event) => {
        cursor = Math.max(cursor, event.cursor);
        onEvent(event);
      });
      if (terminal) return;
      retryDelay = 350;
      consecutiveFailures = 0;
    } catch (cause) {
      if (signal.aborted || isAbort(cause)) return;
      consecutiveFailures += 1;
      if (consecutiveFailures >= 6) throw cause;
      await delay(retryDelay, signal);
      retryDelay = Math.min(4_000, retryDelay * 2);
    }
  }
}

async function consumeEventStream(
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal,
  onEvent: (value: ProjectAgentStreamEvent) => void,
): Promise<boolean> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminal = false;
  try {
    while (!signal.aborted) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
      const frames = buffer.split("\n\n");
      buffer = frames.pop() || "";
      for (const frame of frames) {
        const parsed = parseFrame(frame);
        if (!parsed) continue;
        onEvent(parsed);
        if (parsed.event === "stream.terminal") terminal = true;
      }
      if (done || terminal) break;
    }
  } finally {
    reader.releaseLock();
  }
  return terminal;
}

function parseFrame(frame: string): ProjectAgentStreamEvent | null {
  if (!frame.trim() || frame.startsWith(":")) return null;
  let event = "message";
  let cursor = 0;
  const data: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("id:")) cursor = Number(line.slice(3).trim()) || 0;
    if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return null;
  const parsed = JSON.parse(data.join("\n"));
  return {
    event,
    data: typeof parsed === "object" && parsed !== null ? parsed as Record<string, unknown> : {},
    cursor,
  };
}

function delay(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = window.setTimeout(resolve, milliseconds);
    signal.addEventListener("abort", () => {
      window.clearTimeout(timer);
      resolve();
    }, { once: true });
  });
}

function isAbort(cause: unknown): boolean {
  return cause instanceof DOMException && cause.name === "AbortError";
}

export const projectAgentClient = createProjectAgentClient();
