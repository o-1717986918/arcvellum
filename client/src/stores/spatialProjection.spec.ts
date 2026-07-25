import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SpatialNarrativeProjection } from "@/types/spatial";

const apiMock = vi.fn();
let streamCallback: ((event: string, data: Record<string, unknown>) => void) | null = null;

vi.mock("@/services/api", () => ({
  api: apiMock,
  query: (values: Record<string, string | number | undefined>) => {
    const params = new URLSearchParams();
    Object.entries(values).forEach(([key, value]) => {
      if (value !== undefined && value !== "") params.set(key, String(value));
    });
    return params.toString();
  },
  connectEventStream: (_path: string, callback: (event: string, data: Record<string, unknown>) => void) => {
    streamCallback = callback;
    return { close: vi.fn() };
  },
}));

function projection(revision: string, sequence = 0): SpatialNarrativeProjection {
  return {
    ok: true,
    schema: "arcvellum/narrative-projection/v3",
    project_root: "C:\\ArcVellum\\潮汐之后",
    generated_at: "2026-07-25T00:00:00Z",
    revision,
    projection_revision: revision,
    sequence,
    source_revisions: {},
    level: "book",
    focus: "",
    focus_scope: {
      level: "book",
      focus_id: "",
      anchor_node_ids: [],
      context_node_ids: [],
      chapter_ids: [],
      scene_ids: [],
      character_ids: [],
    },
    relation_profiles: [],
    character_references: [],
    spatial_grammar: "spine",
    available_grammars: ["spine"],
    layout_seed: "seed",
    summary: {},
    nodes: [],
    edges: [],
    clusters: [],
    layout_hints: {},
    lod_summary: { near: 0, mid: 0, far: 0 },
    timeline: [],
    delta: {
      initial: true,
      added_nodes: [],
      removed_nodes: [],
      updated_nodes: [],
      added_edges: [],
      removed_edges: [],
      updated_edges: [],
    },
    motion_events: [],
    legend: [],
    accessibility_summary: "",
  };
}

describe("spatial projection store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    apiMock.mockReset();
    streamCallback = null;
  });

  it("keeps projection identity when a stream repeats the same semantic revision", async () => {
    const initial = projection("projection-1");
    apiMock.mockResolvedValue(initial);
    const { useSpatialProjectionStore } = await import("./spatialProjection");
    const store = useSpatialProjectionStore();
    await store.open(initial.project_root);
    const identity = store.projection;

    streamCallback?.("narrative.v3.projection", projection("projection-1", 1) as unknown as Record<string, unknown>);

    expect(store.projection).toBe(identity);
  });

  it("replaces projection identity when narrative evidence changes", async () => {
    const initial = projection("projection-1");
    apiMock.mockResolvedValue(initial);
    const { useSpatialProjectionStore } = await import("./spatialProjection");
    const store = useSpatialProjectionStore();
    await store.open(initial.project_root);
    const identity = store.projection;

    streamCallback?.("narrative.v3.projection", projection("projection-2", 1) as unknown as Record<string, unknown>);

    expect(store.projection).not.toBe(identity);
    expect(store.projection?.projection_revision).toBe("projection-2");
  });
});
