import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAppStore } from "./app";
import { deliveryClient } from "@/features/delivery/services/deliveryClient";
beforeEach(() => { localStorage.clear(); setActivePinia(createPinia()); });
afterEach(() => vi.restoreAllMocks());
describe("project read scope", () => {
  it("does not paint an old project's manifest over the selected work", async () => {
    let finish!: (value: never) => void;
    vi.spyOn(deliveryClient, "readerManifest").mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const store = useAppStore();
    store.setCurrentProject("work-a", false);
    const pending = store.loadReaderManifest();
    store.setCurrentProject("work-b", false);
    finish({ project_root: "work-a", units: [{ unit_id: "scene-1" }] } as never);
    await pending;
    expect(store.readerManifest).toBeNull();
  });
  it("never puts an old project's text in the new project's unit cache", async () => {
    let finish!: (value: never) => void;
    vi.spyOn(deliveryClient, "readerUnit").mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const store = useAppStore();
    store.setCurrentProject("work-a", false);
    const pending = store.loadReaderUnit("scene-1");
    store.setCurrentProject("work-b", false);
    finish({ unit: { content_hash: "hash-a" }, body: "只属于作品甲的内容" } as never);
    await pending;
    expect(store.readerBodies).toEqual({});
  });
});
