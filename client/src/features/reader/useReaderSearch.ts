import { onScopeDispose, ref, watch, type Ref } from "vue";
import { deliveryClient } from "@/features/delivery/services/deliveryClient";

export function useReaderSearch(projectRoot: Readonly<Ref<string>>) {
  const searchText = ref("");
  const searchResults = ref<Record<string, unknown>[]>([]);
  const searching = ref(false);
  const searched = ref(false);
  const searchError = ref("");
  let revision = 0;
  watch([searchText, projectRoot], () => {
    revision += 1;
    searchResults.value = [];
    searched.value = searching.value = false;
    searchError.value = "";
  }, { flush: "sync" });
  onScopeDispose(() => { revision += 1; });
  async function searchProse(): Promise<void> {
    const text = searchText.value.trim(), root = projectRoot.value;
    if (!text || !root) return;
    const request = ++revision;
    searching.value = true;
    searchError.value = "";
    try {
      const result = await deliveryClient.search(root, text);
      if (request !== revision) return;
      searchResults.value = result.items || [];
      searched.value = true;
    } catch (cause) {
      if (request === revision) searchError.value = cause instanceof Error ? cause.message : "正文搜索没有完成，请重试。";
    } finally { if (request === revision) searching.value = false; }
  }
  return { searchText, searchResults, searching, searched, searchError, searchProse };
}
