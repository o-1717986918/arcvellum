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
  { id: "deepseek-v4-flash-free", qualified_id: "opencode/deepseek-v4-flash-free", name: "DeepSeek V4 Flash Free" },
];

function catalog(worker = "opencode/deepseek-v4-flash-free") {
  return {
    ok: true,
    selected_model: worker,
    selected_models: {
      worker,
      advisor: "opencode/deepseek-v4-flash-free",
      steward: "opencode/deepseek-v4-flash-free",
    },
    available_model_count: models.length,
    providers: [
      { id: "deepseek", name: "DeepSeek", connected: true, model_count: 1, models: [models[0]] },
      { id: "opencode", name: "OpenCode Zen", connected: true, model_count: 1, models: [models[1]] },
    ],
    connection_presets: [],
  };
}

describe("settings model selection", () => {
  beforeEach(() => {
    localStorage.clear();
    apiMock.mockReset();
    apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/model-connections/opencode/catalog") return catalog();
      if (path === "/application/info") return { paths: { projects_root: "C:\\ArcVellum\\Works" } };
      if (path === "/model-connections/opencode/model" && init?.method === "PUT") {
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
      "/model-connections/opencode/model",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ model: "deepseek/deepseek-chat", role: "worker" }),
      }),
    );
    expect(wrapper.text()).toContain("正文与审查模型已经更新并会在重启后保持");
    expect(wrapper.find(".role-model-save-state.saved").exists()).toBe(true);
  });
});
