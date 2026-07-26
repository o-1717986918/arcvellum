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

  it("imports a file queue as one visible batch and refreshes after all commits", async () => {
    const fixture = workbenchFixture();
    let workbenchReads = 0;
    let sourceWrites = 0;
    apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/style-lab/sources" && init?.method === "POST") {
        sourceWrites += 1;
        return {
          schema: "arcvellum/style-author-transaction/v1",
          transaction_id: `style-tx-${sourceWrites}`,
          operation: "import-source",
          status: "committed",
          subject: {
            author_id: "classic-author",
            work_id: "work-one",
            source_id: `source-${sourceWrites + 1}`,
          },
        };
      }
      if (path.startsWith("/style-lab/workbench")) {
        workbenchReads += 1;
        return fixture;
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
    const receipts = await store.importSources([
      {
        author_id: "classic-author",
        work_id: "work-one",
        filename: "卷一.txt",
        media_type: "text/plain",
        content: "第一份来源。",
        rights_mode: "public-domain",
        rights_declaration: "该文本已经进入公有领域，可用于文风分析。",
      },
      {
        author_id: "classic-author",
        work_id: "work-one",
        filename: "卷二.md",
        media_type: "text/markdown",
        content: "第二份来源。",
        rights_mode: "public-domain",
        rights_declaration: "该文本已经进入公有领域，可用于文风分析。",
      },
    ]);

    expect(receipts).toHaveLength(2);
    expect(sourceWrites).toBe(2);
    expect(workbenchReads).toBe(2);
    expect(store.notice).toContain("2 份来源");
  });

  it("binds an exact mount confirmation to the latest impact preview", async () => {
    const initial = workbenchFixture();
    const target = {
      ...initial.versions[0],
      version_id: "v2-reviewed",
      display_name: "克制叙事（二版）",
      state: "built",
      content_hash: "sha256:style-v2",
      mounted: false,
    };
    initial.versions.push(target);
    const mounted = structuredClone(initial);
    mounted.versions = mounted.versions.map((version) => ({
      ...version,
      state: version.version_id === "v2-reviewed" ? "mounted" : "built",
      mounted: version.version_id === "v2-reviewed",
    }));
    mounted.active_mount = {
      style_id: "classic-style",
      version_id: "v2-reviewed",
      profile_id: "restrained",
      content_hash: "sha256:style-v2",
    };
    let workbenchReads = 0;
    apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/style-lab/mount-preview" && init?.method === "POST") {
        const payload = JSON.parse(String(init.body));
        expect(payload).toMatchObject({
          project_root: "C:\\ArcVellum\\潮线",
          style_id: "classic-style",
          version_id: "v2-reviewed",
          content_hash: "sha256:style-v2",
        });
        expect(payload.preview_revision).toBeUndefined();
        return mountPreviewFixture();
      }
      if (path === "/style-lab/mount" && init?.method === "POST") {
        const payload = JSON.parse(String(init.body));
        expect(payload).toMatchObject({
          style_id: "classic-style",
          version_id: "v2-reviewed",
          content_hash: "sha256:style-v2",
          preview_revision: "sha256:mount-preview-v2",
        });
        return {
          schema: "arcvellum/style-mount-transaction/v1",
          status: "mounted",
          style_id: "classic-style",
          version_id: "v2-reviewed",
          content_hash: "sha256:style-v2",
          preview_revision: "sha256:mount-preview-v2",
          active_mount: mounted.active_mount,
          impact: mountPreviewFixture().impact,
        };
      }
      if (path.startsWith("/style-lab/workbench")) {
        workbenchReads += 1;
        return workbenchReads > 1 ? mounted : initial;
      }
      if (path.startsWith("/style-lab/versions/classic-style/")) {
        const versionId = path.includes("v2-reviewed") ? "v2-reviewed" : "v1-stable";
        return {
          schema: "arcvellum/style-profile-version-detail/v1",
          style_id: "classic-style",
          version_id: versionId,
          content_hash: versionId === "v2-reviewed" ? "sha256:style-v2" : "sha256:style",
          author_id: "classic-author",
          profile_id: "restrained",
          state: versionId === "v2-reviewed" ? "built" : "mounted",
        };
      }
      throw new Error(`unexpected path: ${path}`);
    });
    const { useStyleAtelierStore } = await import("./styleAtelier");
    const store = useStyleAtelierStore();
    await store.load();
    await store.selectVersion(target);

    await store.previewMount();

    expect(store.mountPreview?.revision).toBe("sha256:mount-preview-v2");
    expect(store.mountPreview?.impact.affected_scene_count).toBe(1);
    expect(store.selectedVersion?.mounted).toBe(false);

    await store.confirmMount();

    expect(store.mountPreview).toBeNull();
    expect(store.activeMount.version_id).toBe("v2-reviewed");
    expect(store.selectedVersion?.mounted).toBe(true);
    expect(store.notice).toContain("同一份不可变快照");
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

function mountPreviewFixture() {
  return {
    schema: "arcvellum/style-mount-preview/v1",
    status: "confirmation-required",
    revision: "sha256:mount-preview-v2",
    current: {
      style_id: "classic-style",
      version_id: "v1-stable",
      content_hash: "sha256:style",
    },
    target: {
      style_id: "classic-style",
      version_id: "v2-reviewed",
      content_hash: "sha256:style-v2",
    },
    comparison: {
      status: "changed",
      changes: [{
        field: "content_hash",
        label: "版本证据",
        before: "sha256:style",
        after: "sha256:style-v2",
        changed: true,
      }],
      evidence: [{
        field: "prompt_chars",
        label: "提示词细节",
        before: 980,
        after: 1240,
        changed: true,
      }],
    },
    impact: {
      status: "would-propagate",
      mount_changes: true,
      affected_scene_count: 1,
      affected_artifact_count: 2,
      historical_artifact_count: 1,
      inspected_artifact_count: 3,
      entries: [{
        scene_id: "scene_0002",
        stages: ["context", "composition"],
        artifact_count: 2,
        recorded_versions: ["v1-stable"],
        reason: "unpromoted scene evidence uses the previous mounted style",
      }],
      invalidated_stages: ["context", "composition"],
      historical_prose: "preserved",
      revision: "sha256:mount-impact-v2",
    },
    requires_confirmation: true,
  };
}
