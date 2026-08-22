import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import OrreryNodeOverlay from "@/features/orrery/OrreryNodeOverlay.vue";
import type { SpatialNarrativeNode } from "@/types/spatial";

describe("OrreryNodeOverlay", () => {
  it("keeps every visible celestial mark while suppressing only colliding copy", () => {
    const nodes = Array.from({ length: 80 }, (_value, index) => sceneNode(index));
    const anchors = Object.fromEntries(nodes.map((node) => [node.node_id, {
      x: 420 + indexJitter(node.order),
      y: 280 + indexJitter(node.order + 11),
      visible: true,
      scale: 0.52,
    }]));
    const wrapper = mount(OrreryNodeOverlay, { props: { nodes, anchors } });

    expect(wrapper.findAll("button.orrery-v3-node")).toHaveLength(nodes.length);
    expect(wrapper.findAll("button.label-suppressed").length).toBeGreaterThan(60);
    expect(wrapper.findAll(".node-luminary")).toHaveLength(nodes.length);
  });
});

function sceneNode(index: number): SpatialNarrativeNode {
  const order = index + 1;
  return {
    node_id: `scene:${String(order).padStart(4, "0")}`,
    type: "scene",
    label: `场景 ${order}`,
    subtitle: "",
    status: index === 0 ? "current" : "planned",
    source_type: "scene",
    source_id: `scene_${String(order).padStart(4, "0")}`,
    navigate: "",
    metrics: { chapter_id: "chapter_0001" },
    order,
    parent_id: null,
    cluster_id: "chapter_0001",
    time_band: order,
    completion_state: index === 0 ? "active" : "planned",
    importance: index === 0 ? 1 : 0.5,
    detail_level: "far",
    world_hint: { surface: "narrative", grammar: "constellation", elevation_band: "midground", occlusion_priority: 1 },
    detail_endpoint: `/node/scene:${order}`,
  };
}

function indexJitter(value: number): number {
  return value % 2 ? 2 : -2;
}
