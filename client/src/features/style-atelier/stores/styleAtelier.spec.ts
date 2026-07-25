import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StyleAtelierWorkbench } from "../types";

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

vi.mock("@/stores/app", () => ({
  useAppStore: () => ({
    currentProjectPath: "C:\\ArcVellum\\潮线",
    loadAgentObservability: vi.fn(),
  }),
}));

describe("style atelier store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    apiMock.mockReset();
    connectEventStreamMock.mockClear();
    streamCloseMock.mockClear();
    streamListener = null;
  });

  it("loads the workbench and selects the mounted immutable version", async () => {
    apiMock.mockImplementation(async (path: string) => {
      if (path.startsWith("/style-lab/workbench")) return workbenchFixture();
      if (path.startsWith("/style-lab/versions/classic-style/v1-stable")) {
        return {
          schema: "arcvellum/style-profile-version-detail/v1",
          style_id: "classic-style",
          version_id: "v1-stable",
          content_hash: "sha256:style",
          author_id: "classic-author",
          profile_id: "restrained",
          state: "mounted",
          integrity: { status: "pass", issues: [] },
          evaluation: { overall_score: 91, risk_level: "low" },
        };
      }
      throw new Error(`unexpected path: ${path}`);
    });
    const { useStyleAtelierStore } = await import("./styleAtelier");
    const store = useStyleAtelierStore();

    await store.load();

    expect(store.selectedAuthor?.author_id).toBe("classic-author");
    expect(store.selectedWork?.work_id).toBe("work-one");
    expect(store.selectedVersion?.version_id).toBe("v1-stable");
    expect(store.versionDetail?.integrity?.status).toBe("pass");
    expect(apiMock).toHaveBeenCalledWith(
      expect.stringContaining("project_root=C%3A%5CArcVellum%5C%E6%BD%AE%E7%BA%BF"),
    );
  });

  it("keeps planned versions readable without requesting unavailable detail", async () => {
    const fixture = workbenchFixture();
    fixture.versions = [{
      ...fixture.versions[0],
      version_id: "",
      planned_version_id: "v1-planned",
      built: false,
      mounted: false,
      state: "build-ready",
    }];
    apiMock.mockResolvedValue(fixture);
    const { useStyleAtelierStore } = await import("./styleAtelier");
    const store = useStyleAtelierStore();

    await store.load();

    expect(store.selectedVersion?.planned_version_id).toBe("v1-planned");
    expect(store.versionDetail).toBeNull();
    expect(apiMock).toHaveBeenCalledTimes(1);
  });

  it("commits source authoring through the API and refreshes the projection", async () => {
    const fixture = workbenchFixture();
    const expanded = workbenchFixture();
    expanded.authors[0].works[0].sources.push({
      source_id: "source-two",
      filename: "work-two.txt",
      content_sha256: "sha256:source-two",
      character_count: 1500,
      chunk_count: 1,
    });
    expanded.authors[0].works[0].source_count = 2;
    let workbenchReads = 0;
    apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/style-lab/sources" && init?.method === "POST") {
        return {
          schema: "arcvellum/style-author-transaction/v1",
          transaction_id: "style-tx",
          operation: "import-source",
          status: "committed",
          subject: {
            author_id: "classic-author",
            work_id: "work-one",
            source_id: "source-two",
          },
        };
      }
      if (path.startsWith("/style-lab/workbench")) {
        workbenchReads += 1;
        return workbenchReads > 1 ? expanded : fixture;
      }
      if (path.startsWith("/style-lab/versions/classic-style/v1-stable")) {
        return {
          schema: "arcvellum/style-profile-version-detail/v1",
          style_id: "classic-style",
          version_id: "v1-stable",
          content_hash: "sha256:style",
          author_id: "classic-author",
          profile_id: "restrained",
          state: "mounted",
        };
      }
      throw new Error(`unexpected path: ${path}`);
    });
    const { useStyleAtelierStore } = await import("./styleAtelier");
    const store = useStyleAtelierStore();
    await store.load();

    const receipt = await store.importSource({
      author_id: "classic-author",
      work_id: "work-one",
      filename: "work-two.txt",
      media_type: "text/plain",
      content: "这是一份新的合法来源。",
      rights_mode: "public-domain",
      rights_declaration: "这份文本已进入公有领域，可以用于文风分析。",
    });

    expect(receipt.subject.source_id).toBe("source-two");
    expect(store.selectedWork?.sources).toHaveLength(2);
    expect(store.notice).toContain("来源已经固化");
    expect(apiMock).toHaveBeenCalledWith(
      "/style-lab/sources",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("observes a formal style job through SSE and refreshes only at its real terminal state", async () => {
    apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/style-lab/compile" && init?.method === "POST") {
        return {
          schema: "arcvellum/style-compile-job/v1",
          status: "queued",
          task: {
            task_id: "style-engineering-classic-author-new-profile-style-profile",
            current_state: "style-profile",
            status: "issued",
          },
          session: {
            session_id: "classic-author-new-profile",
            author_id: "classic-author",
            profile_id: "new-profile",
            status: "prepared",
          },
          job: {
            job_id: "job-style-new",
            status: "queued",
            revision: 0,
          },
        };
      }
      if (path.startsWith("/style-lab/workbench")) return workbenchFixture();
      if (path.startsWith("/style-lab/versions/classic-style/v1-stable")) {
        return {
          schema: "arcvellum/style-profile-version-detail/v1",
          style_id: "classic-style",
          version_id: "v1-stable",
          content_hash: "sha256:style",
          author_id: "classic-author",
          profile_id: "restrained",
          state: "mounted",
        };
      }
      if (path.startsWith("/agent-observability")) {
        return { schema: "arcvellum/agent-observability/v2", sessions: [], recent_events: [] };
      }
      throw new Error(`unexpected path: ${path}`);
    });
    const { useStyleAtelierStore } = await import("./styleAtelier");
    const store = useStyleAtelierStore();
    await store.load();

    await store.compileProfile({
      author_id: "classic-author",
      profile_id: "new-profile",
      display_name: "新文风",
      training_sources: [{ work_id: "work-one", source_id: "source-one" }],
      holdout_sources: [{ work_id: "work-one", source_id: "source-two" }],
      runtime: "opencode",
    });

    expect(store.engineeringJob?.status).toBe("queued");
    expect(connectEventStreamMock).toHaveBeenCalledWith(
      "/worker/jobs/job-style-new/stream",
      expect.any(Function),
      expect.any(Function),
    );
    streamListener?.("worker", {
      job_id: "job-style-new",
      status: "complete",
      revision: 2,
      result: { message: "task complete" },
    });
    await vi.waitFor(() => expect(store.notice).toContain("当前文风步骤已通过"));
    expect(store.engineeringJob?.status).toBe("complete");
    expect(streamCloseMock).toHaveBeenCalled();
  });
});

function workbenchFixture(): StyleAtelierWorkbench {
  return {
    schema: "arcvellum/style-atelier-workbench/v1" as const,
    revision: "sha256:workbench",
    authors: [{
      author_id: "classic-author",
      name: "古典作者",
      rights: { status: "declared", mode: "public-domain", declaration: "公版来源" },
      works: [{
        work_id: "work-one",
        title: "作品一",
        sources: [{
          source_id: "source-one",
          filename: "work-one.txt",
          content_sha256: "sha256:source",
          character_count: 8200,
          chunk_count: 12,
        }],
        source_count: 1,
      }],
      work_count: 1,
      profile_count: 1,
    }],
    versions: [{
      style_id: "classic-style",
      version_id: "v1-stable",
      author_id: "classic-author",
      profile_id: "restrained",
      display_name: "克制叙事",
      state: "mounted",
      source_count: 1,
      accepted_evaluation_count: 1,
      review_status: "pass",
      content_hash: "sha256:style",
      built: true,
      mounted: true,
    }],
    active_mount: {
      style_id: "classic-style",
      version_id: "v1-stable",
      profile_id: "restrained",
      content_hash: "sha256:style",
    },
    summary: {
      author_count: 1,
      work_count: 1,
      source_count: 1,
      source_character_count: 8200,
      profile_count: 1,
      evaluated_count: 1,
      reviewed_count: 1,
      built_count: 1,
      mounted_count: 1,
    },
    journey: [
      { id: "sources", label: "来源与权利", status: "ready", count: 1 },
      { id: "profiles", label: "文风抽象", status: "ready", count: 1 },
    ],
    issues: [],
  };
}
