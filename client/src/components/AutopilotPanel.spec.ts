import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AutopilotPanel from "./AutopilotPanel.vue";

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }));

vi.mock("@/services/api", () => ({
  api: apiMock,
  query: (values: Record<string, string>) => new URLSearchParams(values).toString(),
  connectEventStream: vi.fn(() => ({ close: vi.fn() })),
}));

const policy = {
  schema: "arcvellum/delegation-policy/v0.1",
  version: "0.1",
  mode: "collaborative" as const,
  delegated_routes: [],
  delegated_decisions: [],
  limits: { max_tasks: 500, max_runtime_hours: 24, max_consecutive_revisions: 3, max_failures_per_task: 2, max_cost: 100 },
  release_policy: "require_user" as const,
  expires_at: "",
};

describe("AutopilotPanel", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    apiMock.mockReset();
    apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.startsWith("/autopilot/status")) return { ok: true, policy, run: null };
      if (path === "/autopilot/policy") {
        const next = JSON.parse(String(init?.body || "{}"));
        return { ok: true, policy: next.policy };
      }
      throw new Error(`Unexpected API path: ${path}`);
    });
  });

  it("makes full-auto selection visible and asks for explicit authorization", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const { useAppStore } = await import("@/stores/app");
    const store = useAppStore();
    store.setCurrentProject("C:\\ArcVellum\\作品", false);
    const wrapper = mount(AutopilotPanel, { global: { plugins: [pinia] } });
    await flushPromises();

    const fullAuto = wrapper.findAll("button").find((button) => button.text().includes("全自动交付"));
    expect(fullAuto).toBeTruthy();
    await fullAuto?.trigger("click");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith("/autopilot/policy", expect.objectContaining({ method: "PUT" }));
    expect(wrapper.text()).toContain("全自动模式已准备好");
    expect(wrapper.text()).toContain("确认授权并开始");
    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(true);
  });
});
