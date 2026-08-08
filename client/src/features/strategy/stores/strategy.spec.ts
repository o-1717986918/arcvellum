import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.fn();
const streamCloseMock = vi.fn();
let streamListener:
  | ((event: string, data: Record<string, unknown>) => void)
  | null = null;
const connectEventStreamMock = vi.fn(
  (
    _path: string,
    listener: (event: string, data: Record<string, unknown>) => void,
  ) => {
    streamListener = listener;
    return { close: streamCloseMock };
  },
);

vi.mock("@/services/api", () => ({
  api: apiMock,
  connectEventStream: connectEventStreamMock,
  query: (values: Record<string, string>) =>
    new URLSearchParams(values).toString(),
}));

function projectionFixture() {
  return {
    schema: "arcvellum/strategy-projection/v1",
    settings: { enabled: false, mode: "fixed", preset: "balanced" },
    active_plan: {
      plan_id: "plan-1",
      revision: 3,
      status: "active",
      scope_kind: "chapter",
      scope_key: "chapter_01",
    },
    rolling_horizon: null,
    capabilities: [],
  };
}

describe("Creation Strategy store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    apiMock.mockReset();
    connectEventStreamMock.mockClear();
    streamCloseMock.mockClear();
    streamListener = null;
    window.localStorage.clear();
  });

  it("loads the read-only strategy projection and starts the typed stream", async () => {
    apiMock.mockResolvedValue({ ok: true, strategy: projectionFixture() });
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\潮线", false);
    const { useStrategyStore } = await import("./strategy");
    const store = useStrategyStore();

    await store.load();

    expect(store.settings?.mode).toBe("fixed");
    expect(store.activePlan?.plan_id).toBe("plan-1");
    expect(apiMock).toHaveBeenCalledWith(
      expect.stringContaining("project_root=C%3A%5CArcVellum%5C%E6%BD%AE%E7%BA%BF"),
    );
    expect(connectEventStreamMock).toHaveBeenCalledTimes(1);
    expect(connectEventStreamMock).toHaveBeenCalledWith(
      expect.stringContaining("follow=true"),
      expect.any(Function),
    );
  });

  it("appends only typed plan events and closes the stream on reload", async () => {
    apiMock.mockResolvedValue({ ok: true, strategy: projectionFixture() });
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\潮线", false);
    const { useStrategyStore } = await import("./strategy");
    const store = useStrategyStore();

    await store.load();
    expect(streamListener).not.toBeNull();
    streamListener?.("plan-event", {
      event_id: "e1",
      event_type: "plan.candidate.completed",
      plan_id: "plan-1",
      revision: 3,
    });
    streamListener?.("unrelated", { event_id: "x" });

    expect(store.events).toHaveLength(1);
    expect(store.events[0].event_type).toBe("plan.candidate.completed");

    await store.load();
    expect(streamCloseMock).toHaveBeenCalled();
  });

  it("reports a friendly load error", async () => {
    apiMock.mockRejectedValue(new Error("创作策略暂时没有读取成功。"));
    const { useAppStore } = await import("@/stores/app");
    useAppStore().setCurrentProject("C:\\ArcVellum\\潮线", false);
    const { useStrategyStore } = await import("./strategy");
    const store = useStrategyStore();

    await store.load();

    expect(store.error).toContain("创作策略");
  });
});
