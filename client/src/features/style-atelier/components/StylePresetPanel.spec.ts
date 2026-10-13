import { flushPromises, mount } from "@vue/test-utils";
import { describe, it, expect, vi } from "vitest";
import StylePresetPanel from "./StylePresetPanel.vue";
const client = vi.hoisted(() => ({ presets: vi.fn(), recalculatePreset: vi.fn(), savePresets: vi.fn() }));
vi.mock("../services/stylometryClient", () => ({ stylometryClient: client }));
function catalog(version = "old", title = "世界与风俗") {
  return { revision: 1, enabled: true, default_preset_id: "world-narration", reference_catalog: { references: [] },
    presets: [{ preset_id: "world-narration", title, literary_intent: "展开世界", narrative_modes: [],
      reference_ids: ["S01", "S02"], stylometry_version_id: version, active: true, combine: "append", usage: "guide" }] };
}
describe("recompute selected complete references", () => {
  it("publishes the recalculated version to the parameter panel", async () => {
    client.presets.mockResolvedValue(catalog()); client.recalculatePreset.mockResolvedValue(catalog("new"));
    const wrapper = mount(StylePresetPanel, { props: { projectRoot: "one", versions: [], canRecalculate: true } });
    await flushPromises();
    await wrapper.findAll("button").find(button => button.text() === "按所选参照重新统计")!.trigger("click");
    await flushPromises();
    expect(client.recalculatePreset).toHaveBeenCalledWith("one", "world-narration", 1);
    expect(wrapper.emitted("select")?.at(-1)).toEqual(["world-narration", "new"]);
    expect(wrapper.text()).toContain("已有交易沿用原快照");
  });
  it("an old project's pending calculation does not replace a newly selected project", async () => {
    let finish: (value: object) => void = () => {};
    client.presets.mockResolvedValue(catalog()); client.recalculatePreset.mockReturnValue(new Promise(resolve => { finish = resolve; }));
    const wrapper = mount(StylePresetPanel, { props: { projectRoot: "one", versions: [], canRecalculate: true } });
    await flushPromises();
    await wrapper.findAll("button").find(button => button.text() === "按所选参照重新统计")!.trigger("click");
    client.presets.mockResolvedValue(catalog("other", "另一部作品"));
    await wrapper.setProps({ projectRoot: "two" }); await flushPromises();
    finish(catalog("new")); await flushPromises();
    expect(wrapper.text()).toContain("另一部作品"); expect(wrapper.emitted("select")).toBeUndefined();
  });
});
