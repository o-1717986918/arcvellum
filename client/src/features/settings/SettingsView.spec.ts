import { createPinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.fn();

vi.mock("@/services/api", () => ({
  api: apiMock,
  authorizedFetch: vi.fn(),
  bootstrapDesktopSession: vi.fn(),
  connectEventStream: vi.fn(() => ({ close: vi.fn() })),
  query: vi.fn(() => ""),
}));

vi.mock("@/services/updater", () => ({
  checkForUpdate: vi.fn(),
  installUpdate: vi.fn(),
  restartApplication: vi.fn(),
}));

const models = [
  { id: "deepseek-chat", qualified_id: "deepseek/deepseek-chat", name: "DeepSeek Chat" },
  { id: "deepseek-v4-flash", qualified_id: "deepseek/deepseek-v4-flash", name: "DeepSeek V4 Flash" },
];

function catalog(worker = "deepseek/deepseek-v4-flash") {
  return {
    ok: true,
    selected_model: worker,
    selected_models: {
      worker,
      advisor: "deepseek/deepseek-v4-flash",
      steward: "deepseek/deepseek-v4-flash",
    },
    available_model_count: models.length,
    providers: [
      { id: "deepseek", name: "DeepSeek", connected: true, model_count: 2, models },
    ],
    connection_presets: [],
  };
}

describe("settings model selection", () => {
  beforeEach(() => {
    localStorage.clear();
    apiMock.mockReset();
    apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/model-connections/pi-worker/catalog") return catalog();
      if (path === "/model-connections/pi-worker/thinking" && !init) {
        return { ok: true, preferences: { creative: "medium", project: "xhigh" } };
      }
      if (path === "/model-connections/pi-worker/thinking" && init?.method === "PUT") {
        const { role, level } = JSON.parse(String(init.body));
        return { ok: true, preferences: { creative: role === "creative" ? level : "medium", project: role === "project" ? level : "xhigh" } };
      }
      if (path === "/model-connections/pi-worker/scene-performance" && !init) {
        return { ok: true, preferences: { enabled: true, max_actor_calls: 12 } };
      }
      if (path === "/model-connections/pi-worker/scene-performance" && init?.method === "PUT") {
        return { ok: true, preferences: JSON.parse(String(init.body)) };
      }
      if (path === "/application/info") return { paths: { projects_root: "C:\\ArcVellum\\Works" } };
      if (path === "/model-connections/pi-worker/model" && init?.method === "PUT") {
        const payload = JSON.parse(String(init.body));
        return { catalog: catalog(payload.model), runtime: { pending_roles: [] } };
      }
      throw new Error(`unexpected path: ${path}`);
    });
  });

  it("persists a role model as soon as the selection changes", async () => {
    const { default: SettingsView } = await import("./SettingsView.vue");
    const wrapper = mount(SettingsView, {
      global: { plugins: [createPinia()] },
    });
    await flushPromises();

    await wrapper.findAll(".role-model-list select")[0].setValue("deepseek/deepseek-chat");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      "/model-connections/pi-worker/model",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ model: "deepseek/deepseek-chat", role: "worker" }),
      }),
    );
    expect(wrapper.text()).toContain("正文与审查模型已经更新并会在重启后保持");
    expect(wrapper.find(".role-model-save-state.saved").exists()).toBe(true);
  });

  it("shows independent levels and persists a changed Project Agent level", async () => {
    const { default: SettingsView } = await import("./SettingsView.vue");
    const wrapper = mount(SettingsView, { global: { plugins: [createPinia()] } });
    await flushPromises();

    expect((wrapper.find('select[aria-label="顶层项目 Agent思考强度"]').element as HTMLSelectElement).value).toBe("xhigh");
    expect((wrapper.find('select[aria-label="创作 Agent思考强度"]').element as HTMLSelectElement).value).toBe("medium");
    await wrapper.find('select[aria-label="顶层项目 Agent思考强度"]').setValue("high");
    await flushPromises();

    expect(apiMock).toHaveBeenCalledWith(
      "/model-connections/pi-worker/thinking",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ role: "project", level: "high" }) }),
    );
    expect(wrapper.text()).toContain("思考强度已保存");
  });

  it("restores the confirmed level when saving fails", async () => {
    const { default: SettingsView } = await import("./SettingsView.vue");
    const wrapper = mount(SettingsView, { global: { plugins: [createPinia()] } });
    await flushPromises();
    apiMock.mockRejectedValueOnce(new Error("保存中断"));

    await wrapper.find('select[aria-label="创作 Agent思考强度"]').setValue("high");
    await flushPromises();

    expect((wrapper.find('select[aria-label="创作 Agent思考强度"]').element as HTMLSelectElement).value).toBe("medium");
    expect(wrapper.text()).toContain("保存中断");
  });

  it("persists scene performance controls", async () => {
    const { default: SettingsView } = await import("./SettingsView.vue");
    const wrapper = mount(SettingsView, { global: { plugins: [createPinia()] } });
    await flushPromises();
    await wrapper.find('select[aria-label="场景表演 Agent"]').setValue("false");
    await flushPromises();
    expect(apiMock).toHaveBeenCalledWith(
      "/model-connections/pi-worker/scene-performance",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ enabled: false, max_actor_calls: 12 }) }),
    );
  });
});
