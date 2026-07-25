import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import { api, query } from "@/services/api";
import { useAppStore } from "@/stores/app";
import type {
  ArchiveAssetDetail,
  ArchiveAssetGroup,
  ArchiveCandidate,
  ArchiveRecord,
  RecycleEntry,
} from "../types";

interface ArchiveTreeResponse {
  groups?: ArchiveAssetGroup[];
  items?: ArchiveRecord[];
}

interface ArchiveHistoryResponse extends ArchiveRecord {
  revisions?: ArchiveRecord[];
  transactions?: ArchiveRecord[];
}

export const useArchiveStore = defineStore("archive", () => {
  const app = useAppStore();
  const assetGroups = ref<ArchiveAssetGroup[]>([]);
  const candidates = ref<ArchiveCandidate[]>([]);
  const recycleEntries = ref<RecycleEntry[]>([]);
  const selectedAsset = shallowRef<ArchiveAssetDetail | null>(null);
  const selectedCandidate = shallowRef<ArchiveCandidate | null>(null);
  const history = shallowRef<ArchiveHistoryResponse>({});
  const draft = ref("");
  const validation = shallowRef<Record<string, unknown> | null>(null);
  const impact = shallowRef<Record<string, unknown> | null>(null);
  const promotionJob = shallowRef<Record<string, unknown> | null>(null);
  const busy = ref(false);
  const error = ref("");
  const notice = ref("");
  const openTabs = ref<Array<{ id: string; title: string; kind: "asset" | "candidate" }>>([]);

  const dirty = computed(() => Boolean(selectedAsset.value && draft.value !== selectedAsset.value.content));
  const projectRoot = computed(() => app.currentProjectPath);

  async function loadWorkspace(): Promise<void> {
    if (!projectRoot.value) return;
    busy.value = true;
    error.value = "";
    try {
      const suffix = query({ project_root: projectRoot.value });
      const [tree, candidateList, recycle] = await Promise.all([
        api<ArchiveTreeResponse>(`/archive/tree?${suffix}`),
        api<{ items?: ArchiveCandidate[] }>(`/archive/candidates?${suffix}`),
        api<{ items?: RecycleEntry[] }>(`/archive/recycle-bin?${suffix}`),
      ]);
      assetGroups.value = tree.groups || [];
      candidates.value = candidateList.items || [];
      recycleEntries.value = recycle.items || [];
    } catch (cause) {
      error.value = messageFor(cause, "作品档案暂时没有读取成功。");
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  async function openAsset(assetId: string): Promise<void> {
    if (!projectRoot.value) return;
    busy.value = true;
    error.value = "";
    selectedCandidate.value = null;
    try {
      const encoded = encodeURIComponent(assetId);
      const suffix = query({ project_root: projectRoot.value });
      const [detail, revisions] = await Promise.all([
        api<{ asset: ArchiveAssetDetail }>(`/archive/assets/${encoded}?${suffix}`),
        api<ArchiveHistoryResponse>(`/archive/assets/${encoded}/history?${suffix}`),
      ]);
      selectedAsset.value = detail.asset;
      history.value = revisions;
      draft.value = detail.asset.content;
      validation.value = null;
      impact.value = null;
      pushTab(assetId, detail.asset.title, "asset");
    } catch (cause) {
      error.value = messageFor(cause, "这份作品资料暂时无法打开。");
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  async function openCandidate(candidateId: string): Promise<void> {
    if (!projectRoot.value) return;
    busy.value = true;
    error.value = "";
    selectedAsset.value = null;
    try {
      const response = await api<{ candidate: ArchiveCandidate }>(
        `/archive/candidates/${encodeURIComponent(candidateId)}?${query({ project_root: projectRoot.value })}`,
      );
      selectedCandidate.value = response.candidate;
      pushTab(candidateId, response.candidate.title || candidateId, "candidate");
    } catch (cause) {
      error.value = messageFor(cause, "候选资料暂时无法打开。");
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  function updateDraft(content: string): void {
    draft.value = content;
    validation.value = null;
    impact.value = null;
  }

  async function previewEdit(): Promise<void> {
    const asset = requireAsset();
    busy.value = true;
    error.value = "";
    try {
      const endpoint = `/archive/assets/${encodeURIComponent(asset.asset_id)}`;
      const body = JSON.stringify({ project_root: projectRoot.value, content: draft.value });
      const [validationResponse, impactResponse] = await Promise.all([
        api<{ validation: Record<string, unknown> }>(`${endpoint}/validate`, { method: "POST", body }),
        api<{ impact: Record<string, unknown> }>(`${endpoint}/impact`, { method: "POST", body }),
      ]);
      validation.value = validationResponse.validation;
      impact.value = impactResponse.impact;
    } catch (cause) {
      error.value = messageFor(cause, "变更检查没有完成。");
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  async function commitEdit(reason: string, ownerWaiver: boolean): Promise<void> {
    const asset = requireAsset();
    if (!ownerWaiver) throw new Error("请确认这次修改以作者决定为准。");
    if (!validation.value || !impact.value) await previewEdit();
    if (validation.value?.valid !== true) throw new Error("资料结构检查未通过，不能保存为正式版本。");
    busy.value = true;
    error.value = "";
    try {
      const response = await api<{ receipt: Record<string, unknown> }>(
        `/archive/assets/${encodeURIComponent(asset.asset_id)}/commit`,
        {
          method: "POST",
          body: JSON.stringify({
            project_root: projectRoot.value,
            base_revision: asset.revision,
            content: draft.value,
            semantic_review: "waived",
            reason,
            expected_impacts: expectedImpactNames(impact.value || {}),
          }),
        },
      );
      selectedAsset.value = {
        ...asset,
        content: draft.value,
        revision: String(response.receipt.new_revision || asset.revision),
      };
      validation.value = null;
      impact.value = null;
      notice.value = "作者版本已保存，相关创作链路会按正式失效证据重新检查。";
      await refreshAfterMutation(asset.asset_id);
    } catch (cause) {
      error.value = messageFor(cause, "作者版本没有保存成功。");
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  async function archiveAsset(reason: string): Promise<void> {
    const asset = requireAsset();
    busy.value = true;
    try {
      await api(`/archive/assets/${encodeURIComponent(asset.asset_id)}/archive`, {
        method: "POST",
        body: JSON.stringify({
          project_root: projectRoot.value,
          base_revision: asset.revision,
          reason,
        }),
      });
      closeTab(asset.asset_id);
      selectedAsset.value = null;
      notice.value = "资料已移入项目回收站。";
      await loadWorkspace();
    } finally {
      busy.value = false;
    }
  }

  async function restoreEntry(entry: RecycleEntry, reason: string): Promise<void> {
    busy.value = true;
    try {
      await api(`/archive/assets/${encodeURIComponent(entry.asset_id)}/restore`, {
        method: "POST",
        body: JSON.stringify({
          project_root: projectRoot.value,
          entry_id: entry.entry_id,
          reason,
        }),
      });
      notice.value = "资料已恢复到正式档案。";
      await loadWorkspace();
    } finally {
      busy.value = false;
    }
  }

  async function promoteCandidate(): Promise<Record<string, unknown>> {
    const candidate = selectedCandidate.value;
    if (!candidate?.candidate_id || !candidate.preview_digest) throw new Error("请先重新打开候选并确认影响范围。");
    if (!candidate.can_promote) throw new Error("候选仍有未完成的审查或批准步骤。");
    busy.value = true;
    try {
      const job = await api<Record<string, unknown>>(
        `/archive/candidates/${encodeURIComponent(candidate.candidate_id)}/promote`,
        {
          method: "POST",
          body: JSON.stringify({
            project_root: projectRoot.value,
            preview_digest: candidate.preview_digest,
          }),
        },
      );
      promotionJob.value = job;
      notice.value = "候选已进入正式晋升任务，结果会继续接受 Engine 门禁。";
      return job;
    } finally {
      busy.value = false;
    }
  }

  async function refreshCandidate(): Promise<void> {
    const id = selectedCandidate.value?.candidate_id;
    if (!id) return;
    await openCandidate(id);
    await loadWorkspace();
  }

  function closeTab(id: string): void {
    openTabs.value = openTabs.value.filter((tab) => tab.id !== id);
  }

  function clearMessages(): void {
    error.value = "";
    notice.value = "";
  }

  function pushTab(id: string, title: string, kind: "asset" | "candidate"): void {
    if (!openTabs.value.some((tab) => tab.id === id && tab.kind === kind)) {
      openTabs.value.push({ id, title, kind });
    }
  }

  function requireAsset(): ArchiveAssetDetail {
    if (!selectedAsset.value) throw new Error("请先选择一份正式资料。");
    return selectedAsset.value;
  }

  async function refreshAfterMutation(assetId: string): Promise<void> {
    const encoded = encodeURIComponent(assetId);
    history.value = await api<ArchiveHistoryResponse>(
      `/archive/assets/${encoded}/history?${query({ project_root: projectRoot.value })}`,
    );
    const tree = await api<ArchiveTreeResponse>(
      `/archive/tree?${query({ project_root: projectRoot.value })}`,
    );
    assetGroups.value = tree.groups || [];
  }

  return {
    assetGroups,
    candidates,
    recycleEntries,
    selectedAsset,
    selectedCandidate,
    history,
    draft,
    validation,
    impact,
    promotionJob,
    busy,
    error,
    notice,
    openTabs,
    dirty,
    loadWorkspace,
    openAsset,
    openCandidate,
    updateDraft,
    previewEdit,
    commitEdit,
    archiveAsset,
    restoreEntry,
    promoteCandidate,
    refreshCandidate,
    closeTab,
    clearMessages,
  };
});

function expectedImpactNames(impact: Record<string, unknown>): string[] {
  const values = impact.stale_categories;
  if (Array.isArray(values)) return values.map(String);
  const categories = impact.categories;
  return Array.isArray(categories) ? categories.map(String) : [];
}

function messageFor(cause: unknown, fallback: string): string {
  return cause instanceof Error && cause.message ? cause.message : fallback;
}
