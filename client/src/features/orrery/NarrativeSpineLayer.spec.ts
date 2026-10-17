import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import NarrativeSpineLayer from "./NarrativeSpineLayer.vue";
import type { SpatialNarrativeProjection } from "@/types/spatial";

afterEach(() => vi.unstubAllGlobals());

describe("relationship rendering ownership", () => {
  it("draws each character connection once while retaining every canon evidence connection", () => {
    vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
    const nodes = ["scene", "character", "canon"].map((type, order) => ({ node_id: type, type, order,
      source_id: type, parent_id: null, metrics: { chapter_id: "one" }, completion_state: "planned" }));
    const edges = Array.from({ length: 80 }, (_, i) => ({ edge_id: String(i), source: "character", target: "scene",
      type: "character", relation_family: "character-scene" }));
    edges.push({ edge_id: "canon", source: "scene", target: "canon", type: "canon", relation_family: "canon-state-impact" });
    const projection = { level: "book", nodes, edges, relation_profiles: [] } as unknown as SpatialNarrativeProjection;
    const anchors = Object.fromEntries(nodes.map((node, i) => [node.node_id, { x: 100 + i * 30, y: 100, scale: 0.8, visible: true }]));
    const wrapper = mount(NarrativeSpineLayer, { props: { projection, anchors } });
    const sumEdges = (selector: string) => wrapper.findAll(selector).reduce((sum, item) => sum + Number(item.attributes("data-edge-count")), 0);
    expect(sumEdges(".narrative-character-thread")).toBe(80);
    expect(sumEdges(".narrative-evidence-flow")).toBe(1);
    expect(wrapper.find('[data-node-type="character"]').exists()).toBe(false);
    wrapper.unmount();
  });
});
