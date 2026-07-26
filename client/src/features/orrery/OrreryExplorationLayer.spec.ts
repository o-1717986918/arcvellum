import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import OrreryExplorationLayer from "@/features/orrery/OrreryExplorationLayer.vue";
import type { SpatialNarrativeNode } from "@/types/spatial";

function node(id: string, order: number): SpatialNarrativeNode {
  return {
    node_id: id, type: "scene", label: id, subtitle: "说明", status: "planned", source_type: "scene",
    source_id: id, navigate: "", metrics: {}, order, parent_id: null, cluster_id: "chapter:1",
    time_band: order, completion_state: "planned", importance: 0.5, detail_level: "near",
    world_hint: { surface: "main", grammar: "spine", elevation_band: "midground", occlusion_priority: 1 },
    detail_endpoint: "/detail",
  };
}

describe("OrreryExplorationLayer", () => {
  it("switches heat lenses and replays the current semantic route", async () => {
    vi.useFakeTimers();
    const nodes = [node("scene:1", 1), node("scene:2", 2)];
    const wrapper = mount(OrreryExplorationLayer, {
      props: { nodes, anchors: {}, level: "scene", heatLens: "", comparedNodeIds: [], bookmarks: [] },
    });
    await wrapper.get("select").setValue("tension");
    expect(wrapper.emitted("heatLens")?.at(-1)).toEqual(["tension"]);
    await wrapper.get('button[title^="沿当前叙事"]').trigger("click");
    expect(wrapper.emitted("replay")?.[0]?.[0]).toMatchObject({ node_id: "scene:1" });
    vi.advanceTimersByTime(1100);
    expect(wrapper.emitted("replay")?.at(-1)?.[0]).toMatchObject({ node_id: "scene:2" });
    wrapper.unmount();
    vi.useRealTimers();
  });

  it("renders project view bookmarks and comparison cards", async () => {
    const nodes = [node("scene:1", 1)];
    const wrapper = mount(OrreryExplorationLayer, {
      props: {
        nodes, anchors: {}, level: "scene", heatLens: "review",
        comparedNodeIds: ["scene:1"],
        bookmarks: [{
          id: "view-1", projectRoot: "work", label: "场景焦点", level: "scene", focus: "scene_0001",
          grammar: "spine", timeCursor: 1, timeWindow: 3, heatLens: "review", nodeId: "scene:1", createdAt: "",
        }],
      },
    });
    expect(wrapper.text()).toContain("并列观察");
    await wrapper.get('button[title="查看视图书签"]').trigger("click");
    expect(wrapper.text()).toContain("场景焦点");
    expect(wrapper.text()).toContain("场景 · 脊柱");
  });

  it("emits a deterministic comparison set after lasso selection", async () => {
    const nodes = [node("scene:1", 1), node("scene:2", 2)];
    const wrapper = mount(OrreryExplorationLayer, {
      props: {
        nodes,
        anchors: {
          "scene:1": { x: 30, y: 30, visible: true, scale: 1 },
          "scene:2": { x: 180, y: 180, visible: true, scale: 1 },
        },
        level: "scene", heatLens: "", comparedNodeIds: [], bookmarks: [],
      },
    });
    const root = wrapper.get(".orrery-exploration-layer");
    Object.defineProperty(root.element, "setPointerCapture", { value: vi.fn() });
    Object.defineProperty(root.element, "releasePointerCapture", { value: vi.fn() });
    vi.spyOn(root.element, "getBoundingClientRect").mockReturnValue({
      x: 0, y: 0, left: 0, top: 0, right: 300, bottom: 300, width: 300, height: 300,
      toJSON: () => ({}),
    });

    await wrapper.get('button[title^="框选节点"]').trigger("click");
    await root.trigger("pointerdown", { button: 0, pointerId: 7, clientX: 10, clientY: 10 });
    await root.trigger("pointermove", { pointerId: 7, clientX: 80, clientY: 80 });
    await root.trigger("pointerup", { pointerId: 7, clientX: 80, clientY: 80 });

    expect(wrapper.emitted("compare")?.at(-1)).toEqual([["scene:1"]]);
  });
});
