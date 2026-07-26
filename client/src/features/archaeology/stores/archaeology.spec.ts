import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.fn();
const streamCloseMock = vi.fn();
let streamListener: ((event: string, data: Record<string, unknown>) => void) | null = null;
const connectEventStreamMock = vi.fn(
  (_path: string, listener: (event: string, data: Record<string, unknown>) => void) => {
    streamListener = listener;
    return { close: streamCloseMock };
  },
);

vi.mock("@/services/api", () => ({
  api: apiMock,
  connectEventStream: connectEventStreamMock,
  query: (values: Record<string, string>) => new URLSearchParams(values).toString(),
}));

describe("Project Archaeology store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    apiMock.mockReset();
    connectEventStreamMock.mockClear();
    streamCloseMock.mockClear();
    streamListener = null;
    window.localStorage.clear();
  });

  it("loads a safe catalog and selects the first imported work", async () => {
    apiMock.mockImplementation(async (path: string) => {
      if (path === "/archaeology/options") return optionsFixture();
      if (path.startsWith("/archaeology/imports?")) return catalogFixture();
      if (path.startsWith("/archaeology/workbench/legacy-work")) return workbenchFixture();
      throw new Error(`unexpected path: ${path}`);
    });
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\潮线", false);
    const { useArchaeologyStore } = await import("./archaeology");
    const store = useArchaeologyStore();

    await store.load();

    expect(store.options?.modes).toHaveLength(4);
    expect(store.selectedWorkId).toBe("legacy-work");
    expect(store.workbench?.status.current_step).toBe("chunk-extraction-agent-task");
    expect(apiMock).toHaveBeenCalledWith(
      expect.stringContaining("project_root=C%3A%5CArcVellum%5C%E6%BD%AE%E7%BA%BF"),
    );
  });

  it("runs the current source-ingest task and observes the existing Worker", async () => {
    apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/archaeology/options") return optionsFixture();
      if (path.startsWith("/archaeology/imports?")) return catalogFixture();
      if (path.startsWith("/archaeology/workbench/legacy-work")) return workbenchFixture();
      if (path === "/worker/run" && init?.method === "POST") {
        expect(JSON.parse(String(init.body))).toMatchObject({
          project_root: "C:\\ArcVellum\\潮线",
          route: "source-ingest",
          runtime: "opencode",
        });
        return { job_id: "job-archaeology", status: "queued", revision: 1 };
      }
      throw new Error(`unexpected path: ${path}`);
    });
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\潮线", false);
    const { useArchaeologyStore } = await import("./archaeology");
    const store = useArchaeologyStore();
    await store.load();

    await store.runNextTask();

    expect(store.job?.job_id).toBe("job-archaeology");
    expect(connectEventStreamMock).toHaveBeenCalledWith(
      "/worker/jobs/job-archaeology/stream",
      expect.any(Function),
      expect.any(Function),
    );
    streamListener?.("runtime.delta", {
      sequence: 2,
      event: "runtime.delta",
      at: "2026-07-26T10:00:00Z",
      data: { text: "working" },
    });
    expect(store.events.at(-1)?.event).toBe("runtime.delta");
  });

  it("does not launch another task after the formal route is ready", async () => {
    const ready = workbenchFixture();
    ready.status.status = "ready";
    ready.status.current_step = "ready";
    apiMock.mockImplementation(async (path: string) => {
      if (path === "/archaeology/options") return optionsFixture();
      if (path.startsWith("/archaeology/imports?")) return catalogFixture();
      if (path.startsWith("/archaeology/workbench/legacy-work")) return ready;
      throw new Error(`unexpected path: ${path}`);
    });
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\潮线", false);
    const { useArchaeologyStore } = await import("./archaeology");
    const store = useArchaeologyStore();
    await store.load();

    await store.runNextTask();

    expect(apiMock).not.toHaveBeenCalledWith("/worker/run", expect.anything());
  });
});

function optionsFixture() {
  return {
    schema: "arcvellum/project-archaeology-options/v1",
    modes: [
      { id: "continuation", label: "续写基础", intent: "恢复未结承诺。" },
      { id: "rewrite", label: "改写重构", intent: "识别结构问题。" },
      { id: "adaptation", label: "媒介改编", intent: "识别场景化事件。" },
      { id: "analysis", label: "作品分析", intent: "只形成分析。" },
    ],
    supported_extensions: [".txt", ".md", ".markdown", ".docx"],
    max_source_bytes: 25 * 1024 * 1024,
  };
}

function catalogFixture() {
  return {
    schema: "arcvellum/project-archaeology-catalog/v1",
    count: 1,
    imports: [{
      work_id: "legacy-work",
      title: "旧作",
      mode: optionsFixture().modes[0],
      source_count: 1,
      chunk_count: 1,
      status: stateFixture(),
      recovery: recoveryFixture(),
    }],
    recovery: [],
    revision: "catalog-revision",
  };
}

function workbenchFixture() {
  return {
    schema: "arcvellum/project-archaeology-workbench/v1",
    work_id: "legacy-work",
    title: "旧作",
    mode: optionsFixture().modes[0],
    status: stateFixture(),
    journey: [
      { id: "source", label: "源文本保全", status: "complete", count: 1 },
      { id: "chunks", label: "分块理解", status: "active", count: 0 },
    ],
    sources: [{
      source_id: "source-one",
      title: "旧作",
      filename: "旧作.md",
      media_type: "text/markdown",
      extraction_method: "markdown",
      content_sha256: "sha256:source",
      character_count: 1200,
    }],
    segmentation: { segment_count: 4, chunk_count: 1, chunks: [] },
    entities: { occurrence_count: 0, resolved_count: 0, groups: [] },
    conflicts: { count: 0, unresolved_count: 0, items: [] },
    reconstruction: { summary: {}, status: "waiting", domains: [], assets: [] },
    promotion_queue: { status: "waiting", ready_count: 0, deferred_count: 0, items: [] },
    evidence: { revision: "evidence", reference_count: 4, aggregate_revision: "" },
    recovery: recoveryFixture(),
    revision: "workbench-revision",
  };
}

function stateFixture() {
  return {
    status: "blocked",
    current_step: "chunk-extraction-agent-task",
    next_action: "",
    message: "",
    chunk_id: "chunk-0001",
  };
}

function recoveryFixture() {
  return {
    interrupted: false,
    staging_detected: false,
    backup_detected: false,
    resume_supported: true,
  };
}
