import { computed, ref } from "vue";
import type {
  ArchiveAssetDetail,
  ArchiveHistory,
  ArchiveStructuredDocument,
} from "../types";

export interface ArchiveTab {
  id: string;
  title: string;
  kind: "asset" | "candidate";
}

export interface AssetDraftSession {
  asset: ArchiveAssetDetail;
  draft: string;
  validation: Record<string, unknown> | null;
  impact: Record<string, unknown> | null;
  structure: ArchiveStructuredDocument | null;
  history: ArchiveHistory;
}

export function useArchiveSessions() {
  const openTabs = ref<ArchiveTab[]>([]);
  const activeTabKey = ref("");
  const assetSessions = ref<Record<string, AssetDraftSession>>({});
  const dirtyAssetIds = computed(() =>
    Object.values(assetSessions.value)
      .filter((session) => session.draft !== session.asset.content)
      .map((session) => session.asset.asset_id),
  );

  function asset(assetId: string): AssetDraftSession | null {
    return assetSessions.value[assetId] || null;
  }

  function save(session: AssetDraftSession): void {
    assetSessions.value = {
      ...assetSessions.value,
      [session.asset.asset_id]: session,
    };
  }

  function open(id: string, title: string, kind: ArchiveTab["kind"]): void {
    if (!openTabs.value.some((tab) => key(tab.id, tab.kind) === key(id, kind))) {
      openTabs.value.push({ id, title, kind });
    }
    activeTabKey.value = key(id, kind);
  }

  function remove(id: string, kind: ArchiveTab["kind"]): number {
    const target = key(id, kind);
    const index = openTabs.value.findIndex((tab) => key(tab.id, tab.kind) === target);
    openTabs.value = openTabs.value.filter((tab) => key(tab.id, tab.kind) !== target);
    if (kind === "asset") {
      const next = { ...assetSessions.value };
      delete next[id];
      assetSessions.value = next;
    }
    return index;
  }

  function fallback(index: number): ArchiveTab | null {
    return openTabs.value[Math.min(Math.max(index, 0), openTabs.value.length - 1)] || null;
  }

  function reset(): void {
    openTabs.value = [];
    activeTabKey.value = "";
    assetSessions.value = {};
  }

  function key(id: string, kind: ArchiveTab["kind"]): string {
    return `${kind}:${id}`;
  }

  return {
    openTabs,
    activeTabKey,
    dirtyAssetIds,
    asset,
    save,
    open,
    remove,
    fallback,
    reset,
    key,
  };
}
