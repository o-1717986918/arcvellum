import { effectScope, ref } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import { deliveryClient } from "@/features/delivery/services/deliveryClient";
import { useReaderSearch } from "./useReaderSearch";
afterEach(() => vi.restoreAllMocks());
describe("reader search ordering", () => {
  it("ignores a late result when the query or project has changed", async () => {
    let finish!: (value: { items: Record<string, unknown>[] }) => void;
    vi.spyOn(deliveryClient, "search").mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const root = ref("first"), scope = effectScope();
    const search = scope.run(() => useReaderSearch(root))!;
    search.searchText.value = "old";
    const pending = search.searchProse();
    root.value = "second";
    finish({ items: [{ title: "belongs to first" }] });
    await pending;
    expect(search.searchResults.value).toEqual([]);
    expect(search.searched.value).toBe(false);
    scope.stop();
  });
  it("reports an unsuccessful search and allows a real retry", async () => {
    const call = vi.spyOn(deliveryClient, "search").mockRejectedValueOnce(new Error("离线")).mockResolvedValue({ items: [{ unit_id: "scene-2" }] });
    const scope = effectScope();
    const search = scope.run(() => useReaderSearch(ref("work")))!;
    search.searchText.value = "人物";
    await search.searchProse();
    expect(search.searchError.value).toBe("离线");
    expect(search.searching.value).toBe(false);
    await search.searchProse();
    expect(call).toHaveBeenCalledTimes(2);
    expect(search.searchError.value).toBe("");
    expect(search.searchResults.value[0].unit_id).toBe("scene-2");
    scope.stop();
  });
});
