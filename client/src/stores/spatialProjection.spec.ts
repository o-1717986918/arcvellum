import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SpatialNarrativeProjection, SpatialNarrativeProjectionPatch } from "@/types/spatial";

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

function patch(base: string, target: string, sequence = 1): SpatialNarrativeProjectionPatch {
  return {
    ok: true,
    schema: "arcvellum/narrative-projection-patch/v1",
    base_revision: base,
    target_revision: target,
    sequence,
    meta: { summary: { changed: true } },
    meta_remove: [],
    nodes: { upsert: [], remove: [], order: [] },
    edges: { upsert: [], remove: [], order: [] },
    delta: {
      initial: false,
      added_nodes: [],
      removed_nodes: [],
      updated_nodes: [],
      added_edges: [],
      removed_edges: [],
      updated_edges: [],
    },
    motion_events: [],
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

    streamCallback?.("narrative.v4.projection", projection("projection-1", 1) as unknown as Record<string, unknown>);

    expect(store.projection).toBe(identity);
  });

  it("accepts a new chapter focus even when the narrative revision is unchanged", async () => {
    const initial = projection("projection-1");
    const focused = {
      ...projection("projection-1", 1),
      level: "chapter" as const,
      focus: "chapter_0050",
      focus_scope: {
        level: "chapter" as const,
        focus_id: "chapter_0050",
        anchor_node_ids: ["chapter:chapter_0050"],
        context_node_ids: [],
        chapter_ids: ["chapter_0050"],
        scene_ids: [],
        character_ids: [],
      },
    };
    apiMock.mockResolvedValueOnce(initial).mockResolvedValueOnce(focused);
    const { useSpatialProjectionStore } = await import("./spatialProjection");
    const store = useSpatialProjectionStore();
    await store.open(initial.project_root);
    const identity = store.projection;

    await store.setView({ level: "chapter", focus: "chapter_0050" });

    expect(store.projection).not.toBe(identity);
    expect(store.projection?.level).toBe("chapter");
    expect(store.projection?.focus).toBe("chapter_0050");
  });

  it("enters a formal character focus and returns through focus history", async () => {
    const initial = projection("projection-1");
    const characterFocused = {
      ...projection("projection-2", 1),
      level: "character" as const,
      focus: "character:lin",
      focus_scope: {
        level: "character" as const,
        focus_id: "lin",
        anchor_node_ids: ["character:lin"],
        context_node_ids: [],
        chapter_ids: ["chapter_0001"],
        scene_ids: ["scene_0001"],
        character_ids: ["lin"],
      },
    };
    apiMock.mockResolvedValueOnce(initial).mockResolvedValueOnce(characterFocused).mockResolvedValueOnce(initial);
    const { useSpatialProjectionStore } = await import("./spatialProjection");
    const store = useSpatialProjectionStore();
    await store.open(initial.project_root);

    await store.setView({ level: "character", focus: "character:lin" });

    expect(store.level).toBe("character");
    expect(store.canGoBack).toBe(true);
    await store.goBack();
    expect(store.level).toBe("book");
    expect(store.focus).toBe("");
    expect(store.canGoBack).toBe(false);
  });

  it("replaces projection identity when narrative evidence changes", async () => {
    const initial = projection("projection-1");
    apiMock.mockResolvedValue(initial);
    const { useSpatialProjectionStore } = await import("./spatialProjection");
    const store = useSpatialProjectionStore();
    await store.open(initial.project_root);
    const identity = store.projection;

    streamCallback?.("narrative.v4.projection", projection("projection-2", 1) as unknown as Record<string, unknown>);

    expect(store.projection).not.toBe(identity);
    expect(store.projection?.projection_revision).toBe("projection-2");
  });

  it("applies a patch only to its exact projection base", async () => {
    const initial = projection("projection-1");
    apiMock.mockResolvedValue(initial);
    const { useSpatialProjectionStore } = await import("./spatialProjection");
    const store = useSpatialProjectionStore();
    await store.open(initial.project_root);

    streamCallback?.("narrative.v4.patch", patch("projection-1", "projection-2") as unknown as Record<string, unknown>);

    expect(store.projection?.projection_revision).toBe("projection-2");
    expect(store.projection?.summary).toEqual({ changed: true });
  });

  it("refreshes from the snapshot endpoint when a patch base does not match", async () => {
    const initial = projection("projection-1");
    const recovered = projection("projection-3", 3);
    apiMock.mockResolvedValueOnce(initial).mockResolvedValueOnce(recovered);
    const { useSpatialProjectionStore } = await import("./spatialProjection");
    const store = useSpatialProjectionStore();
    await store.open(initial.project_root);

    streamCallback?.("narrative.v4.patch", patch("unknown-base", "projection-2") as unknown as Record<string, unknown>);

    await vi.waitFor(() => expect(store.projection?.projection_revision).toBe("projection-3"));
    expect(apiMock).toHaveBeenCalledTimes(2);
  });
});
