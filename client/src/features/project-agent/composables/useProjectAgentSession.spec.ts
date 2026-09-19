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
    const onToolFinished = vi.fn();
    const { wrapper, agent } = mountSession(client, onToolFinished);

    await agent.createSession();
    const pending = agent.ask("项目到哪里了？");
    await flushPromises();
    await vi.waitFor(() => expect(publish).toBeTypeOf("function"));
    publish?.({ event: "project_agent.turn.started", cursor: 1, data: {} });
    publish?.({ event: "project_agent.tool.started", cursor: 2, data: { name: "project_overview", request_id: "read-1" } });
    publish?.({ event: "project_agent.tool.finished", cursor: 3, data: { name: "project_overview", request_id: "read-1", ok: true } });
    publish?.({ event: "project_agent.event", cursor: 4, data: { event: "text.delta", text: "第一章" } });
    publish?.({ event: "project_agent.event", cursor: 5, data: { event: "text.delta", text: "正在准备。" } });
    await new Promise((resolve) => window.setTimeout(resolve, 0));

    expect(agent.messages.value.at(-1)?.payload.text).toBe("第一章正在准备。");
    expect(agent.activity.value?.tools[0].label).toBe("查看作品进度");
    expect(onToolFinished).toHaveBeenCalledWith("project_overview", true);
    publish?.({ event: "project_agent.goal.waiting", cursor: 6, data: { run_id: "autopilot-1" } });
    expect(agent.activity.value?.statusLabel).toBe("后台正在持续完成长期目标");
    publish?.({ event: "project_agent.goal.progress", cursor: 7, data: { current_route: "scene-development", tasks_completed: 4 } });
    expect(agent.activity.value?.statusLabel).toBe("正在推进正文创作 · 已完成 4 项");
    publish?.({ event: "project_agent.goal.terminal", cursor: 8, data: { status: "complete" } });
    expect(agent.activity.value?.statusLabel).toBe("长期目标已完成，正在复核交付");
    publish?.({ event: "project_agent.goal.followup.started", cursor: 9, data: {} });
    expect(agent.activity.value?.statusLabel).toBe("正在核验最终结果");
    expect(agent.messages.value.at(-1)?.payload.text).toBe("");
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
    await agent.createSession();

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

  it("lists conversations across works without creating one, then opens its bound work", async () => {
    const first = session([]);
    const second = { ...session([]), session_id: "project-agent-2", project_root: "C:/Works/other", title: "另一部作品", updated_at: "2026-09-15T00:00:00Z" };
    const createSession = vi.fn(async () => first);
    const listSessions = vi.fn(async (root: string) => ({ items: root === first.project_root ? [first] : root === second.project_root ? [second] : [] }));
    const onSessionOpened = vi.fn();
    const client = fakeClient({ createSession, listSessions, readSession: vi.fn(async (id) => id === second.session_id ? second : first) });
    let agent: ReturnType<typeof useProjectAgentSession> | undefined;
    const wrapper = mount(defineComponent({
      setup() {
        agent = useProjectAgentSession({
          projectRoot: ref(first.project_root),
          projectTitle: ref("潮汐之后"),
          projectRoots: ref([first.project_root, second.project_root]),
          client,
          onSessionOpened,
        });
        return {};
      },
      template: "<div />",
    }));

    await agent!.load();
    expect(createSession).not.toHaveBeenCalled();
    expect(agent!.sessions.value.map((item) => item.session_id)).toEqual([second.session_id, first.session_id]);
    expect(agent!.session.value?.project_root).toBe(second.project_root);
    expect(onSessionOpened).toHaveBeenCalledWith(second);
    wrapper.unmount();
  });

  it("does not send a starter prompt through an unrelated saved conversation", async () => {
    const listSessions = vi.fn(async () => ({ items: [] }));
    const startTurn = vi.fn();
    const client = fakeClient({ listSessions, startTurn });
    const { wrapper, agent } = mountSession(client);

    await agent.ask("继续写作");

    expect(listSessions).not.toHaveBeenCalled();
    expect(startTurn).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});

function mountSession(client: ProjectAgentClient, onToolFinished?: (name: string, ok: boolean) => void) {
  let agent: ReturnType<typeof useProjectAgentSession> | undefined;
  const wrapper = mount(defineComponent({
    setup() {
      agent = useProjectAgentSession({
        projectRoot: ref("C:/Works/story"),
        projectTitle: ref("潮汐之后"),
        client,
        flushDelayMs: 0,
        onToolFinished,
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
    stopJob: vi.fn(async () => ({ job_id: "job-1", status: "stopping", stopped: true })),
    observeJob: vi.fn(async () => undefined),
    ...overrides,
  } as ProjectAgentClient;
}
