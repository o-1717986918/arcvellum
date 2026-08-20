import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import { useAppStore } from "@/stores/app";
import type {
  ArchiveAssetDetail,
  ArchiveAssetGroup,
  ArchiveCandidate,
  ArchiveCreationOption,
  ArchiveCreationPayload,
  ArchiveCreationPreview,
  ArchiveStructuredDocument,
  RecycleEntry,
} from "../types";
import {
  archiveFormalAsset,
  commitArchiveCreation,
  commitArchiveEdit,
  fetchArchiveAsset,
  fetchArchiveCandidate,
  fetchArchiveWorkspace,
  fetchStructuredDocument,
  promoteArchiveCandidate,
  previewArchiveCreation,
  previewArchiveEdit,
  refreshArchiveMutation,
  restoreArchiveAsset,
  renderStructuredDocument,
} from "../services/archiveClient";
import {
  useArchiveSessions,
} from "./archiveSessions";
import { useArchiveEditorState } from "./archiveEditorState";
import {
  archiveErrorMessage as messageFor,
  expectedImpactNames,
} from "./archiveMessages";

export const useArchiveStore = defineStore("archive", () => {
  const app = useAppStore();
  const assetGroups = ref<ArchiveAssetGroup[]>([]);
  const candidates = ref<ArchiveCandidate[]>([]);
  const recycleEntries = ref<RecycleEntry[]>([]);
  const creationOptions = ref<ArchiveCreationOption[]>([]);
  const creationPreview = shallowRef<ArchiveCreationPreview | null>(null);
  const editor = useArchiveEditorState();
  const {
    selectedAsset,
    selectedCandidate,
    history,
    draft,
    structuredDocument,
    validation,
    impact,
  } = editor;
  const promotionJob = shallowRef<Record<string, unknown> | null>(null);
  const busy = ref(false);
  const error = ref("");
  const notice = ref("");
  const sessions = useArchiveSessions();
  const openTabs = sessions.openTabs;
  const activeTabKey = sessions.activeTabKey;
  const loadedProjectRoot = ref("");

  const dirty = editor.dirty;
  const dirtyAssetIds = sessions.dirtyAssetIds;
  const projectRoot = computed(() => app.currentProjectPath);

  async function loadWorkspace(): Promise<void> {
    if (!projectRoot.value) return;
    if (loadedProjectRoot.value && loadedProjectRoot.value !== projectRoot.value) {
      resetEditorWorkspace();
    }
    loadedProjectRoot.value = projectRoot.value;
    busy.value = true;
    error.value = "";
    try {
      const workspace = await fetchArchiveWorkspace(projectRoot.value);
      assetGroups.value = workspace.groups;
      candidates.value = workspace.candidates;
      recycleEntries.value = workspace.recycleEntries;
      creationOptions.value = workspace.creationOptions;
    } catch (cause) {
      error.value = messageFor(cause, "作品档案暂时没有读取成功。");
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  async function openAsset(assetId: string): Promise<void> {
    if (!projectRoot.value) return;
    persistCurrentAssetSession();
    const cached = sessions.asset(assetId);
    if (cached) {
      error.value = "";
      editor.restore(cached);
      sessions.open(assetId, cached.asset.title, "asset");
      return;
    }
    busy.value = true;
    error.value = "";
    selectedCandidate.value = null;
    try {
      const detail = await fetchArchiveAsset(projectRoot.value, assetId);
      let structure: ArchiveStructuredDocument | null = null;
      try {
        structure = await fetchStructuredDocument(
          projectRoot.value,
          assetId,
          detail.asset.content,
        );
      } catch (cause) {
        error.value = messageFor(
          cause,
          "这份资料暂时无法建立结构化表单，请使用专家源文本修复结构。",
        );
      }
      const session = {
        asset: detail.asset,
        draft: detail.asset.content,
        validation: null,
        impact: null,
        structure,
        history: detail.history,
      };
      sessions.save(session);
      editor.restore(session);
      sessions.open(assetId, detail.asset.title, "asset");
    } catch (cause) {
      error.value = messageFor(cause, "这份作品资料暂时无法打开。");
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  async function openCandidate(candidateId: string): Promise<void> {
    if (!projectRoot.value) return;
    persistCurrentAssetSession();
    busy.value = true;
    error.value = "";
    selectedAsset.value = null;
    try {
      const response = await fetchArchiveCandidate(projectRoot.value, candidateId);
      selectedCandidate.value = response.candidate;
      sessions.open(candidateId, response.candidate.title || candidateId, "candidate");
    } catch (cause) {
      error.value = messageFor(cause, "候选资料暂时无法打开。");
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  function updateDraft(content: string): void {
    draft.value = content;
    structuredDocument.value = null;
    validation.value = null;
    impact.value = null;
    persistCurrentAssetSession();
  }

  async function applyStructuredFields(fields: Record<string, unknown>): Promise<void> {
    const asset = requireAsset();
    const structure = structuredDocument.value;
    if (!structure) throw new Error("字段契约已过期，请重新打开这份资料。");
    busy.value = true;
    error.value = "";
    try {
      const response = await renderStructuredDocument(
        projectRoot.value,
        asset.asset_id,
        draft.value,
        structure.source_revision,
        fields,
      );
      draft.value = response.content;
      structuredDocument.value = response.structure;
      validation.value = response.validation;
      impact.value = null;
      notice.value = "字段修改已应用到当前草稿，保存正式版本前仍需检查影响。";
      persistCurrentAssetSession();
    } catch (cause) {
      error.value = messageFor(cause, "字段修改没有应用到当前草稿。");
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  async function reloadStructuredDocument(): Promise<void> {
    const asset = requireAsset();
    busy.value = true;
    error.value = "";
    try {
      structuredDocument.value = await fetchStructuredDocument(
        projectRoot.value,
        asset.asset_id,
        draft.value,
      );
      persistCurrentAssetSession();
    } catch (cause) {
      error.value = messageFor(
        cause,
        "当前草稿无法建立结构化表单，请在专家源文本中修复格式。",
      );
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  async function previewEdit(): Promise<void> {
    const asset = requireAsset();
    busy.value = true;
    error.value = "";
    try {
      const preview = await previewArchiveEdit(
        projectRoot.value,
        asset.asset_id,
        draft.value,
      );
      validation.value = preview.validation;
      impact.value = preview.impact;
      persistCurrentAssetSession();
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
      const response = await commitArchiveEdit(
        projectRoot.value,
        asset.asset_id,
        {
          baseRevision: asset.revision,
          content: draft.value,
          reason,
          expectedImpacts: expectedImpactNames(impact.value || {}),
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
      persistCurrentAssetSession();
    } catch (cause) {
      error.value = messageFor(cause, "作者版本没有保存成功。");
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  async function previewCreation(payload: ArchiveCreationPayload): Promise<ArchiveCreationPreview> {
    busy.value = true;
    error.value = "";
    creationPreview.value = null;
    try {
      const response = await previewArchiveCreation(projectRoot.value, payload);
      creationPreview.value = response.preview;
      return response.preview;
    } catch (cause) {
      error.value = messageFor(cause, "新资料检查没有完成。");
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  async function createAsset(payload: ArchiveCreationPayload): Promise<string> {
    const preview = creationPreview.value;
    if (!preview?.preview_digest || !preview.committable) {
      throw new Error("请先完成新资料检查，并处理所有结构问题。");
    }
    busy.value = true;
    error.value = "";
    try {
      const response = await commitArchiveCreation(
        projectRoot.value,
        payload,
        preview.preview_digest,
      );
      creationPreview.value = null;
      notice.value = "新资料已进入正式档案，并建立了首个作者版本。";
      await loadWorkspace();
      await openAsset(response.asset_id);
      return response.asset_id;
    } catch (cause) {
      error.value = messageFor(cause, "新资料没有创建成功。");
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  function resetCreationPreview(): void {
    creationPreview.value = null;
  }

  async function archiveAsset(reason: string): Promise<void> {
    const asset = requireAsset();
    busy.value = true;
    try {
      await archiveFormalAsset(projectRoot.value, asset.asset_id, asset.revision, reason);
      await closeTab(asset.asset_id, "asset", true);
      notice.value = "资料已移入项目回收站。";
      await loadWorkspace();
    } finally {
      busy.value = false;
    }
  }

  async function restoreEntry(entry: RecycleEntry, reason: string): Promise<void> {
    busy.value = true;
    try {
      await restoreArchiveAsset(projectRoot.value, entry.asset_id, entry.entry_id, reason);
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
      const job = await promoteArchiveCandidate(projectRoot.value, candidate.candidate_id, candidate.preview_digest);
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

  async function closeTab(
    id: string,
    kind: "asset" | "candidate",
    discard = false,
  ): Promise<boolean> {
    persistCurrentAssetSession();
    const session = kind === "asset" ? sessions.asset(id) : null;
    if (session && session.draft !== session.asset.content && !discard) {
      error.value = `“${session.asset.title}”还有未保存修改。请先保存或使用“放弃草稿”，再关闭标签。`;
      return false;
    }
    const closingKey = sessions.key(id, kind);
    const index = sessions.remove(id, kind);
    if (activeTabKey.value !== closingKey) return true;

    editor.reset();
    activeTabKey.value = "";
    const fallback = sessions.fallback(index);
    if (fallback?.kind === "asset") await openAsset(fallback.id);
    if (fallback?.kind === "candidate") await openCandidate(fallback.id);
    return true;
  }

  async function discardCurrentDraft(): Promise<void> {
    const asset = requireAsset();
    draft.value = asset.content;
    validation.value = null;
    impact.value = null;
    structuredDocument.value = null;
    persistCurrentAssetSession();
    await reloadStructuredDocument();
    notice.value = "未保存的修改已放弃，当前标签恢复到正式版本。";
  }

  function clearMessages(): void {
    error.value = "";
    notice.value = "";
  }

  function persistCurrentAssetSession(): void {
    const snapshot = editor.snapshot();
    if (snapshot) sessions.save(snapshot);
  }

  function resetEditorWorkspace(): void {
    sessions.reset();
    editor.reset();
  }

  function requireAsset(): ArchiveAssetDetail {
    if (!selectedAsset.value) throw new Error("请先选择一份正式资料。");
    return selectedAsset.value;
  }

  async function refreshAfterMutation(assetId: string): Promise<void> {
    const refreshed = await refreshArchiveMutation(projectRoot.value, assetId);
    history.value = refreshed.history;
    assetGroups.value = refreshed.groups;
  }

  return {
    assetGroups,
    candidates,
    recycleEntries,
    creationOptions,
    creationPreview,
    selectedAsset,
    selectedCandidate,
    history,
    draft,
    structuredDocument,
    validation,
    impact,
    promotionJob,
    busy,
    error,
    notice,
    openTabs,
    dirty,
    dirtyAssetIds,
    loadWorkspace,
    openAsset,
    openCandidate,
    updateDraft,
    applyStructuredFields,
    reloadStructuredDocument,
    previewEdit,
    commitEdit,
    previewCreation,
    createAsset,
    resetCreationPreview,
    archiveAsset,
    restoreEntry,
    promoteCandidate,
    refreshCandidate,
    closeTab,
    discardCurrentDraft,
    clearMessages,
  };
});
