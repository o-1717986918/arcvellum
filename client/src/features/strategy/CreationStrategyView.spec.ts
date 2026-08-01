import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CreationStrategyView from "./CreationStrategyView.vue";

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }));
const streamCloseMock = vi.hoisted(() => vi.fn());
let streamListener:
  | ((event: string, data: Record<string, unknown>) => void)
  | null = null;

vi.mock("@/services/api", () => ({
  api: apiMock,
  query: (values: Record<string, string>) =>
    new URLSearchParams(values).toString(),
  connectEventStream: vi.fn(
    (
      _path: string,
      listener: (event: string, data: Record<string, unknown>) => void,
    ) => {
      streamListener = listener;
      return { close: streamCloseMock };
    },
  ),
}));

function projectionFixture(activePlan: unknown) {
  return {
    schema: "arcvellum/strategy-projection/v1",
    settings: { enabled: false, mode: "fixed", preset: "balanced" },
    active_plan: activePlan,
    rolling_horizon: null,
  };
}

describe("CreationStrategyView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    apiMock.mockReset();
    streamCloseMock.mockReset();
    streamListener = null;
    window.localStorage.clear();
  });

  it("renders real strategy settings and active plan summary", async () => {
    apiMock.mockResolvedValue(
      projectionFixture({
        plan_id: "plan-1",
        revision: 3,
        status: "active",
        scope_kind: "chapter",
        scope_key: "chapter_01",
      }),
    );
    const pinia = createPinia();
    setActivePinia(pinia);
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\潮线", false);

    const wrapper = mount(CreationStrategyView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("fixed");
    expect(wrapper.text()).toContain("balanced");
    expect(wrapper.text()).toContain("plan-1");
    expect(wrapper.text()).toContain("chapter_01");
  });

  it("explains an empty active plan without fabricating data", async () => {
    apiMock.mockResolvedValue(projectionFixture(null));
    const pinia = createPinia();
    setActivePinia(pinia);
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\潮线", false);

    const wrapper = mount(CreationStrategyView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("还没有激活的创作计划");
  });

  it("renders typed plan events from the live stream", async () => {
    apiMock.mockResolvedValue(projectionFixture(null));
    const pinia = createPinia();
    setActivePinia(pinia);
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\潮线", false);

    const wrapper = mount(CreationStrategyView, {
      global: { plugins: [pinia] },
    });
    await flushPromises();
    streamListener?.("plan-event", {
      event_id: "e1",
      event_type: "plan.candidate.completed",
      plan_id: "plan-1",
      revision: 3,
      created_at: "2026-07-30T01:00:00+00:00",
    });
    await flushPromises();

    expect(wrapper.text()).toContain("plan.candidate.completed");
    expect(wrapper.text()).toContain("plan-1");
    expect(streamCloseMock).not.toHaveBeenCalled();
  });
});
