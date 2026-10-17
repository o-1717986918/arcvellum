import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import OrreryNodeOverlay from "@/features/orrery/OrreryNodeOverlay.vue";
import type { SpatialNarrativeNode } from "@/types/spatial";

describe("OrreryNodeOverlay", () => {
  it("avoids overlapping copy in a small scene cluster without removing any node", async () => {
    const nodes = Array.from({ length: 20 }, (_, i) => sceneNode(i));
    const anchors = Object.fromEntries(nodes.map((node) => [node.node_id, { x: 400, y: 300, visible: true, scale: 0.7 }]));
    // Historical motion must not force every nearby label back into the cluster.
    const motionEvents = nodes.map((node) => ({ type: "formal", node_id: node.node_id, label: "正文已形成" }));
    const wrapper = mount(OrreryNodeOverlay, { props: { nodes, anchors, motionEvents } });
    expect(wrapper.findAll("button")).toHaveLength(20);
    expect(wrapper.findAll(".node-copy").length).toBeLessThan(5);
    const mark = wrapper.find("button.mark-only");
    await mark.trigger("focus");
    expect(mark.find(".node-copy").exists()).toBe(true);
    await mark.trigger("click");
    expect(wrapper.emitted("select")?.[0][0]).toMatchObject({ node_id: mark.attributes("data-node-id") });
    await wrapper.setProps({ showAllLabels: true });
    expect(wrapper.findAll(".node-copy")).toHaveLength(20);
    wrapper.unmount();
  });
  it("batches dense marks without losing pointer selection or native keyboard access", async () => {
    const nodes = Array.from({ length: 200 }, (_, i) => sceneNode(i));
    const anchors = Object.fromEntries(nodes.map((n) => [n.node_id, { x: 400, y: 300, visible: true, scale: 0.5 }]));
    const wrapper = mount(OrreryNodeOverlay, { props: { nodes, anchors } });
    expect(wrapper.findAll("button")).toHaveLength(200);
    const mark = wrapper.find(".orrery-node-marks circle");
    const id = mark.attributes("data-node-id");
    await mark.trigger("click");
    expect(wrapper.emitted("select")?.[0][0]).toMatchObject({ node_id: id });
    const button = wrapper.find(`button[data-node-id="${id}"]`);
    expect(button.classes()).toContain("batched-mark");
    await button.trigger("focus");
    expect(button.classes()).not.toContain("batched-mark");
    expect(button.find(".node-copy").exists()).toBe(true);
    await button.trigger("click");
    expect(wrapper.emitted("select")?.[1][0]).toMatchObject({ node_id: id });
    await wrapper.setProps({ heatLens: "review" });
    expect(wrapper.findAll("button.batched-mark")).toHaveLength(0);
    expect(wrapper.find(".orrery-node-marks").exists()).toBe(false);
    await wrapper.setProps({ heatLens: "" });
    expect(wrapper.findAll("button.batched-mark").length).toBeGreaterThan(100);
    wrapper.unmount();
  });
  it("avoids dense chapter copy while preserving explicit selection and accurate anchor movement", async () => {
    const nodes = Array.from({ length: 80 }, (_, i) => ({ ...sceneNode(i), type: "chapter" as const }));
    const anchors = Object.fromEntries(nodes.map((node) => [node.node_id, { x: 420, y: 280, visible: true, scale: 0.5 }]));
    const wrapper = mount(OrreryNodeOverlay, { props: { nodes, anchors, selectedNodeId: nodes[79].node_id } });
    expect(wrapper.findAll("button")).toHaveLength(80);
    expect(wrapper.findAll(".node-copy").length).toBeLessThan(10);
    expect(wrapper.find("button.selected .node-copy").exists()).toBe(true);
    const before = wrapper.find("button.selected").attributes("style");
    await wrapper.setProps({ anchors: Object.fromEntries(Object.entries(anchors).map(([id, a]) => [id, { ...a, x: a.x + 20 }])) });
    expect(wrapper.find("button.selected").attributes("style")).not.toBe(before);
    expect(wrapper.find("button.selected").attributes("style")).toContain("440px");
    wrapper.unmount();
  });
  it("keeps every mark selectable and keyboard-addressable without mounting suppressed copy", async () => {
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
    expect(wrapper.findAll(".mark-only").length).toBeGreaterThan(60);
    expect(wrapper.findAll(".node-copy").length).toBeLessThan(20);
    const mark = wrapper.find("button.mark-only");
    const label = mark.attributes("aria-label");
    await mark.trigger("click");
    expect(wrapper.emitted("select")?.[0][0]).toMatchObject({ label: mark.attributes("title") });
    await mark.trigger("focus");
    expect(mark.find(".node-copy").exists()).toBe(true);
    expect(mark.attributes("aria-label")).toBe(label);
    await mark.trigger("blur");
    expect(mark.find(".node-copy").exists()).toBe(false);
    await wrapper.setProps({ showAllLabels: true });
    expect(wrapper.findAll(".node-copy")).toHaveLength(nodes.length);
    wrapper.unmount();
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
