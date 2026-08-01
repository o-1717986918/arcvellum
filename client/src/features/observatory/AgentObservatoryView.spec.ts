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
    schema: "arcvellum/agent-observability/v2",
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
