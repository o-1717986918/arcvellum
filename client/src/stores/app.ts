import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import { api, bootstrapDesktopSession, query, sseUrl } from "@/services/api";
import type {
  BootstrapSnapshot,
  DashboardResponse,
  DeliveryResponse,
  LibraryResponse,
  ModelCatalog,
  ProjectSummary,
  ProjectsResponse,
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
  const modelCatalog = shallowRef<ModelCatalog | null>(null);
  const activeJob = shallowRef<Record<string, unknown> | null>(null);
  let bootstrapStream: EventSource | null = null;
  let dashboardStream: EventSource | null = null;
  let libraryStream: EventSource | null = null;

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
    await Promise.allSettled([loadDashboard(), loadLibrary(), loadDelivery()]);
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

  async function loadModelCatalog(force = false): Promise<void> {
    const response = force
      ? await api<{ ok: boolean; bootstrap: BootstrapSnapshot }>("/application/warmup", { method: "POST" })
      : null;
    if (response?.bootstrap) bootstrap.value = response.bootstrap;
    const catalog = await api<ModelCatalog & { ok: boolean }>("/model-connections/opencode/catalog");
    modelCatalog.value = catalog;
  }

  function startBootstrapStream(): void {
    if (!window.EventSource || bootstrapStream) return;
    bootstrapStream = new EventSource(sseUrl("/application/bootstrap/stream?interval_seconds=1"));
    bootstrapStream.addEventListener("application.bootstrap", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as BootstrapSnapshot;
      bootstrap.value = payload;
      if (payload.model_catalog) modelCatalog.value = payload.model_catalog;
      if (payload.can_enter_workspace && !["loading", "waiting"].includes(payload.model_warmup.status)) {
        bootstrapStream?.close();
        bootstrapStream = null;
      }
    });
  }

  function startProjectStreams(): void {
    stopProjectStreams();
    const root = currentProjectPath.value;
    if (!root || !window.EventSource) return;
    dashboardStream = new EventSource(
      sseUrl(`/workflow/dashboard/stream?${query({ project_root: root, interval_seconds: 5 })}`),
    );
    dashboardStream.addEventListener("dashboard", (event) => {
      dashboard.value = JSON.parse((event as MessageEvent).data) as DashboardResponse;
    });
    libraryStream = new EventSource(
      sseUrl(`/project/library/stream?${query({ project_root: root, interval_seconds: 7 })}`),
    );
    libraryStream.addEventListener("library", (event) => {
      library.value = JSON.parse((event as MessageEvent).data) as LibraryResponse;
    });
  }

  function stopProjectStreams(): void {
    dashboardStream?.close();
    libraryStream?.close();
    dashboardStream = null;
    libraryStream = null;
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
