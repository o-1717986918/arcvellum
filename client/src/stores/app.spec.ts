import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.fn();
const bootstrapDesktopSessionMock = vi.fn();
const streamConnections: Array<{ path: string; callback: (event: string, data: Record<string, unknown>) => void; closed: boolean }> = [];

vi.mock("@/services/api", () => ({
  api: apiMock,
  bootstrapDesktopSession: bootstrapDesktopSessionMock,
  query: (values: Record<string, string | number | undefined>) => {
    const params = new URLSearchParams();
    Object.entries(values).forEach(([key, value]) => {
      if (value !== undefined && value !== "") params.set(key, String(value));
    });
    return params.toString();
  },
  connectEventStream: (path: string, callback: (event: string, data: Record<string, unknown>) => void) => {
    const connection = { path, callback, closed: false };
    streamConnections.push(connection);
    return { close: () => (connection.closed = true) };
  },
}));

const bootstrap = {
  ok: true,
  schema: "arcvellum/application-bootstrap/v0.1",
  phase: "degraded",
  ready: true,
  can_enter_workspace: true,
  degraded: true,
  progress: { completed: 7, total: 8 },
  steps: [],
  notices: ["模型目录将在后台重试。"],
  project: null,
  project_count: 1,
  model_catalog: { selected_model: "opencode/big-pickle", providers: [] },
  model_warmup: { status: "degraded", attempted_at: "", loaded_at: "", error: "离线" },
};

describe("application store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    streamConnections.length = 0;
    apiMock.mockReset();
    bootstrapDesktopSessionMock.mockReset();
    apiMock.mockImplementation(async (path: string) => {
      if (path === "/application/bootstrap") return bootstrap;
      if (path === "/projects") {
        return {
          ok: true,
          current_project: "C:\\ArcVellum\\潮汐之后",
          projects: [
            {
              path: "C:\\ArcVellum\\潮汐之后",
              title: "潮汐之后",
              work_type: "novel",
              target_length: 30000,
              status: "active",
              genre: "现实",
              premise: "一座港口城的旧约重新浮现。",
              direction_count: 1,
            },
          ],
        };
      }
      if (path.startsWith("/project/workspace?")) return {
        dashboard: { ok: true, current_task: { title: "梳理人物" } },
        library: { ok: true, sections: { characters: [] } },
        delivery: { ok: true, project_root: "C:\\ArcVellum\\潮汐之后", status: "draft", files: [] },
        reader_manifest: { ok: true, units: [], delta: { added: [], removed: [], initial: true } },
        project_progress: { ok: true, status: "waiting_calibration", overall_percent: null, parts: [] },
        autopilot_status: { ok: true, run: null },
        agent_observability: { ok: true, status: "idle", active_task: null, sessions: [], recent_events: [] },
      };
      if (path.startsWith("/workflow/dashboard")) return { ok: true, current_task: { title: "梳理人物" } };
      if (path.startsWith("/project/library")) return { ok: true, sections: { characters: [] } };
      if (path.startsWith("/project/delivery")) return { ok: true, project_root: "C:\\ArcVellum\\潮汐之后", status: "draft", files: [] };
      if (path.startsWith("/reader/manifest")) return { ok: true, units: [], delta: { added: [], removed: [], initial: true } };
      if (path.startsWith("/project/progress")) return { ok: true, status: "waiting_calibration", overall_percent: null, parts: [] };
      if (path.startsWith("/autopilot/status")) return { ok: true, run: null };
      if (path.startsWith("/agent-observability")) return { ok: true, status: "idle", active_task: null, sessions: [], recent_events: [] };
      throw new Error(`Unexpected API path: ${path}`);
    });
  });

  it("restores the current project and cached model without opening settings", async () => {
    const { useAppStore } = await import("./app");
    const store = useAppStore();

    await store.initialize();

    expect(bootstrapDesktopSessionMock).toHaveBeenCalledOnce();
    expect(store.initialized).toBe(true);
    expect(store.currentProject?.title).toBe("潮汐之后");
    expect(store.modelCatalog?.selected_model).toBe("opencode/big-pickle");
    expect(streamConnections).toHaveLength(1);
  });

  it("does not let a stale startup stream replace a model selected in settings", async () => {
    const { useAppStore } = await import("./app");
    const store = useAppStore();
    await store.initialize();
    apiMock.mockImplementation(async (path: string) => {
      if (path === "/model-connections/opencode/catalog") {
        return {
          selected_model: "deepseek/deepseek-chat",
          selected_models: { worker: "deepseek/deepseek-chat" },
          providers: [],
        };
      }
      throw new Error(`Unexpected API path: ${path}`);
    });

    await store.loadModelCatalog();
    const stream = streamConnections.find((item) => item.path.startsWith("/application/bootstrap/stream"));
    stream?.callback("application.bootstrap", {
      ...bootstrap,
      model_catalog: {
        selected_model: "opencode/deepseek-v4-flash-free",
        providers: [],
      },
    });

    expect(store.modelCatalog?.selected_model).toBe("deepseek/deepseek-chat");
    expect(store.bootstrap?.model_catalog?.selected_model).toBe("deepseek/deepseek-chat");
  });

  it("uses one workspace stream for the active project's live read models", async () => {
    const { useAppStore } = await import("./app");
    const store = useAppStore();
    await store.initialize();

    await store.refreshWorkspace();

    expect(store.dashboard?.current_task).toEqual({ title: "梳理人物" });
    expect(store.library?.sections).toEqual({ characters: [] });
    const initialReadPaths = apiMock.mock.calls.map(([path]) => String(path));
    expect(initialReadPaths.filter((path) => path.startsWith("/project/workspace?"))).toHaveLength(1);
    expect(initialReadPaths.some((path) => path.startsWith("/workflow/dashboard?"))).toBe(false);
    expect(initialReadPaths.some((path) => path.startsWith("/project/library?"))).toBe(false);
    const projectStreams = streamConnections.filter((item) => item.path.includes("/stream"));
    expect(projectStreams.filter((item) => item.path.startsWith("/project/workspace/stream"))).toHaveLength(1);
    expect(projectStreams.filter((item) => item.path.startsWith("/agent-observability/stream"))).toHaveLength(1);

    const workspaceStream = projectStreams.find((item) => item.path.startsWith("/project/workspace/stream"));
    workspaceStream?.callback("workspace.snapshot", {
      dashboard: { ok: true, current_task: { title: "开始写第一场" } },
      library: { ok: true, sections: { characters: [] } },
      delivery: { ok: true, project_root: "C:\\ArcVellum\\潮汐之后", status: "draft", files: [] },
      reader_manifest: { ok: true, units: [], delta: { added: [], removed: [], initial: true } },
      project_progress: { ok: true, status: "waiting_calibration", overall_percent: null, parts: [] },
      autopilot_status: { ok: true, run: null },
      agent_observability: { ok: true, status: "idle", active_task: null, sessions: [], recent_events: [] },
    });
    expect(store.dashboard?.current_task).toEqual({ title: "开始写第一场" });
  });

  it("coalesces concurrent workspace refreshes for one large project", async () => {
    const { useAppStore } = await import("./app");
    const store = useAppStore();
    await store.initialize();
    let releaseSnapshot!: (value: Record<string, unknown>) => void;
    const snapshot = new Promise<Record<string, unknown>>((resolve) => (releaseSnapshot = resolve));
    apiMock.mockImplementation(async (path: string) => {
      if (path.startsWith("/project/workspace?")) return snapshot;
      throw new Error(`Unexpected API path: ${path}`);
    });

    const first = store.refreshWorkspace();
    const second = store.refreshWorkspace();
    await Promise.resolve();

    const workspaceCalls = apiMock.mock.calls.filter(([path]) => String(path).startsWith("/project/workspace?"));
    expect(workspaceCalls).toHaveLength(1);
    releaseSnapshot({
      dashboard: { ok: true, current_task: { title: "合并加载" } },
      library: { ok: true, sections: { characters: [] } },
      delivery: { ok: true, project_root: "C:\\ArcVellum\\潮汐之后", status: "draft", files: [] },
      reader_manifest: { ok: true, units: [], delta: { added: [], removed: [], initial: true } },
      project_progress: { ok: true, status: "waiting_calibration", overall_percent: null, parts: [] },
      autopilot_status: { ok: true, run: null },
      agent_observability: { ok: true, status: "idle", active_task: null, sessions: [], recent_events: [] },
    });
    await Promise.all([first, second]);
    expect(store.dashboard?.current_task).toEqual({ title: "合并加载" });
  });

  it("preserves unchanged read-model identities across observability-only workspace updates", async () => {
    const { useAppStore } = await import("./app");
    const store = useAppStore();
    await store.initialize();
    await store.refreshWorkspace();
    const workspaceStream = streamConnections.find((item) => item.path.startsWith("/project/workspace/stream"));
    const base = {
      project_root: "C:\\ArcVellum\\潮汐之后",
      revision: "workspace-1",
      source_revisions: {
        dashboard: "dashboard-1",
        library: "library-1",
        delivery: "delivery-1",
        reader_manifest: "reader-1",
        project_progress: "progress-1",
        autopilot_status: "autopilot-1",
        agent_observability: "agent-1",
      },
      dashboard: { ok: true, current_task: { title: "开始写第一场" } },
      library: { ok: true, sections: { characters: [] } },
      delivery: { ok: true, project_root: "C:\\ArcVellum\\潮汐之后", status: "draft", files: [] },
      reader_manifest: { ok: true, units: [], delta: { added: [], removed: [], initial: true } },
      project_progress: { ok: true, status: "waiting_calibration", overall_percent: null, parts: [] },
      autopilot_status: { ok: true, run: null },
      agent_observability: { ok: true, revision: "agent-1", status: "active", active_task: null, sessions: [], recent_events: [] },
    };
    workspaceStream?.callback("workspace.snapshot", base);
    const dashboardIdentity = store.dashboard;
    const libraryIdentity = store.library;

    workspaceStream?.callback("workspace.snapshot", {
      ...base,
      revision: "workspace-2",
      source_revisions: { ...base.source_revisions, agent_observability: "agent-2" },
      dashboard: { ok: true, current_task: { title: "不应替换的副本" } },
      library: { ok: true, sections: { characters: [{ id: "not-applied" }] } },
      agent_observability: { ok: true, revision: "agent-2", status: "active", active_task: { stage: "主创正在工作" }, sessions: [], recent_events: [] },
    });

    expect(store.dashboard).toBe(dashboardIdentity);
    expect(store.library).toBe(libraryIdentity);
    expect(store.dashboard?.current_task).toEqual({ title: "开始写第一场" });
    expect(store.agentObservability?.active_task?.stage).toBe("主创正在工作");
  });

  it("explains a packaged desktop connection failure in user-facing language", async () => {
    const { friendlyError } = await import("./app");

    expect(friendlyError(new TypeError("Failed to fetch"), "启动失败")).toContain("本地创作服务没有连接成功");
    expect(friendlyError(new TypeError("CannotFetch"), "启动失败")).toContain("本地创作服务没有连接成功");
  });
});
