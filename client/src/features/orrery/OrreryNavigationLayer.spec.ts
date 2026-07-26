import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OrreryNavigationLayer from "@/features/orrery/OrreryNavigationLayer.vue";
import type { SpatialNarrativeNode, WorldPoint } from "@/types/spatial";

class ResizeObserverStub {
  observe = vi.fn();
  disconnect = vi.fn();
}

function narrativeNode(id: string, label: string, order: number): SpatialNarrativeNode {
  return {
    node_id: id,
    type: "scene",
    label,
    subtitle: `${label}的场景说明`,
    status: order === 1 ? "current" : "planned",
    source_type: "scene",
    source_id: id.replace("scene:", ""),
    navigate: "",
    metrics: {},
    order,
    parent_id: "chapter:chapter_0001",
    cluster_id: "chapter:chapter_0001",
    time_band: order,
    completion_state: order === 1 ? "active" : "planned",
    importance: 0.7,
    detail_level: "near",
    world_hint: { surface: "main", grammar: "spine", elevation_band: "midground", occlusion_priority: 1 },
    detail_endpoint: "/node",
  };
}

describe("OrreryNavigationLayer", () => {
  beforeEach(() => {
    vi.stubGlobal("ResizeObserver", ResizeObserverStub);
  });

  it("forces search-result labels and opens the selected result", async () => {
    const nodes = [
      narrativeNode("scene:scene_0001", "潮声初现", 1),
      narrativeNode("scene:scene_0002", "遗失的信", 2),
    ];
    const points = new Map<string, WorldPoint>([
      [nodes[0].node_id, { x: 0, y: 0, z: 0 }],
      [nodes[1].node_id, { x: 100, y: 40, z: 0 }],
    ]);
    const wrapper = mount(OrreryNavigationLayer, {
      props: {
        nodes,
        points,
        anchors: {
          [nodes[0].node_id]: { x: 100, y: 100, visible: true, scale: 1 },
          [nodes[1].node_id]: { x: 300, y: 120, visible: true, scale: 1 },
        },
      },
    });

    await wrapper.get('button[title^="搜索叙事节点"]').trigger("click");
    await wrapper.get('input[type="search"]').setValue("信");
    await flushPromises();

    expect(wrapper.emitted("forcedLabels")?.at(-1)).toEqual([[nodes[1].node_id]]);
    await wrapper.get(".orrery-search-results button").trigger("click");
    expect(wrapper.emitted("inspect")?.at(-1)?.[0]).toMatchObject({ node_id: nodes[1].node_id });
    wrapper.unmount();
  });

  it("navigates spatially with arrow keys and inspects with Enter", async () => {
    const nodes = [
      narrativeNode("scene:scene_0001", "第一场", 1),
      narrativeNode("scene:scene_0002", "第二场", 2),
    ];
    const points = new Map<string, WorldPoint>([
      [nodes[0].node_id, { x: 0, y: 0, z: 0 }],
      [nodes[1].node_id, { x: 100, y: 0, z: 0 }],
    ]);
    const wrapper = mount(OrreryNavigationLayer, {
      props: { nodes, points, anchors: {}, activeNodeId: nodes[0].node_id },
    });

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    await flushPromises();
    expect(wrapper.emitted("navigate")?.at(-1)?.[0]).toMatchObject({ node_id: nodes[1].node_id });

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await flushPromises();
    expect(wrapper.emitted("inspect")?.at(-1)?.[0]).toMatchObject({ node_id: nodes[1].node_id });
    wrapper.unmount();
  });
});
