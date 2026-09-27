import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  promptCatalog: vi.fn(), promptHistory: vi.fn(), savePromptLayer: vi.fn(),
  activatePromptVersion: vi.fn(), resetPromptLayer: vi.fn(), previewPromptLayers: vi.fn(),
}));
vi.mock("./services/settingsClient", () => ({ settingsClient: api }));

describe("prompt workbench", () => {
  it("loads the selected scope before editing so project text cannot leak into a global version", async () => {
    api.promptCatalog.mockImplementation(async (root: string) => ({ layers: [{
      layer_id: "scene.creator.identity", responsibility: "identity", purpose: "主创文学使命",
      source: root ? "project" : "global", version: "1", owner: "Studio", editable: true,
      digest: "digest-1", usage_status: "active",
      default_text: "随包默认", effective_text: root ? "作品指引" : "全局指引",
    }], formal_assets: [] }));
    api.promptHistory.mockResolvedValue({ versions: [] });
    const { default: PromptWorkbench } = await import("./PromptWorkbench.vue");
    const wrapper = mount(PromptWorkbench, { props: { projectRoot: "C:/Books/Work" } });
    await flushPromises();
    expect(api.promptCatalog).toHaveBeenCalledWith("");
    expect((wrapper.findAll("textarea")[1].element as HTMLTextAreaElement).value).toBe("全局指引");
    api.resetPromptLayer.mockResolvedValue({ effective: { source: "package" } });
    await wrapper.findAll(".button-row button")[1].trigger("click");
    await flushPromises();
    expect(api.resetPromptLayer).toHaveBeenCalledWith("scene.creator.identity", {
      scope: "global", project_root: "", expected_digest: "digest-1",
    });
    await wrapper.find("select[aria-label='提示词范围']").setValue("project");
    await flushPromises();
    expect(api.promptCatalog).toHaveBeenCalledWith("C:/Books/Work");
    expect((wrapper.findAll("textarea")[1].element as HTMLTextAreaElement).value).toBe("作品指引");
    await wrapper.find("select[aria-label='提示词范围']").setValue("global");
    await flushPromises();
    expect((wrapper.findAll("textarea")[1].element as HTMLTextAreaElement).value).toBe("全局指引");
  });

  it("edits literary guidance, activates history, and keeps protocol read only", async () => {
    api.promptCatalog.mockResolvedValue({ layers: [
      { layer_id: "scene.creator.identity", responsibility: "identity", purpose: "主创文学使命",
        source: "package", version: "1", owner: "Studio", editable: true,
        digest: "digest-2", usage_status: "active",
        default_text: "旧指引", effective_text: "旧指引" },
      { layer_id: "scene.protocol", responsibility: "protocol", purpose: "固定权限",
        source: "package", version: "1", owner: "Engine", editable: false,
        digest: "digest-3", usage_status: "active",
        default_text: "协议", effective_text: "协议" },
    ], formal_assets: [] });
    api.promptHistory.mockResolvedValue({ versions: [{ version: 1, text: "旧指引", created_at: "now" }] });
    api.savePromptLayer.mockResolvedValue({ saved: { version: 2 } });
    api.activatePromptVersion.mockResolvedValue({ activated: { version: 1 } });
    const { default: PromptWorkbench } = await import("./PromptWorkbench.vue");
    const wrapper = mount(PromptWorkbench, { props: { projectRoot: "C:/Books/Work" } });
    await flushPromises();
    await wrapper.findAll("textarea")[1].setValue("请让读者先误认这场沉默");
    await wrapper.find(".primary-button").trigger("click");
    await flushPromises();
    expect(api.savePromptLayer).toHaveBeenCalledWith("scene.creator.identity", {
      scope: "global", project_root: "", text: "请让读者先误认这场沉默", expected_digest: "digest-2",
    });
    await wrapper.find(".prompt-version-list button").trigger("click");
    await flushPromises();
    expect(api.activatePromptVersion).toHaveBeenCalledWith("scene.creator.identity", {
      scope: "global", project_root: "", version: 1, expected_digest: "digest-2",
    });
    await wrapper.find("select[aria-label='提示词层']").setValue("scene.protocol");
    await flushPromises();
    expect((wrapper.findAll("textarea")[1].element as HTMLTextAreaElement).readOnly).toBe(true);
    expect((wrapper.find(".primary-button").element as HTMLButtonElement).disabled).toBe(true);
  });
});
