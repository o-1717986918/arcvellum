import { defineComponent, ref } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { ProjectAgentClient } from "@/features/project-agent/services/projectAgentClient";
import type { ProjectAgentSession } from "@/features/project-agent/types";
import { useProjectAgentSession } from "./useProjectAgentSession";

describe("useProjectAgentSession", () => {
  it("joins the durable job stream and restores the persisted conversation", async () => {
    let publish: Parameters<ProjectAgentClient["observeJob"]>[2] | undefined;
    let finish: (() => void) | undefined;
    const active = session([]);
    const completed = session([
      { role: "user", payload: { text: "项目到哪里了？" } },
      { role: "assistant", payload: { text: "第一章正在准备。", job_id: "job-1" } },
    ]);
    const client = fakeClient({
      createSession: vi.fn(async () => active),
      readSession: vi.fn(async () => completed),
      observeJob: vi.fn((_job, _signal, onEvent) => {
        publish = onEvent;
        return new Promise<void>((resolve) => { finish = resolve; });
      }),
    });
    const { wrapper, agent } = mountSession(client);

    await agent.load();
    const pending = agent.ask("项目到哪里了？");
    await flushPromises();
    await vi.waitFor(() => expect(publish).toBeTypeOf("function"));
    publish?.({ event: "project_agent.turn.started", cursor: 1, data: {} });
    publish?.({ event: "project_agent.tool.started", cursor: 2, data: { name: "project_overview", request_id: "read-1" } });
    publish?.({ event: "project_agent.event", cursor: 3, data: { event: "text.delta", text: "第一章" } });
    publish?.({ event: "project_agent.event", cursor: 4, data: { event: "text.delta", text: "正在准备。" } });
    await new Promise((resolve) => window.setTimeout(resolve, 0));

    expect(agent.messages.value.at(-1)?.payload.text).toBe("第一章正在准备。");
    expect(agent.activity.value?.tools[0].label).toBe("查看作品进度");
    finish?.();
    await pending;

    expect(agent.messages.value).toEqual(completed.messages);
    expect(agent.sending.value).toBe(false);
    wrapper.unmount();
  });

  it("reattaches a persisted active turn after the desktop returns", async () => {
    let publish: Parameters<ProjectAgentClient["observeJob"]>[2] | undefined;
    let finish: (() => void) | undefined;
    const active = session([
      { role: "user", payload: { text: "继续推进", turn_id: "turn-2", job_id: "job-2" } },
    ]);
    active.active_turn = { job_id: "job-2", turn_id: "turn-2", status: "running" };
    const completed = session([
      ...active.messages,
      { role: "assistant", payload: { text: "已经恢复并完成。", turn_id: "turn-2", job_id: "job-2" } },
    ]);
    const readSession = vi.fn()
      .mockResolvedValueOnce(active)
      .mockResolvedValueOnce(completed);
    const client = fakeClient({
      createSession: vi.fn(async () => active),
      readSession,
      observeJob: vi.fn((_job, _signal, onEvent) => {
        publish = onEvent;
        return new Promise<void>((resolve) => { finish = resolve; });
      }),
    });
    const { wrapper, agent } = mountSession(client);
    await agent.load();

    const recovering = agent.recover();
    await vi.waitFor(() => expect(publish).toBeTypeOf("function"));
    expect(agent.sending.value).toBe(true);
    expect(agent.activity.value?.statusLabel).toBe("正在重新连接");
    publish?.({ event: "project_agent.event", cursor: 9, data: { event: "text.delta", text: "已经恢复" } });
    await new Promise((resolve) => window.setTimeout(resolve, 0));
    expect(agent.messages.value.at(-1)?.payload.text).toBe("已经恢复");

    finish?.();
    await recovering;
    expect(agent.messages.value.at(-1)?.payload.text).toBe("已经恢复并完成。");
    expect(agent.sending.value).toBe(false);
    wrapper.unmount();
  });

  it("keeps a long conversation responsive while reporting omitted history", async () => {
    const history = Array.from({ length: 95 }, (_, index) => ({
      role: index % 2 ? "assistant" as const : "user" as const,
      payload: { text: `message-${index + 1}` },
    }));
    const restored = session(history);
    const client = fakeClient({
      listSessions: vi.fn(async () => ({ items: [{
        session_id: restored.session_id,
        project_root: restored.project_root,
        title: restored.title,
        session_kind: "project-agent" as const,
        created_at: restored.created_at,
        updated_at: restored.updated_at,
      }] })),
      readSession: vi.fn(async () => restored),
    });
    const { wrapper, agent } = mountSession(client);

    await agent.load();

    expect(agent.messages.value).toHaveLength(80);
    expect(agent.messages.value[0].payload.text).toBe("message-16");
    expect(agent.omittedMessageCount.value).toBe(15);
    wrapper.unmount();
  });
});

function mountSession(client: ProjectAgentClient) {
  let agent: ReturnType<typeof useProjectAgentSession> | undefined;
  const wrapper = mount(defineComponent({
    setup() {
      agent = useProjectAgentSession({
        projectRoot: ref("C:/Works/story"),
        projectTitle: ref("潮汐之后"),
        client,
        flushDelayMs: 0,
      });
      return {};
    },
    template: "<div />",
  }));
  return { wrapper, agent: agent! };
}
function session(messages: ProjectAgentSession["messages"]): ProjectAgentSession {
  return {
    session_id: "project-agent-1",
    project_root: "C:/Works/story",
    title: "潮汐之后创作会话",
    session_kind: "project-agent",
    snapshot_digest: "digest",
    created_at: "2026-09-14T00:00:00Z",
    updated_at: "2026-09-14T00:00:00Z",
    messages,
  };
}

function fakeClient(overrides: Partial<ProjectAgentClient> = {}): ProjectAgentClient {
  return {
    listSessions: vi.fn(async () => ({ items: [] })),
    createSession: vi.fn(async () => session([])),
    readSession: vi.fn(async () => session([])),
    startTurn: vi.fn(async () => ({ session_id: "project-agent-1", turn_id: "turn-1", job_id: "job-1", status: "queued" })),
    readJob: vi.fn(),
    observeJob: vi.fn(async () => undefined),
    ...overrides,
  } as ProjectAgentClient;
}
