import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  promptCatalog: vi.fn(), promptHistory: vi.fn(), savePromptLayer: vi.fn(),
  activatePromptVersion: vi.fn(), resetPromptLayer: vi.fn(), previewPromptLayers: vi.fn(),
}));
vi.mock("./services/settingsClient", () => ({ settingsClient: api }));

describe("prompt workbench", () => {
  it("opens the matching prompt after a delayed catalog arrives for an existing search", async () => {
    let deliver: (value: object) => void = () => {};
    api.promptCatalog.mockReturnValue(new Promise(resolve => { deliver = resolve; }));
    api.promptHistory.mockResolvedValue({ versions: [] });
    const { default: PromptWorkbench } = await import("./PromptWorkbench.vue");
    const wrapper = mount(PromptWorkbench, { props: { projectRoot: "C:/Books/Work" } });
    await wrapper.find("input[aria-label='搜索提示词']").setValue("scene.v2.creator.selection");
    deliver({ layers: [{ layer_id: "scene.v2.creator.selection", responsibility: "stage", purpose: "取舍",
      source: "package", version: "1", editable: true, flow_stage: "scene.selection", default_text: "取舍", effective_text: "取舍" }],
      formal_assets: [], flow_tree: [{ id: "scene", label: "场景", children: [{ id: "scene.selection", label: "候选", children: [
        { id: "scene.v2.creator.selection", layer_id: "scene.v2.creator.selection", label: "取舍" },
      ] }] }] });
    await flushPromises();
    expect(wrapper.find(".prompt-tree-leaf").text()).toContain("scene.v2.creator.selection");
    wrapper.unmount();
  });
  it("loads the selected scope before editing so project text cannot leak into a global version", async () => {
    api.promptCatalog.mockImplementation(async (root: string) => ({ layers: [{
      layer_id: "scene.creator.identity", responsibility: "identity", purpose: "主创文学使命",
      source: root ? "project" : "global", version: "1", owner: "Studio", editable: true,
      digest: "digest-1", usage_status: "active", flow_stage: "scene.entry",
      default_text: "随包默认", effective_text: root ? "作品指引" : "全局指引",
    }], formal_assets: [], flow_tree: [{ id: "scene", label: "04 · 场景创作", children: [
      { id: "scene.entry", label: "入场与意图", children: [
        { id: "scene.creator.identity", layer_id: "scene.creator.identity", label: "主创文学使命" },
      ] },
    ] }] }));
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
        digest: "digest-2", usage_status: "active", flow_stage: "scene.entry",
        default_text: "旧指引", effective_text: "旧指引" },
      { layer_id: "scene.protocol", responsibility: "protocol", purpose: "固定权限",
        source: "package", version: "1", owner: "Engine", editable: false,
        digest: "digest-3", usage_status: "active", flow_stage: "scene.entry",
        default_text: "协议", effective_text: "协议" },
    ], formal_assets: [], flow_tree: [{ id: "scene", label: "04 · 场景创作", children: [
      { id: "scene.entry", label: "入场与意图", children: [
        { id: "scene.creator.identity", layer_id: "scene.creator.identity", label: "主创文学使命" },
        { id: "scene.protocol", layer_id: "scene.protocol", label: "固定权限" },
      ] },
    ] }] });
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
    expect(wrapper.findAll(".prompt-tree-leaf")).toHaveLength(2);
    await wrapper.findAll(".prompt-tree-leaf")[1].trigger("click");
    await flushPromises();
    expect(wrapper.find(".prompt-fixed-template pre").text()).toBe("协议");
    expect(wrapper.findAll("textarea")).toHaveLength(0);
    expect(wrapper.find(".primary-button").exists()).toBe(false);
    await wrapper.find(".prompt-tree-stage").trigger("click");
    expect(wrapper.findAll(".prompt-tree-leaf")).toHaveLength(0);
    await wrapper.find(".prompt-tree-stage").trigger("click");
    await wrapper.find("select[aria-label='提示词职责筛选']").setValue("protocol");
    expect(wrapper.findAll(".prompt-tree-leaf")).toHaveLength(1);
  });
});
