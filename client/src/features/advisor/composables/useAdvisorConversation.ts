import { computed, onBeforeUnmount, ref, type Ref } from "vue";
import { advisorClient, type AdvisorClient } from "@/features/advisor/services/advisorClient";
import type { AdvisorAnswer, AdvisorMessage, AdvisorSession } from "@/types/api";

interface AdvisorConversationOptions {
  projectRoot: Readonly<Ref<string>>;
  projectTitle: Readonly<Ref<string>>;
  context: () => Record<string, unknown>;
  client?: AdvisorClient;
  onError?: (cause: unknown, fallback: string) => void;
  afterRender?: () => void | Promise<void>;
  flushDelayMs?: number;
}

export function useAdvisorConversation(options: AdvisorConversationOptions) {
  const client = options.client || advisorClient;
  const loadingSession = ref(false);
  const thinking = ref(false);
  const session = ref<AdvisorSession | null>(null);
  const transientMessages = ref<AdvisorMessage[]>([]);
  const messages = computed(() => transientMessages.value.length
    ? transientMessages.value
    : session.value?.messages || []);
  let requestController: AbortController | null = null;
  let deltaBuffer = "";
  let deltaTimer = 0;

  async function ensureSession(): Promise<AdvisorSession | null> {
    if (session.value || loadingSession.value || !options.projectRoot.value) return session.value;
    loadingSession.value = true;
    try {
      const list = await client.sessions(options.projectRoot.value);
      session.value = list.items?.[0]?.session_id
        ? await client.session(list.items[0].session_id)
        : await client.createSession(options.projectRoot.value, `${options.projectTitle.value}创作对话`);
      await notifyRendered();
      return session.value;
    } catch (cause) {
      options.onError?.(cause, "暂时无法建立顾问对话。");
      return null;
    } finally {
      loadingSession.value = false;
    }
  }

  async function ask(question: string): Promise<void> {
    const value = question.trim();
    if (!value || thinking.value || !options.projectRoot.value) return;
    const activeSession = await ensureSession();
    if (!activeSession) return;
    thinking.value = true;
    resetDelta();
    transientMessages.value = [
      ...(activeSession.messages || []),
      { role: "user", payload: { question: value } },
      { role: "advisor", payload: { message: "", evidence: [], uncertainties: [], suggested_actions: [] } },
    ];
    await notifyRendered();
    try {
      requestController = new AbortController();
      await client.ask(
        activeSession.session_id,
        value,
        options.context(),
        requestController.signal,
        consumeStreamEvent,
      );
      session.value = await client.session(activeSession.session_id);
      transientMessages.value = [];
    } catch (cause) {
      const current = currentAdvisorMessage();
      if (current && !isAbort(cause)) {
        current.payload.message = errorMessage(cause, "顾问暂时没有完成回答，请重试。");
      }
    } finally {
      flushDelta();
      requestController = null;
      thinking.value = false;
      await notifyRendered();
    }
  }

  function consumeStreamEvent(event: string, data: Record<string, unknown>): void {
    const current = currentAdvisorMessage();
    if (!current) return;
    if (event === "advisor.delta") {
      deltaBuffer += String(data.text || "");
      scheduleDeltaFlush();
    } else if (event === "advisor.result") {
      flushDelta();
      current.payload = (data.answer || {}) as AdvisorAnswer;
    } else if (event === "advisor.error") {
      current.payload.message = String(data.message || "顾问暂时没有完成回答。");
    }
    void notifyRendered();
  }

  function scheduleDeltaFlush(): void {
    if (deltaTimer) return;
    deltaTimer = window.setTimeout(() => {
      deltaTimer = 0;
      flushDelta();
    }, options.flushDelayMs ?? 72);
  }

  function flushDelta(): void {
    if (!deltaBuffer) return;
    const current = currentAdvisorMessage();
    if (current) current.payload.message = String(current.payload.message || "") + deltaBuffer;
    deltaBuffer = "";
    void notifyRendered();
  }

  function reset(): void {
    stop();
    session.value = null;
    transientMessages.value = [];
    loadingSession.value = false;
    resetDelta();
  }

  function stop(): void {
    requestController?.abort();
  }

  function resetDelta(): void {
    deltaBuffer = "";
    window.clearTimeout(deltaTimer);
    deltaTimer = 0;
  }

  function currentAdvisorMessage(): AdvisorMessage | undefined {
    const current = transientMessages.value.at(-1);
    return current?.role === "advisor" ? current : undefined;
  }

  async function notifyRendered(): Promise<void> {
    await options.afterRender?.();
  }

  onBeforeUnmount(() => {
    stop();
    resetDelta();
  });

  return {
    ask,
    ensureSession,
    loadingSession,
    messages,
    reset,
    session,
    stop,
    thinking,
  };
}

function isAbort(cause: unknown): boolean {
  return cause instanceof DOMException && cause.name === "AbortError";
}

function errorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof Error && cause.message.trim()) return cause.message;
  return fallback;
}
