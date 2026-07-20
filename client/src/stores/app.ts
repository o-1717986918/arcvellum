import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import { api, bootstrapDesktopSession, connectEventStream, query, type EventStreamConnection } from "@/services/api";
import type {
  BootstrapSnapshot,
  DashboardResponse,
  DeliveryResponse,
  LibraryResponse,
  ModelCatalog,
  ProjectSummary,
  ProjectsResponse,
  ReaderManifest,
  ReaderUnitResponse,
} from "@/types/api";

export const useAppStore = defineStore("app", () => {
  const initialized = ref(false);
  const loading = ref(false);
  const error = ref("");
  const notice = ref("");
  const bootstrap = shallowRef<BootstrapSnapshot | null>(null);
  const projects = ref<ProjectSummary[]>([]);
  const currentProjectPath = ref(localStorage.getItem("arcvellum.currentProject") || "");
  const dashboard = shallowRef<DashboardResponse | null>(null);
  const library = shallowRef<LibraryResponse | null>(null);
  const delivery = shallowRef<DeliveryResponse | null>(null);
  const readerManifest = shallowRef<ReaderManifest | null>(null);
  const readerBodies = ref<Record<string, { hash: string; body: string }>>({});
  const modelCatalog = shallowRef<ModelCatalog | null>(null);
  const activeJob = shallowRef<Record<string, unknown> | null>(null);
  let bootstrapStream: EventStreamConnection | null = null;
  let dashboardStream: EventStreamConnection | null = null;
  let libraryStream: EventStreamConnection | null = null;
  let readerStream: EventStreamConnection | null = null;

  const currentProject = computed(
    () => projects.value.find((item) => item.path === currentProjectPath.value) || bootstrap.value?.project || null,
  );
  const hasProject = computed(() => Boolean(currentProjectPath.value));

  async function initialize(): Promise<void> {
    if (initialized.value || loading.value) return;
    loading.value = true;
    error.value = "";
    try {
      await bootstrapDesktopSession();
      bootstrap.value = await api<BootstrapSnapshot>("/application/bootstrap");
      if (bootstrap.value.model_catalog) modelCatalog.value = bootstrap.value.model_catalog;
      await loadProjects();
      startBootstrapStream();
      initialized.value = true;
    } catch (cause) {
      error.value = friendlyError(cause, "ArcVellum 暂时无法完成启动，请重试。");
    } finally {
      loading.value = false;
    }
  }

  async function loadProjects(): Promise<void> {
    const response = await api<ProjectsResponse>("/projects");
    projects.value = response.projects || [];
    const remembered = projects.value.some((item) => item.path === currentProjectPath.value);
    const preferred = remembered ? currentProjectPath.value : response.current_project || response.projects[0]?.path || "";
    if (preferred) setCurrentProject(preferred, false);
  }

  function setCurrentProject(path: string, refresh = true): void {
    currentProjectPath.value = path;
    localStorage.setItem("arcvellum.currentProject", path);
    stopProjectStreams();
    dashboard.value = null;
    library.value = null;
    delivery.value = null;
    readerManifest.value = null;
    readerBodies.value = {};
    if (refresh && path) void refreshWorkspace();
  }

  async function createProject(payload: Record<string, unknown>): Promise<ProjectSummary> {
    const response = await api<{ ok: boolean; project: ProjectSummary }>("/projects/create", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    await loadProjects();
    setCurrentProject(response.project.path);
    notice.value = `《${response.project.title}》已经建立。`;
    return response.project;
  }

  async function openProject(projectRoot: string): Promise<ProjectSummary> {
    const response = await api<{ ok: boolean; project: ProjectSummary }>("/projects/open", {
      method: "POST",
      body: JSON.stringify({ project_root: projectRoot }),
    });
    await loadProjects();
    setCurrentProject(response.project.path);
    notice.value = `已打开《${response.project.title}》。`;
    return response.project;
  }

  async function refreshWorkspace(): Promise<void> {
    if (!currentProjectPath.value) return;
    error.value = "";
    await Promise.allSettled([loadDashboard(), loadLibrary(), loadDelivery(), loadReaderManifest()]);
    startProjectStreams();
  }

  async function loadDashboard(): Promise<void> {
    if (!currentProjectPath.value) return;
    dashboard.value = await api<DashboardResponse>(
      `/workflow/dashboard?${query({ project_root: currentProjectPath.value })}`,
    );
  }

  async function loadLibrary(): Promise<void> {
    if (!currentProjectPath.value) return;
    library.value = await api<LibraryResponse>(`/project/library?${query({ project_root: currentProjectPath.value })}`);
  }

  async function loadDelivery(): Promise<void> {
    if (!currentProjectPath.value) return;
    delivery.value = await api<DeliveryResponse>(`/project/delivery?${query({ project_root: currentProjectPath.value })}`);
  }

  async function loadReaderManifest(): Promise<void> {
    if (!currentProjectPath.value) return;
    readerManifest.value = await api<ReaderManifest>(
      `/reader/manifest?${query({ project_root: currentProjectPath.value })}`,
    );
  }

  async function loadReaderUnit(unitId: string): Promise<string> {
    const summary = readerManifest.value?.units.find((item) => item.unit_id === unitId);
    const cached = readerBodies.value[unitId];
    if (cached && summary && cached.hash === summary.content_hash) return cached.body;
    const response = await api<ReaderUnitResponse>(
      `/reader/units/${encodeURIComponent(unitId)}?${query({ project_root: currentProjectPath.value })}`,
    );
    readerBodies.value = {
      ...readerBodies.value,
      [unitId]: { hash: response.unit.content_hash, body: response.body },
    };
    return response.body;
  }

  async function loadModelCatalog(force = false): Promise<void> {
    void force;
    const catalog = await api<ModelCatalog & { ok: boolean }>("/model-connections/opencode/catalog");
    modelCatalog.value = catalog;
  }

  function startBootstrapStream(): void {
    if (bootstrapStream) return;
    bootstrapStream = connectEventStream("/application/bootstrap/stream?interval_seconds=1", (event, data) => {
      if (event !== "application.bootstrap") return;
      const payload = data as unknown as BootstrapSnapshot;
      bootstrap.value = payload;
      if (payload.model_catalog) modelCatalog.value = payload.model_catalog;
      if (payload.can_enter_workspace && payload.model_warmup.status !== "loading") {
        bootstrapStream?.close();
        bootstrapStream = null;
      }
    });
  }

  function startProjectStreams(): void {
    stopProjectStreams();
    const root = currentProjectPath.value;
    if (!root) return;
    dashboardStream = connectEventStream(
      `/workflow/dashboard/stream?${query({ project_root: root, interval_seconds: 5 })}`,
      (event, data) => {
        if (event === "dashboard") dashboard.value = data as unknown as DashboardResponse;
      },
    );
    libraryStream = connectEventStream(
      `/project/library/stream?${query({ project_root: root, interval_seconds: 7 })}`,
      (event, data) => {
        if (event === "library") library.value = data as unknown as LibraryResponse;
      },
    );
    readerStream = connectEventStream(
      `/reader/stream?${query({ project_root: root, interval_seconds: 4 })}`,
      (event, data) => {
        if (event !== "reader.manifest") return;
        const manifest = data as unknown as ReaderManifest;
        const added = manifest.delta?.initial ? [] : manifest.delta?.added || [];
        readerManifest.value = manifest;
        if (added.length) notice.value = `有 ${added.length} 节新正文进入阅读长卷。`;
      },
    );
  }

  function stopProjectStreams(): void {
    dashboardStream?.close();
    libraryStream?.close();
    readerStream?.close();
    dashboardStream = null;
    libraryStream = null;
    readerStream = null;
  }

  function clearMessages(): void {
    error.value = "";
    notice.value = "";
  }

  return {
    initialized,
    loading,
    error,
    notice,
    bootstrap,
    projects,
    currentProjectPath,
    currentProject,
    hasProject,
    dashboard,
    library,
    delivery,
    readerManifest,
    readerBodies,
    modelCatalog,
    activeJob,
    initialize,
    loadProjects,
    setCurrentProject,
    createProject,
    openProject,
    refreshWorkspace,
    loadDashboard,
    loadLibrary,
    loadDelivery,
    loadReaderManifest,
    loadReaderUnit,
    loadModelCatalog,
    clearMessages,
    stopProjectStreams,
  };
});

export function friendlyError(cause: unknown, fallback: string): string {
  if (cause instanceof Error && cause.message.trim()) {
    return cause.message
      .replace("not a Literary Engineering work project", "这里没有找到 ArcVellum 作品")
      .replace("project.yaml", "作品入口文件");
  }
  return fallback;
}
