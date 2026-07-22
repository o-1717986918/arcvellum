import { beforeEach, describe, expect, it } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useSpatialWindowsStore } from "@/stores/spatialWindows";
import type { SpatialNarrativeNode } from "@/types/spatial";

const node: SpatialNarrativeNode = {
  node_id: "scene:one",
  type: "scene",
  label: "第一场",
  subtitle: "",
  status: "current",
  source_type: "scene",
  source_id: "scene:one",
  navigate: "",
  metrics: {},
  order: 1,
  parent_id: null,
  cluster_id: "cluster:one",
  time_band: 1,
  importance: 0.8,
  detail_level: "near",
  world_hint: { surface: "narrative", grammar: "stage", elevation_band: "foreground", occlusion_priority: 1 },
  detail_endpoint: "/node/scene:one",
};

describe("spatialWindows", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    Object.defineProperty(window, "innerWidth", { value: 1280, configurable: true });
    Object.defineProperty(window, "innerHeight", { value: 860, configurable: true });
  });

  it("opens independent node windows and brings an existing node forward instead of duplicating it", () => {
    const store = useSpatialWindowsStore();
    store.openNode(node, null, { x: 420, y: 220 });
    const layer = store.windows[0].layer;
    store.openNode(node, null, { x: 620, y: 320 });
    expect(store.windows).toHaveLength(1);
    expect(store.windows[0].layer).toBeGreaterThan(layer);
    expect(store.selectedNodeId).toBe(node.node_id);
  });

  it("keeps different instruments independently addressable and clamps their positions", () => {
    const store = useSpatialWindowsStore();
    store.openInstrument("progress");
    store.openInstrument("reader");
    expect(store.windows.map((item) => item.kind)).toEqual(["progress", "reader"]);
    store.updatePosition("instrument:reader", { left: 10000, top: -100 });
    const reader = store.windows.find((item) => item.id === "instrument:reader");
    expect(reader?.position.left).toBeLessThan(1000);
    expect(reader?.position.top).toBeGreaterThanOrEqual(12);
  });

  it("resizes a window without changing its drag-owned position or violating its compact bounds", () => {
    const store = useSpatialWindowsStore();
    store.openInstrument("decisions");
    const id = "instrument:decisions";
    store.updatePosition(id, { left: 142, top: 126 });
    store.updateSize(id, { width: 330, height: 302 });
    const window = store.windows.find((item) => item.id === id);
    expect(window?.position).toEqual({ left: 142, top: 126 });
    expect(window?.size).toEqual({ width: 330, height: 302 });
    store.updateSize(id, { width: 1, height: 1 });
    expect(store.windows.find((item) => item.id === id)?.size.width).toBeGreaterThanOrEqual(300);
  });

  it("restores a project-local instrument layout without writing into project facts", () => {
    const first = useSpatialWindowsStore();
    first.setScope("project-a::spine", [node]);
    first.openInstrument("rules");
    first.updatePosition("instrument:rules", { left: 236, top: 184 });

    setActivePinia(createPinia());
    const second = useSpatialWindowsStore();
    second.setScope("project-a::spine", [node]);
    const restored = second.windows.find((item) => item.id === "instrument:rules");
    expect(restored?.position).toEqual({ left: 236, top: 184 });
    expect(localStorage.getItem("arcvellum.spatial-window-layout.v1.project-a%3A%3Aspine")).toContain("instrument:rules");
  });

  it("keeps a fresh node window attached to its scene until the user drags it", () => {
    const store = useSpatialWindowsStore();
    store.openNode(node, null, { x: 400, y: 260 });
    const id = "node:scene:one";
    const first = store.windows.find((item) => item.id === id);
    const initialLeft = first?.position.left;
    expect(first?.anchor?.enabled).toBe(true);
    store.syncNodeAnchors({ [node.node_id]: { x: 630, y: 330, visible: true } });
    const attached = store.windows.find((item) => item.id === id);
    expect(attached?.position.left).not.toBe(initialLeft);
    store.updatePosition(id, { left: 120, top: 148 });
    expect(store.windows.find((item) => item.id === id)?.anchor?.enabled).toBe(false);
    store.syncNodeAnchors({ [node.node_id]: { x: 760, y: 400, visible: true } });
    expect(store.windows.find((item) => item.id === id)?.position).toEqual({ left: 120, top: 148 });
  });

  it("exposes top-window operations for keyboard-equivalent controls", () => {
    const store = useSpatialWindowsStore();
    store.openInstrument("progress");
    store.openInstrument("rules");
    const nextId = store.focusNext();
    expect(nextId).toBe("instrument:progress");
    store.toggleActive();
    expect(store.windows.find((item) => item.id === "instrument:progress")?.collapsed).toBe(true);
    store.closeActive();
    expect(store.windows).toHaveLength(1);
  });

  it("keeps the stage legible by moving older windows into the minimized rail", () => {
    const store = useSpatialWindowsStore();
    for (let index = 0; index < 14; index += 1) {
      store.openNode({ ...node, node_id: `scene:${index}`, label: `第${index}场` }, null, { x: 220 + index * 8, y: 180 + index * 4 });
    }
    expect(store.expandedWindows).toHaveLength(12);
    expect(store.minimizedWindows).toHaveLength(2);
    const minimized = store.minimizedWindows[0];
    store.restore(minimized.id);
    expect(store.expandedWindows).toHaveLength(12);
    expect(store.minimizedWindows).toHaveLength(2);
    expect(store.windows.find((item) => item.id === minimized.id)?.collapsed).toBe(false);
  });
});
