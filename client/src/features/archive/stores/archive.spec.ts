import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.fn();

vi.mock("@/services/api", () => ({
  api: apiMock,
  query: (values: Record<string, string>) => new URLSearchParams(values).toString(),
}));

vi.mock("@/stores/app", () => ({
  useAppStore: () => ({ currentProjectPath: "C:\\ArcVellum\\潮线" }),
}));

describe("archive store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    apiMock.mockReset();
  });

  it("loads formal assets, candidates, and recycle entries without merging their identities", async () => {
    apiMock.mockImplementation(async (path: string) => {
      if (path.startsWith("/archive/tree")) {
        return {
          groups: [{ asset_type: "character", items: [{ asset_id: "character:lin", title: "林澈" }] }],
          items: [{ asset_id: "character:lin", title: "林澈" }],
        };
      }
      if (path.startsWith("/archive/candidates")) {
        return { items: [{ candidate_id: "lin-revision", title: "林澈候选", current_step: "asset-approval" }] };
      }
      if (path.startsWith("/archive/recycle-bin")) {
        return { items: [{ entry_id: "recycle-one", asset_id: "character:mei", title: "梅汐" }] };
      }
      if (path.startsWith("/archive/creation/options")) {
        return { items: [{ asset_type: "character", template: "character_id: __ASSET_ID__\n", available: true }] };
      }
      throw new Error(`unexpected path: ${path}`);
    });
    const { useArchiveStore } = await import("./archive");
    const store = useArchiveStore();

    await store.loadWorkspace();

    expect(store.assetGroups[0].items[0].asset_id).toBe("character:lin");
    expect(store.candidates[0].candidate_id).toBe("lin-revision");
    expect(store.recycleEntries[0].entry_id).toBe("recycle-one");
    expect(store.creationOptions[0].asset_type).toBe("character");
  });

  it("previews and commits an owner edit against the exact base revision", async () => {
    apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.startsWith("/archive/assets/character%3Alin?")) {
        return {
          asset: {
            asset_id: "character:lin",
            title: "林澈",
            revision: "sha256:old",
            content: "character_id: lin\nname: 林澈\n",
            writable_fields: ["name"],
          },
        };
      }
      if (path.endsWith("/history?project_root=C%3A%5CArcVellum%5C%E6%BD%AE%E7%BA%BF")) {
        return { revisions: [], transactions: [] };
      }
      if (path.endsWith("/validate")) return { validation: { valid: true, issues: [] } };
      if (path.endsWith("/impact")) return { impact: { summary: { reference_count: 2 }, stale_categories: ["context"] } };
      if (path.endsWith("/commit")) {
        const body = JSON.parse(String(init?.body));
        expect(body.base_revision).toBe("sha256:old");
        expect(body.content).toContain("importance: major");
        return { receipt: { new_revision: "sha256:new", authority: "owner" } };
      }
      if (path.startsWith("/archive/tree")) return { groups: [], items: [] };
      if (path.startsWith("/archive/candidates")) return { items: [] };
      if (path.startsWith("/archive/recycle-bin")) return { items: [] };
      throw new Error(`unexpected path: ${path}`);
    });
    const { useArchiveStore } = await import("./archive");
    const store = useArchiveStore();
    await store.openAsset("character:lin");
    store.updateDraft("character_id: lin\nname: 林澈\nimportance: major\n");

    await store.previewEdit();
    await store.commitEdit("作者确认人物在本卷承担主线。", true);

    const commitCall = apiMock.mock.calls.find(([path]) => String(path).endsWith("/commit"));
    expect(commitCall).toBeTruthy();
    expect(store.dirty).toBe(false);
    expect(store.notice).toContain("作者版本");
  });

  it("binds candidate promotion to the preview digest", async () => {
    apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.startsWith("/archive/candidates/lin-revision?")) {
        return {
          candidate: {
            candidate_id: "lin-revision",
            can_promote: true,
            preview_digest: "sha256:preview",
            impact: { formal_outputs: [{ path: "characters/lin.yaml", effect: "replace" }] },
          },
        };
      }
      if (path.endsWith("/promote")) {
        expect(JSON.parse(String(init?.body)).preview_digest).toBe("sha256:preview");
        return { job_id: "job-promote", status: "queued" };
      }
      throw new Error(`unexpected path: ${path}`);
    });
    const { useArchiveStore } = await import("./archive");
    const store = useArchiveStore();
    await store.openCandidate("lin-revision");

    const job = await store.promoteCandidate();

    expect(job.job_id).toBe("job-promote");
    expect(store.promotionJob?.status).toBe("queued");
  });

  it("creates a registered asset only from its exact checked preview", async () => {
    apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/archive/creation/preview") {
        const body = JSON.parse(String(init?.body));
        expect(body.asset_type).toBe("character");
        expect(body.local_id).toBe("mei");
        return {
          preview: {
            preview_digest: "sha256:creation-preview",
            committable: true,
            validation: { valid: true, issues: [] },
            impact: { stale_categories: [] },
          },
        };
      }
      if (path === "/archive/creation/commit") {
        const body = JSON.parse(String(init?.body));
        expect(body.preview_digest).toBe("sha256:creation-preview");
        return { asset_id: "character:mei", receipt: { operation: "create" } };
      }
      if (path.startsWith("/archive/tree")) {
        return {
          groups: [{ asset_type: "character", items: [{ asset_id: "character:mei", title: "梅汐" }] }],
        };
      }
      if (path.startsWith("/archive/candidates")) return { items: [] };
      if (path.startsWith("/archive/recycle-bin")) return { items: [] };
      if (path.startsWith("/archive/creation/options")) return { items: [] };
      if (path.startsWith("/archive/assets/character%3Amei/history")) {
        return { revisions: [], transactions: [] };
      }
      if (path.startsWith("/archive/assets/character%3Amei")) {
        return {
          asset: {
            asset_id: "character:mei",
            asset_type: "character",
            title: "梅汐",
            revision: "sha256:new",
            content: "character_id: mei\nname: 梅汐\nimportance: secondary\n",
          },
        };
      }
      throw new Error(`unexpected path: ${path}`);
    });
    const { useArchiveStore } = await import("./archive");
    const store = useArchiveStore();
    const payload = {
      asset_type: "character",
      local_id: "mei",
      content: "character_id: mei\nname: 梅汐\nimportance: secondary\n",
      semantic_review: "waived" as const,
      reason: "作者创建新的正式人物资产。",
      expected_impacts: [],
    };

    await store.previewCreation(payload);
    const assetId = await store.createAsset(payload);

    expect(assetId).toBe("character:mei");
    expect(store.selectedAsset?.asset_id).toBe("character:mei");
    expect(store.creationPreview).toBeNull();
    expect(store.notice).toContain("新资料");
  });
});
