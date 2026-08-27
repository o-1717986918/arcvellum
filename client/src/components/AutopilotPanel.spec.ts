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
  limits: { max_consecutive_revisions: 3, max_failures_per_task: 2 },
  release_policy: "require_user" as const,
};

describe("AutopilotPanel", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
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

  it("starts formal creation with the embedded Pi worker by default", async () => {
    apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.startsWith("/autopilot/status")) return { ok: true, policy, run: null };
      if (path === "/autopilot/start") {
        const request = JSON.parse(String(init?.body || "{}"));
        expect(request.runtime).toBe("pi-worker");
        return {
          ok: true,
          run: {
            run_id: "run-pi-worker",
            project_root: "C:\\ArcVellum\\作品",
            mode: "collaborative",
            runtime: request.runtime,
            status: "running",
            current_route: "planning",
            current_task_id: "",
            tasks_completed: 0,
            failures: 0,
            consecutive_revisions: 0,
            estimated_cost: 0,
            last_error: "",
            stop_reason: "",
          },
        };
      }
      throw new Error(`Unexpected API path: ${path}`);
    });
    const pinia = createPinia();
    setActivePinia(pinia);
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\作品", false);
    const wrapper = mount(AutopilotPanel, { global: { plugins: [pinia] } });
    await flushPromises();

    expect(wrapper.text()).toContain("内置 Pi 主创");
    const start = wrapper.findAll("button").find((button) => button.text() === "开始");
    expect(start).toBeTruthy();
    await start?.trigger("click");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      "/autopilot/start",
      expect.objectContaining({ method: "POST" }),
    );
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
    expect(wrapper.text()).toContain("不设任务数、时长或费用上限");
    expect(wrapper.text()).not.toContain("授权需要续期");
  });

  it("labels the counter as formal gate advances rather than finished creative works", async () => {
    apiMock.mockImplementation(async (path: string) => {
      if (path.startsWith("/autopilot/status")) {
        return {
          ok: true,
          policy,
          run: {
            run_id: "run-counter",
            project_root: "C:\\ArcVellum\\作品",
            mode: "collaborative",
            runtime: "opencode",
            status: "running",
            current_route: "scene-development",
            current_task_id: "scene-review",
            tasks_completed: 85,
            failures: 0,
            consecutive_revisions: 0,
            estimated_cost: 0,
            last_error: "",
            stop_reason: "",
          },
        };
      }
      throw new Error(`Unexpected API path: ${path}`);
    });
    const pinia = createPinia();
    setActivePinia(pinia);
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\作品", false);
    const wrapper = mount(AutopilotPanel, { global: { plugins: [pinia] } });
    await flushPromises();

    expect(wrapper.text()).toContain("已通过正式门禁 85 次");
    expect(wrapper.text()).not.toContain("已经完成 85 项创作任务");
  });

  it("renders a recovery card instead of exposing a raw runtime failure as the headline", async () => {
    apiMock.mockImplementation(async (path: string) => {
      if (path.startsWith("/autopilot/status")) {
        return {
          ok: true,
          policy,
          run: {
            run_id: "run-failure",
            project_root: "C:\\ArcVellum\\作品",
            mode: "collaborative",
            runtime: "pi-worker",
            status: "paused",
            current_route: "longform-planning",
            current_task_id: "scene-inventory",
            tasks_completed: 5,
            failures: 1,
            consecutive_revisions: 0,
            estimated_cost: 0.01,
            last_error: "ArcVellum 在调用模型前发现任务资料超过安全上限，已阻止超长提示词继续消耗额度。",
            stop_reason: "repeated-task-failure",
            failure: {
              schema: "arcvellum/failure-presentation/v1",
              code: "prompt_input_over_budget",
              category: "task_context",
              title: "本次任务携带的资料过多",
              summary: "ArcVellum 在调用模型前发现任务资料超过安全上限，已阻止超长提示词继续消耗额度。",
              impact: "当前任务尚未写入正式作品；已有正文和设定不会丢失。",
              recovery_actions: [{ action_id: "compact-and-resume", label: "精简本次资料并继续", kind: "retry", target: "overview" }],
              retryable: true,
              requires_user_action: false,
              technical_detail: "Pi Worker Prompt v3 lint failed: 67021 > 48000",
            },
          },
        };
      }
      throw new Error(`Unexpected API path: ${path}`);
    });
    const pinia = createPinia();
    setActivePinia(pinia);
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\作品", false);

    const wrapper = mount(AutopilotPanel, { global: { plugins: [pinia] } });
    await flushPromises();

    expect(wrapper.find(".autopilot-failure-card").exists()).toBe(true);
    expect(wrapper.find(".autopilot-failure-card strong").text()).toContain("资料过多");
    expect(wrapper.text()).toContain("精简本次资料并继续");
  });
});
