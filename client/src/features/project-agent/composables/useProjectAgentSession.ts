import { computed, onBeforeUnmount, ref, type Ref } from "vue";
import {
  PROJECT_AGENT_TOOL_LABELS,
  type ProjectAgentMessage,
  type ProjectAgentSession,
  type ProjectAgentSessionSummary,
  type ProjectAgentStreamEvent,
  type ProjectAgentTurnActivity,
} from "@/features/project-agent/types";
import {
  projectAgentClient,
  type ProjectAgentClient,
} from "@/features/project-agent/services/projectAgentClient";

interface ProjectAgentSessionOptions {
  projectRoot: Readonly<Ref<string>>;
  projectTitle: Readonly<Ref<string>>;
  client?: ProjectAgentClient;
  onError?: (cause: unknown, fallback: string) => void;
  afterRender?: () => void | Promise<void>;
  flushDelayMs?: number;
}

const MAX_RENDERED_MESSAGES = 80;

export function useProjectAgentSession(options: ProjectAgentSessionOptions) {
  const client = options.client || projectAgentClient;
  const sessions = ref<ProjectAgentSessionSummary[]>([]);
  const session = ref<ProjectAgentSession | null>(null);
  const loading = ref(false);
  const creating = ref(false);
  const sending = ref(false);
  const activity = ref<ProjectAgentTurnActivity | null>(null);
  const transientMessages = ref<ProjectAgentMessage[]>([]);
  const messages = computed(() => {
    const source = transientMessages.value.length ? transientMessages.value : session.value?.messages || [];
    return source.slice(-MAX_RENDERED_MESSAGES);
  });
  const omittedMessageCount = computed(() => {
    const count = transientMessages.value.length || session.value?.messages.length || 0;
    return Math.max(0, count - MAX_RENDERED_MESSAGES);
  });
  let eventController: AbortController | null = null;
  let deltaBuffer = "";
  let deltaTimer = 0;

  async function load(): Promise<ProjectAgentSession | null> {
    if (!options.projectRoot.value || loading.value) return session.value;
    loading.value = true;
    try {
      const response = await client.listSessions(options.projectRoot.value);
      sessions.value = response.items || [];
      if (sessions.value[0]) return await openSession(sessions.value[0].session_id);
      return await createSession();
    } catch (cause) {
      options.onError?.(cause, "项目 Agent 暂时无法读取会话。");
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function createSession(): Promise<ProjectAgentSession | null> {
    if (!options.projectRoot.value || sending.value || creating.value) return null;
    creating.value = true;
    try {
      const created = await client.createSession(
        options.projectRoot.value,
        `${options.projectTitle.value}创作会话`,
      );
      sessions.value = [sessionSummary(created), ...sessions.value.filter((item) => item.session_id !== created.session_id)];
      session.value = created;
      transientMessages.value = [];
      activity.value = null;
      await notifyRendered();
      return created;
    } catch (cause) {
      options.onError?.(cause, "暂时无法建立新对话。");
      return null;
    } finally {
      creating.value = false;
    }
  }

  async function openSession(sessionId: string): Promise<ProjectAgentSession | null> {
    if (!sessionId || sending.value) return session.value;
    try {
      session.value = await client.readSession(sessionId);
      transientMessages.value = [];
      activity.value = null;
      await notifyRendered();
      return session.value;
    } catch (cause) {
      options.onError?.(cause, "暂时无法打开这段对话。");
      return null;
    }
  }

  async function ask(message: string): Promise<void> {
    const value = message.trim();
    if (!value || sending.value || !options.projectRoot.value) return;
    const active = session.value || await load();
    if (!active) return;
    sending.value = true;
    resetDelta();
    transientMessages.value = [
      ...(active.messages || []),
      { role: "user", at: new Date().toISOString(), payload: { text: value } },
      { role: "assistant", at: new Date().toISOString(), payload: { text: "" } },
    ];
    activity.value = emptyActivity();
    await notifyRendered();
    try {
      const turn = await client.startTurn(active.session_id, value);
      activity.value = {
        ...emptyActivity(),
        jobId: turn.job_id,
        turnId: turn.turn_id,
        statusLabel: "等待执行",
      };
      eventController = new AbortController();
      await client.observeJob(turn.job_id, eventController.signal, consumeEvent);
      flushDelta();
      session.value = await client.readSession(active.session_id);
      const latest = sessionSummary(session.value);
      sessions.value = [latest, ...sessions.value.filter((item) => item.session_id !== latest.session_id)];
      transientMessages.value = [];
    } catch (cause) {
      flushDelta();
      const answer = currentTransientAnswer();
      if (answer && !answer.payload.text) answer.payload.text = errorMessage(cause, "这次回答没有完成，请重试。");
      if (activity.value) {
        activity.value.status = "failed";
        activity.value.statusLabel = "回答中断";
      }
      options.onError?.(cause, "项目 Agent 暂时没有完成回答。");
    } finally {
      eventController = null;
      sending.value = false;
      await notifyRendered();
    }
  }

  function consumeEvent(value: ProjectAgentStreamEvent): void {
    const data = value.data;
    if (value.event === "project_agent.turn.started") {
      patchActivity({ status: "running", statusLabel: "正在理解作品" });
    } else if (value.event === "project_agent.event") {
      consumeAgentEvent(data);
    } else if (value.event === "project_agent.tool.started") {
      upsertTool(String(data.request_id || data.name || "tool"), String(data.name || ""), "running");
      patchActivity({ statusLabel: "正在查阅项目" });
    } else if (value.event === "project_agent.tool.finished") {
      upsertTool(
        String(data.request_id || data.name || "tool"),
        String(data.name || ""),
        data.ok === false ? "failed" : "complete",
      );
      patchActivity({ statusLabel: data.ok === false ? "资料读取失败" : "已取得项目证据" });
    } else if (value.event === "project_agent.result") {
      flushDelta();
      const answer = currentTransientAnswer();
      if (answer) answer.payload.text = String(data.answer || answer.payload.text || "");
      patchActivity({ status: "complete", statusLabel: "回答完成" });
    } else if (value.event === "project_agent.error") {
      patchActivity({ status: "failed", statusLabel: String(data.message || "回答失败") });
    }
    void notifyRendered();
  }

  function consumeAgentEvent(data: Record<string, unknown>): void {
    const event = String(data.event || data.kind || "");
    if (event === "text.delta") {
      deltaBuffer += String(data.text || "");
      scheduleDeltaFlush();
    } else if (event === "reasoning.delta") {
      if (activity.value) activity.value.reasoning += String(data.text || "");
      patchActivity({ statusLabel: "正在推理" });
    } else if (event === "model.usage" && activity.value) {
      activity.value.inputTokens += Number(data.input_tokens || 0);
      activity.value.outputTokens += Number(data.output_tokens || 0);
    }
  }

  function upsertTool(key: string, name: string, status: "running" | "complete" | "failed"): void {
    if (!activity.value) return;
    const existing = activity.value.tools.find((item) => item.key === key);
    if (existing) {
      existing.status = status;
      return;
    }
    activity.value.tools.push({
      key,
      name,
      label: PROJECT_AGENT_TOOL_LABELS[name] || "读取项目信息",
      status,
    });
  }

  function patchActivity(values: Partial<ProjectAgentTurnActivity>): void {
    if (activity.value) Object.assign(activity.value, values);
  }

  function scheduleDeltaFlush(): void {
    if (deltaTimer) return;
    deltaTimer = window.setTimeout(() => {
      deltaTimer = 0;
      flushDelta();
    }, options.flushDelayMs ?? 64);
  }

  function flushDelta(): void {
    if (!deltaBuffer) return;
    const answer = currentTransientAnswer();
    if (answer) answer.payload.text = String(answer.payload.text || "") + deltaBuffer;
    deltaBuffer = "";
    void notifyRendered();
  }

  function reset(): void {
    eventController?.abort();
    eventController = null;
    sessions.value = [];
    session.value = null;
    transientMessages.value = [];
    activity.value = null;
    loading.value = false;
    creating.value = false;
    sending.value = false;
    resetDelta();
  }

  function currentTransientAnswer(): ProjectAgentMessage | undefined {
    const last = transientMessages.value.at(-1);
    return last?.role === "assistant" ? last : undefined;
  }

  function resetDelta(): void {
    deltaBuffer = "";
    window.clearTimeout(deltaTimer);
    deltaTimer = 0;
  }

  async function notifyRendered(): Promise<void> {
    await options.afterRender?.();
  }

  onBeforeUnmount(() => {
    eventController?.abort();
    resetDelta();
  });

  return {
    activity,
    ask,
    createSession,
    creating,
    load,
    loading,
    messages,
    omittedMessageCount,
    openSession,
    reset,
    sending,
    session,
    sessions,
  };
}

function emptyActivity(): ProjectAgentTurnActivity {
  return {
    jobId: "",
    turnId: "",
    status: "queued",
    statusLabel: "准备回答",
    reasoning: "",
    tools: [],
    inputTokens: 0,
    outputTokens: 0,
    startedAt: Date.now(),
  };
}

function sessionSummary(session: ProjectAgentSession): ProjectAgentSessionSummary {
  return {
    session_id: session.session_id,
    project_root: session.project_root,
    title: session.title,
    session_kind: "project-agent",
    created_at: session.created_at,
    updated_at: session.updated_at,
  };
}

function errorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof Error && cause.message.trim()) return cause.message;
  return fallback;
}
