import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ArchiveView from "./ArchiveView.vue";

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }));

vi.mock("@/services/api", () => ({
  api: apiMock,
  query: (values: Record<string, string>) => new URLSearchParams(values).toString(),
}));

describe("Narrative Archive view", () => {
  beforeEach(() => {
    apiMock.mockReset();
  });

  it("opens the first formal asset without waiting for the human-choice query", async () => {
    apiMock.mockImplementation((path: string) => {
      if (path.startsWith("/archive/tree")) {
        return Promise.resolve({
          groups: [
            {
              asset_type: "character",
              label: "人物",
              items: [
                {
                  asset_id: "character:lin",
                  asset_type: "character",
                  title: "林澈",
                  revision: "rev-1",
                  editor_kind: "form",
                },
              ],
            },
          ],
        });
      }
      if (path.startsWith("/archive/candidates")) return Promise.resolve({ items: [] });
      if (path.startsWith("/archive/recycle-bin")) return Promise.resolve({ items: [] });
      if (path.startsWith("/archive/assets/character%3Alin/history")) {
        return Promise.resolve({ revisions: [], transactions: [] });
      }
      if (path.startsWith("/archive/assets/character%3Alin")) {
        return Promise.resolve({
          asset: {
            asset_id: "character:lin",
            asset_type: "character",
            title: "林澈",
            relative_path: "characters/lin.yaml",
            revision: "rev-1",
            content: "character_id: lin\nname: 林澈\n",
            editor_kind: "form",
            writable_fields: ["name"],
          },
        });
      }
      if (path.startsWith("/workflow/current-choice")) {
        return new Promise(() => {});
      }
      return Promise.reject(new Error(`Unexpected API path: ${path}`));
    });

    const pinia = createPinia();
    setActivePinia(pinia);
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\潮线", false);

    const wrapper = mount(ArchiveView, {
      global: {
        plugins: [pinia],
        stubs: {
          RouterLink: { template: "<a><slot /></a>" },
        },
      },
    });
    await flushPromises();

    expect(wrapper.find(".archive-editor-pane").exists()).toBe(true);
    expect(wrapper.text()).toContain("林澈");
    expect(wrapper.findAll(".archive-tabs > div")).toHaveLength(1);
    wrapper.unmount();
  });
});
