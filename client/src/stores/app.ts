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
  AutopilotRun,
  AutopilotStatus,
  AgentObservability,
  ProjectProgress,
} from "@/types/api";

interface ProjectWorkspaceSnapshot {
  dashboard: DashboardResponse;
  library: LibraryResponse;
  delivery: DeliveryResponse;
  reader_manifest: ReaderManifest;
  project_progress: ProjectProgress;
  autopilot_status: AutopilotStatus;
  agent_observability: AgentObservability;
}

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
  const autopilotStatus = shallowRef<AutopilotStatus | null>(null);
  const projectProgress = shallowRef<ProjectProgress | null>(null);
  const agentObservability = shallowRef<AgentObservability | null>(null);
  let bootstrapStream: EventStreamConnection | null = null;
  let workspaceStream: EventStreamConnection | null = null;
  let autopilotStream: EventStreamConnection | null = null;

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
    autopilotStatus.value = null;
    projectProgress.value = null;
    agentObservability.value = null;
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
    const snapshot = await api<ProjectWorkspaceSnapshot>(
      `/project/workspace?${query({ project_root: currentProjectPath.value })}`,
    );
    applyWorkspaceSnapshot(snapshot);
    startProjectStreams();
  }

  function applyWorkspaceSnapshot(snapshot: ProjectWorkspaceSnapshot): void {
    const manifest = snapshot.reader_manifest;
    const added = manifest?.delta?.initial ? [] : manifest?.delta?.added || [];
    dashboard.value = snapshot.dashboard;
    library.value = snapshot.library;
    delivery.value = snapshot.delivery;
    readerManifest.value = manifest;
    projectProgress.value = snapshot.project_progress;
    autopilotStatus.value = snapshot.autopilot_status;
    agentObservability.value = snapshot.agent_observability;
    if (added.length) notice.value = `有 ${added.length} 节新正文进入阅读长卷。`;
  }

  async function loadAutopilotStatus(): Promise<void> {
    if (!currentProjectPath.value) return;
    autopilotStatus.value = await api<AutopilotStatus>(
      `/autopilot/status?${query({ project_root: currentProjectPath.value })}`,
    );
  }

  function setAutopilotStatus(value: AutopilotStatus | null): void {
    autopilotStatus.value = value;
  }

  function setAutopilotRun(run: AutopilotRun): void {
    if (!autopilotStatus.value) return;
    autopilotStatus.value = { ...autopilotStatus.value, run };
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

  async function loadProjectProgress(): Promise<void> {
    if (!currentProjectPath.value) return;
    projectProgress.value = await api<ProjectProgress>(
      `/project/progress?${query({ project_root: currentProjectPath.value })}`,
    );
  }

  async function loadAgentObservability(): Promise<void> {
    if (!currentProjectPath.value) return;
    agentObservability.value = await api<AgentObservability>(
      `/agent-observability?${query({ project_root: currentProjectPath.value })}`,
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
    workspaceStream = connectEventStream(
      `/project/workspace/stream?${query({ project_root: root, interval_seconds: 2 })}`,
      (event, data) => {
        if (event !== "workspace.snapshot") return;
        applyWorkspaceSnapshot(data as unknown as ProjectWorkspaceSnapshot);
      },
    );
    const activeRun = autopilotStatus.value?.run;
    if (activeRun?.status === "running") {
      autopilotStream = connectEventStream(
        `/autopilot/runs/${encodeURIComponent(activeRun.run_id)}/stream`,
        (event, data) => {
          if (event !== "autopilot.status") return;
          const payload = data as unknown as { run: AutopilotRun };
          setAutopilotRun(payload.run);
          if (["complete", "paused", "blocked", "cancelled", "failed"].includes(payload.run.status)) {
            autopilotStream?.close();
            autopilotStream = null;
          }
        },
      );
    }
  }

  function stopProjectStreams(): void {
    workspaceStream?.close();
    autopilotStream?.close();
    workspaceStream = null;
    autopilotStream = null;
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
    autopilotStatus,
    projectProgress,
    agentObservability,
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
    loadProjectProgress,
    loadAgentObservability,
    loadReaderUnit,
    loadAutopilotStatus,
    setAutopilotStatus,
    setAutopilotRun,
    loadModelCatalog,
    clearMessages,
    stopProjectStreams,
  };
});

export function friendlyError(cause: unknown, fallback: string): string {
  if (cause instanceof Error && cause.message.trim()) {
    if (/failed to fetch|cannot\s*fetch|load failed|networkerror/i.test(cause.message)) {
      return "本地创作服务没有连接成功。请重新启动 ArcVellum；如果仍然失败，请在“使用帮助”中导出诊断信息。";
    }
    return cause.message
      .replace("not a Literary Engineering work project", "这里没有找到 ArcVellum 作品")
      .replace("project.yaml", "作品入口文件");
  }
  return fallback;
}
