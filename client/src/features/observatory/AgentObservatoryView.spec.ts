import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AgentObservatoryView from "./AgentObservatoryView.vue";

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }));

vi.mock("@/services/api", () => ({
  api: apiMock,
  query: (values: Record<string, string>) =>
    new URLSearchParams(values).toString(),
  connectEventStream: vi.fn(() => ({ close: vi.fn() })),
}));

function observabilityFixture() {
  return {
    ok: true,
    schema: "arcvellum/agent-observability/v3",
    project_root: "C:\\ArcVellum\\潮线",
    status: "active",
    active_task: {
      role: "main-creative-agent",
      runtime: "opencode",
      route: "scene-development",
      task_id: "task-1",
      status: "running",
      stage: "generation-agent-task",
      message: "",
      tasks_completed: 1,
      failures: 0,
    },
    activity: {
      phase: "reasoning",
      label: "正在推演",
      runtime_active: true,
      productive_progress_observed: false,
      waiting_reason: "模型连接保持活动，正在组织判断。",
      last_event: "runner.reasoning.started",
    },
    context_diagnostics: {
      available: true,
      task_kind: "prose",
      mode: "bounded",
      contract_status: "bounded-ready",
      digest: "context-digest",
      tiers: { must_inline: 8, exact_on_demand: 3, excluded: 2 },
      access: { available: true, read_tool_calls: 4, unique_read_targets: 3, redundant_read_calls: 1 },
    },
    sessions: [
      {
        session_id: "session-1",
        role: "writer",
        runtime: "opencode",
        status: "active",
        route: "scene-development",
        event_count: 3,
        started_at: "2026-07-30T01:00:00+00:00",
      },
    ],
    recent_events: [
      {
        sequence: 1,
        at: "2026-07-30T01:00:00+00:00",
        event: "task.started",
        stage: "generation",
        message: "",
        task_id: "task-1",
        route: "scene-development",
      },
    ],
    revision: "rev-1",
  };
}

describe("AgentObservatoryView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    apiMock.mockReset();
    window.localStorage.clear();
  });

  it("renders real active task, sessions and recent events", async () => {
    apiMock.mockResolvedValue(observabilityFixture());
    const pinia = createPinia();
    setActivePinia(pinia);
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\潮线", false);

    const wrapper = mount(AgentObservatoryView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("main-creative-agent");
    expect(wrapper.text()).toContain("task-1");
    expect(wrapper.text()).toContain("writer");
    expect(wrapper.text()).toContain("task.started");
    expect(wrapper.text()).toContain("主创 Agent");
    expect(wrapper.text()).toContain("任务已开始");
    expect(wrapper.text()).toContain("正在推演");
    expect(wrapper.text()).toContain("8 直接 / 3 按需 / 2 排除");
    expect(wrapper.text()).toContain("1 次");
  });

  it("explains missing observability without fabricating data", async () => {
    apiMock.mockRejectedValue(new Error("no project"));
    const pinia = createPinia();
    setActivePinia(pinia);
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\潮线", false);

    const wrapper = mount(AgentObservatoryView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("观测数据暂不可用");
  });
});
