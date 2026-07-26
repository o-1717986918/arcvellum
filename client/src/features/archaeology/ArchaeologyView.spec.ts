import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ArchaeologyView from "./ArchaeologyView.vue";

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }));

vi.mock("@/services/api", () => ({
  api: apiMock,
  connectEventStream: vi.fn(() => ({ close: vi.fn() })),
  query: (values: Record<string, string>) => new URLSearchParams(values).toString(),
}));

describe("Project Archaeology view", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    apiMock.mockReset();
    window.localStorage.clear();
  });

  it("presents formal evidence and opens the four-mode import workshop", async () => {
    apiMock.mockImplementation(async (path: string) => {
      if (path === "/archaeology/options") return optionsFixture();
      if (path.startsWith("/archaeology/imports?")) return catalogFixture();
      if (path.startsWith("/archaeology/workbench/legacy-work")) return workbenchFixture();
      throw new Error(`unexpected path: ${path}`);
    });
    const pinia = createPinia();
    setActivePinia(pinia);
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\潮线", false);

    const wrapper = mount(ArchaeologyView, {
      global: {
        plugins: [pinia],
        stubs: { RouterLink: { template: "<a><slot /></a>" } },
      },
      attachTo: document.body,
    });
    await flushPromises();

    expect(wrapper.text()).toContain("旧作");
    expect(wrapper.text()).toContain("逐块理解人物、事件与设定");
    expect(wrapper.text()).toContain("4");
    await wrapper.find(".archaeology-primary").trigger("click");
    await flushPromises();
    const dialog = document.querySelector('[aria-label="导入已有作品"]');
    expect(dialog).not.toBeNull();
    expect(dialog?.textContent).toContain("续写基础");
    expect(dialog?.textContent).toContain("改写重构");
    expect(dialog?.textContent).toContain("媒介改编");
    expect(dialog?.textContent).toContain("作品分析");
    wrapper.unmount();
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
    revision: "catalog",
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
    revision: "workbench",
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
