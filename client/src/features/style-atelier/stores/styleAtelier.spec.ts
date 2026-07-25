import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StyleAtelierWorkbench } from "../types";

const apiMock = vi.fn();

vi.mock("@/services/api", () => ({
  api: apiMock,
  query: (values: Record<string, string>) => new URLSearchParams(values).toString(),
}));

vi.mock("@/stores/app", () => ({
  useAppStore: () => ({ currentProjectPath: "C:\\ArcVellum\\潮线" }),
}));

describe("style atelier store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    apiMock.mockReset();
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
