import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.fn();
const bootstrapDesktopSessionMock = vi.fn();

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
  sseUrl: (path: string) => path,
}));

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  readonly url: string;
  closed = false;
  listeners = new Map<string, (event: MessageEvent) => void>();

  constructor(url: string | URL) {
    this.url = String(url);
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListenerOrEventListenerObject): void {
    this.listeners.set(type, listener as (event: MessageEvent) => void);
  }

  close(): void {
    this.closed = true;
  }

  emit(type: string, data: unknown): void {
    this.listeners.get(type)?.(new MessageEvent(type, { data: JSON.stringify(data) }));
  }
}

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
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
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
      if (path.startsWith("/workflow/dashboard")) return { ok: true, current_task: { title: "梳理人物" } };
      if (path.startsWith("/project/library")) return { ok: true, sections: { characters: [] } };
      if (path.startsWith("/project/delivery")) return { ok: true, project_root: "C:\\ArcVellum\\潮汐之后", status: "draft", files: [] };
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
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it("streams the active project's dashboard and archive after the initial load", async () => {
    const { useAppStore } = await import("./app");
    const store = useAppStore();
    await store.initialize();

    await store.refreshWorkspace();

    expect(store.dashboard?.current_task).toEqual({ title: "梳理人物" });
    expect(store.library?.sections).toEqual({ characters: [] });
    const projectStreams = FakeEventSource.instances.filter((item) => item.url.includes("/stream"));
    expect(projectStreams.some((item) => item.url.startsWith("/workflow/dashboard/stream"))).toBe(true);
    expect(projectStreams.some((item) => item.url.startsWith("/project/library/stream"))).toBe(true);

    const dashboardStream = projectStreams.find((item) => item.url.startsWith("/workflow/dashboard/stream"));
    dashboardStream?.emit("dashboard", { ok: true, current_task: { title: "开始写第一场" } });
    expect(store.dashboard?.current_task).toEqual({ title: "开始写第一场" });
  });
});
