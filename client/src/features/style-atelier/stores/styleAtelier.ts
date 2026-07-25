import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import { useAppStore } from "@/stores/app";
import {
  fetchStyleVersionDetail,
  fetchStyleWorkbench,
} from "../services/styleAtelierClient";
import type {
  StyleAuthor,
  StyleVersion,
  StyleVersionDetail,
  StyleWork,
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
  const error = ref("");

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
    workbench.value = null;
    loadedProjectRoot.value = "";
    error.value = "";
    resetSelections();
  }

  function clearError(): void {
    error.value = "";
  }

  return {
    workbench,
    versionDetail,
    selectedAuthorId,
    selectedWorkId,
    selectedVersionKey,
    busy,
    detailBusy,
    error,
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
    clearError,
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
