import { defineComponent, ref } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { useAdvisorConversation } from "./useAdvisorConversation";
import type { AdvisorClient } from "@/features/advisor/services/advisorClient";
import type { AdvisorSession } from "@/types/api";

function mountConversation(client: AdvisorClient) {
  let conversation: ReturnType<typeof useAdvisorConversation> | undefined;
  const wrapper = mount(defineComponent({
    setup() {
      conversation = useAdvisorConversation({
        projectRoot: ref("C:/Works/story"),
        projectTitle: ref("潮汐之后"),
        context: () => ({ view: "overview", user_intent: "free_conversation" }),
        client,
        flushDelayMs: 0,
      });
      return {};
    },
    template: "<div />",
  }));
  return { wrapper, conversation: conversation! };
}

function fakeClient(overrides: Partial<AdvisorClient> = {}): AdvisorClient {
  const active: AdvisorSession = {
    session_id: "advisor-1",
    project_root: "C:/Works/story",
    title: "潮汐之后创作对话",
    messages: [],
  };
  return {
    surface: vi.fn(),
    observeInbox: vi.fn(),
    selectPersona: vi.fn(),
    saveCustomPersona: vi.fn(),
    saveInboxSettings: vi.fn(),
    markNotice: vi.fn(),
    sessions: vi.fn(async () => ({ items: [] })),
    session: vi.fn(async () => active),
    createSession: vi.fn(async () => active),
    ask: vi.fn(async () => undefined),
    ...overrides,
  } as AdvisorClient;
}

describe("useAdvisorConversation", () => {
  it("restores or creates a session and consumes streamed answer events", async () => {
    let publish: ((event: string, data: Record<string, unknown>) => void) | undefined;
    let finish: (() => void) | undefined;
    const completed: AdvisorSession = {
      session_id: "advisor-1",
      project_root: "C:/Works/story",
      title: "潮汐之后创作对话",
      messages: [{ role: "advisor", payload: { message: "完整回答" } }],
    };
    const client = fakeClient({
      ask: vi.fn((_id, _question, _context, _signal, onEvent) => {
        publish = onEvent;
        return new Promise<void>((resolve) => { finish = resolve; });
      }),
      session: vi.fn(async () => completed),
    });
    const { wrapper, conversation } = mountConversation(client);

    const pending = conversation.ask("下一步该做什么？");
    await flushPromises();
    await vi.waitFor(() => expect(publish).toBeTypeOf("function"));
    publish?.("advisor.delta", { text: "先完善" });
    publish?.("advisor.delta", { text: "人物动机。" });
    await new Promise((resolve) => window.setTimeout(resolve, 0));

    expect(conversation.thinking.value).toBe(true);
    expect(conversation.messages.value.at(-1)?.payload.message).toBe("先完善人物动机。");
    expect(client.ask).toHaveBeenCalledWith(
      "advisor-1",
      "下一步该做什么？",
      { view: "overview", user_intent: "free_conversation" },
      expect.any(AbortSignal),
      expect.any(Function),
    );

    finish?.();
    await pending;
    expect(conversation.messages.value).toEqual(completed.messages);
    expect(conversation.thinking.value).toBe(false);
    wrapper.unmount();
  });

  it("cancels the active request without replacing the answer with an error", async () => {
    const client = fakeClient({
      ask: vi.fn((_id, _question, _context, signal) => new Promise<void>((_resolve, reject) => {
        signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
      })),
    });
    const { wrapper, conversation } = mountConversation(client);
    const pending = conversation.ask("停一下");
    await flushPromises();
    await vi.waitFor(() => expect(client.ask).toHaveBeenCalledOnce());
    conversation.stop();
    await pending;

    expect(conversation.thinking.value).toBe(false);
    expect(conversation.messages.value.at(-1)?.payload.message).toBe("");
    wrapper.unmount();
  });
});
