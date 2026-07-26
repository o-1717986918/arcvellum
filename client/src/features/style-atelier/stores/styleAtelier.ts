import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import { useAppStore } from "@/stores/app";
import {
  advanceStyleProfile,
  buildStyleProfile,
  compileStyleProfile,
  createStyleAuthor,
  createStyleWork,
  fetchStyleVersionDetail,
  fetchStyleWorkbench,
  importStyleSource,
  mountStyleVersion,
  previewStyleMount,
} from "../services/styleAtelierClient";
import { useStyleEngineeringSession } from "./styleEngineeringSession";
import type {
  StyleAdvancePayload,
  StyleAuthor,
  StyleAuthorCreatePayload,
  StyleBuildPayload,
  StyleCompilePayload,
  StyleMountPayload,
  StyleMountPreview,
  StyleSourceCreatePayload,
  StyleTransactionReceipt,
  StyleVersion,
  StyleVersionDetail,
  StyleWork,
  StyleWorkCreatePayload,
} from "../types";

export const useStyleAtelierStore = defineStore("style-atelier", () => {
  const app = useAppStore();
  const workbench = shallowRef<Awaited<ReturnType<typeof fetchStyleWorkbench>> | null>(null);
  const versionDetail = shallowRef<StyleVersionDetail | null>(null);
  const selectedAuthorId = ref("");
  const selectedWorkId = ref("");
  const selectedVersionKey = ref("");
  const loadedProjectRoot = ref("");
  const busy = ref(false);
  const detailBusy = ref(false);
  const authoringBusy = ref(false);
  const mountBusy = ref(false);
  const mountPreview = shallowRef<StyleMountPreview | null>(null);
  const error = ref("");
  const notice = ref("");
  const engineering = useStyleEngineeringSession({
    refreshWorkbench,
    refreshObservability: async () => {
      await app.loadAgentObservability();
    },
    setError: (message) => {
      error.value = message;
    },
    setNotice: (message) => {
      notice.value = message;
    },
  });

  const projectRoot = computed(() => app.currentProjectPath);
  const authors = computed(() => workbench.value?.authors || []);
  const versions = computed(() => workbench.value?.versions || []);
  const activeMount = computed(() => workbench.value?.active_mount || {});
  const selectedAuthor = computed<StyleAuthor | null>(
    () => authors.value.find((item) => item.author_id === selectedAuthorId.value) || authors.value[0] || null,
  );
  const works = computed<StyleWork[]>(() => selectedAuthor.value?.works || []);
  const selectedWork = computed<StyleWork | null>(
    () => works.value.find((item) => item.work_id === selectedWorkId.value) || works.value[0] || null,
  );
  const selectedVersion = computed<StyleVersion | null>(
    () => versions.value.find((item) => versionKey(item) === selectedVersionKey.value) || versions.value[0] || null,
  );

  async function load(): Promise<void> {
    if (!projectRoot.value) {
      reset();
      return;
    }
    busy.value = true;
    error.value = "";
    try {
      if (loadedProjectRoot.value && loadedProjectRoot.value !== projectRoot.value) resetSelections();
      loadedProjectRoot.value = projectRoot.value;
      workbench.value = await fetchStyleWorkbench(projectRoot.value);
      stabilizeSelections();
      await loadSelectedVersionDetail();
    } catch (cause) {
      error.value = messageFor(cause, "文风工坊暂时没有读取成功。");
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  async function createAuthor(payload: StyleAuthorCreatePayload): Promise<StyleTransactionReceipt> {
    return runAuthoring(
      () => createStyleAuthor(payload),
      (receipt) => {
        selectedAuthorId.value = receipt.subject.author_id;
        selectedWorkId.value = "";
      },
      "作者资料已经建立，可以继续登记作品。",
    );
  }

  async function createWork(payload: StyleWorkCreatePayload): Promise<StyleTransactionReceipt> {
    return runAuthoring(
      () => createStyleWork(payload),
      (receipt) => {
        selectedAuthorId.value = receipt.subject.author_id;
        selectedWorkId.value = receipt.subject.work_id || "";
      },
      "作品资料已经建立，可以继续导入来源。",
    );
  }

  async function importSource(payload: StyleSourceCreatePayload): Promise<StyleTransactionReceipt> {
    const receipts = await importSources([payload]);
    return receipts[0];
  }

  async function importSources(payloads: StyleSourceCreatePayload[]): Promise<StyleTransactionReceipt[]> {
    if (!payloads.length) return [];
    authoringBusy.value = true;
    error.value = "";
    notice.value = "";
    const receipts: StyleTransactionReceipt[] = [];
    try {
      for (const payload of payloads) {
        const receipt = await importStyleSource(payload);
        receipts.push(receipt);
        selectedAuthorId.value = receipt.subject.author_id;
        selectedWorkId.value = receipt.subject.work_id || "";
      }
      await refreshWorkbench();
      notice.value = receipts.length === 1
        ? "来源已经固化，正文不会在工作台中直接回显。"
        : `${receipts.length} 份来源已经固化，可以继续构建文风档案。`;
      return receipts;
    } catch (cause) {
      if (receipts.length) await refreshWorkbench();
      const reason = messageFor(cause, "这项文风资料操作没有完成。");
      error.value = receipts.length
        ? `已固化 ${receipts.length} 份来源，其余文件未完成：${reason}`
        : reason;
      throw cause;
    } finally {
      authoringBusy.value = false;
    }
  }

  async function previewMount(version = selectedVersion.value): Promise<void> {
    if (!projectRoot.value || !isMountableVersion(version)) return;
    mountBusy.value = true;
    error.value = "";
    notice.value = "";
    try {
      mountPreview.value = await previewStyleMount(
        mountPayload(projectRoot.value, version),
      );
    } catch (cause) {
      error.value = messageFor(cause, "当前文风版本的挂载影响没有读取成功。");
      throw cause;
    } finally {
      mountBusy.value = false;
    }
  }

  async function confirmMount(): Promise<void> {
    const preview = mountPreview.value;
    const version = selectedVersion.value;
    if (!projectRoot.value || !preview || !isMountableVersion(version)) return;
    mountBusy.value = true;
    error.value = "";
    try {
      const transaction = await mountStyleVersion({
        ...mountPayload(projectRoot.value, version),
        preview_revision: preview.revision,
      });
      mountPreview.value = null;
      await refreshWorkbench();
      notice.value = transaction.status === "mounted"
        ? "文风版本已经挂载；后续创作与审查将使用同一份不可变快照。"
        : "当前作品已经在使用这个文风版本。";
    } catch (cause) {
      error.value = messageFor(cause, "文风版本没有成功挂载，请重新预览影响后再确认。");
      throw cause;
    } finally {
      mountBusy.value = false;
    }
  }

  function dismissMountPreview(): void {
    mountPreview.value = null;
  }

  async function compileProfile(payload: Omit<StyleCompilePayload, "project_root">): Promise<void> {
    if (!projectRoot.value) return;
    engineering.authorId.value = payload.author_id;
    engineering.profileId.value = payload.profile_id;
    await engineering.launch(() => compileStyleProfile({
      ...payload,
      project_root: projectRoot.value,
    }));
  }

  async function advanceProfile(
    authorId = selectedVersion.value?.author_id || engineering.authorId.value,
    profileId = selectedVersion.value?.profile_id || engineering.profileId.value,
  ): Promise<void> {
    if (!projectRoot.value || !authorId || !profileId) return;
    engineering.authorId.value = authorId;
    engineering.profileId.value = profileId;
    const payload: StyleAdvancePayload = {
      project_root: projectRoot.value,
      author_id: authorId,
      profile_id: profileId,
      runtime: "opencode",
    };
    await engineering.launch(() => advanceStyleProfile(payload));
  }

  async function buildProfile(
    authorId = selectedVersion.value?.author_id || engineering.authorId.value,
    profileId = selectedVersion.value?.profile_id || engineering.profileId.value,
  ): Promise<void> {
    if (!projectRoot.value || !authorId || !profileId) return;
    engineering.authorId.value = authorId;
    engineering.profileId.value = profileId;
    const payload: StyleBuildPayload = {
      project_root: projectRoot.value,
      author_id: authorId,
      profile_id: profileId,
      runtime: "opencode",
    };
    await engineering.launch(() => buildStyleProfile(payload));
  }

  async function runAuthoring(
    operation: () => Promise<StyleTransactionReceipt>,
    selectSubject: (receipt: StyleTransactionReceipt) => void,
    successMessage: string,
  ): Promise<StyleTransactionReceipt> {
    authoringBusy.value = true;
    error.value = "";
    notice.value = "";
    try {
      const receipt = await operation();
      selectSubject(receipt);
      await refreshWorkbench();
      notice.value = successMessage;
      return receipt;
    } catch (cause) {
      error.value = messageFor(cause, "这项文风资料操作没有完成。");
      throw cause;
    } finally {
      authoringBusy.value = false;
    }
  }

  async function refreshWorkbench(): Promise<void> {
    if (!projectRoot.value) return;
    workbench.value = await fetchStyleWorkbench(projectRoot.value);
    stabilizeSelections();
    await loadSelectedVersionDetail();
  }

  function selectAuthor(authorId: string): void {
    selectedAuthorId.value = authorId;
    selectedWorkId.value = selectedAuthor.value?.works[0]?.work_id || "";
    const matching = versions.value.find((item) => item.author_id === authorId);
    if (matching) {
      selectedVersionKey.value = versionKey(matching);
      void loadSelectedVersionDetail();
    }
  }

  function selectWork(workId: string): void {
    selectedWorkId.value = workId;
  }

  async function selectVersion(version: StyleVersion): Promise<void> {
    mountPreview.value = null;
    selectedVersionKey.value = versionKey(version);
    if (version.author_id && authors.value.some((item) => item.author_id === version.author_id)) {
      selectedAuthorId.value = version.author_id;
      selectedWorkId.value = selectedAuthor.value?.works[0]?.work_id || "";
    }
    await loadSelectedVersionDetail();
  }

  async function loadSelectedVersionDetail(): Promise<void> {
    versionDetail.value = null;
    const version = selectedVersion.value;
    if (!projectRoot.value || !version?.built || !version.style_id || !version.version_id) return;
    detailBusy.value = true;
    try {
      versionDetail.value = await fetchStyleVersionDetail(
        projectRoot.value,
        version.style_id,
        version.version_id,
      );
    } catch (cause) {
      error.value = messageFor(cause, "这个文风版本的证据详情暂时无法读取。");
    } finally {
      detailBusy.value = false;
    }
  }

  function stabilizeSelections(): void {
    if (!authors.value.some((item) => item.author_id === selectedAuthorId.value)) {
      selectedAuthorId.value = preferredAuthor(authors.value)?.author_id || "";
    }
    if (!works.value.some((item) => item.work_id === selectedWorkId.value)) {
      selectedWorkId.value = works.value[0]?.work_id || "";
    }
    if (!versions.value.some((item) => versionKey(item) === selectedVersionKey.value)) {
      const mounted = versions.value.find((item) => item.mounted);
      const matching = versions.value.find((item) => item.author_id === selectedAuthorId.value);
      selectedVersionKey.value = versionKey(mounted || matching || versions.value[0]);
    }
  }

  function resetSelections(): void {
    selectedAuthorId.value = "";
    selectedWorkId.value = "";
    selectedVersionKey.value = "";
    versionDetail.value = null;
  }

  function reset(): void {
    engineering.reset();
    workbench.value = null;
    loadedProjectRoot.value = "";
    error.value = "";
    notice.value = "";
    mountPreview.value = null;
    resetSelections();
  }

  function clearError(): void {
    error.value = "";
  }

  function clearNotice(): void {
    notice.value = "";
  }

  return {
    workbench,
    versionDetail,
    selectedAuthorId,
    selectedWorkId,
    selectedVersionKey,
    busy,
    detailBusy,
    authoringBusy,
    mountBusy,
    mountPreview,
    engineeringBusy: engineering.busy,
    engineeringJob: engineering.job,
    engineeringTask: engineering.task,
    engineeringEvents: engineering.events,
    engineeringStreamError: engineering.streamError,
    engineeringAuthorId: engineering.authorId,
    engineeringProfileId: engineering.profileId,
    error,
    notice,
    projectRoot,
    authors,
    versions,
    activeMount,
    selectedAuthor,
    works,
    selectedWork,
    selectedVersion,
    load,
    selectAuthor,
    selectWork,
    selectVersion,
    createAuthor,
    createWork,
    importSource,
    importSources,
    previewMount,
    confirmMount,
    dismissMountPreview,
    compileProfile,
    advanceProfile,
    buildProfile,
    approveWriteback: engineering.approveWriteback,
    rejectWriteback: engineering.rejectWriteback,
    retryEngineering: engineering.retry,
    stopEngineering: engineering.stop,
    disposeEngineeringStream: engineering.dispose,
    clearError,
    clearNotice,
  };
});

function versionKey(version?: StyleVersion): string {
  if (!version) return "";
  return `${version.style_id}:${version.version_id || version.planned_version_id || version.profile_id}`;
}

function preferredAuthor(authors: StyleAuthor[]): StyleAuthor | undefined {
  return [...authors].sort((left, right) => {
    const sourceDifference = sourceCount(right) - sourceCount(left);
    if (sourceDifference) return sourceDifference;
    return Number(right.profile_count || 0) - Number(left.profile_count || 0);
  })[0];
}

function sourceCount(author: StyleAuthor): number {
  return author.works.reduce((sum, work) => sum + Number(work.source_count || 0), 0);
}

function messageFor(cause: unknown, fallback: string): string {
  return cause instanceof Error && cause.message ? cause.message : fallback;
}

function isMountableVersion(version: StyleVersion | null): version is StyleVersion {
  return Boolean(
    version?.built
    && version.style_id
    && version.version_id
    && version.content_hash
    && version.state !== "conflict",
  );
}

function mountPayload(projectRoot: string, version: StyleVersion): StyleMountPayload {
  return {
    project_root: projectRoot,
    style_id: version.style_id,
    version_id: version.version_id,
    content_hash: version.content_hash,
    scope: "project",
    priority: "highest",
  };
}
