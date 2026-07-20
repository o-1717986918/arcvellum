import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, authorizedFetch, bootstrapDesktopSession, query, streamApi } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("API client", () => {
  it("sends JSON requests with the desktop session cookie", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true, title: "潮汐之后" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await api<{ ok: boolean; title: string }>("/projects/create", {
      method: "POST",
      body: JSON.stringify({ title: "潮汐之后" }),
    });

    expect(result.title).toBe("潮汐之后");
    const [, init] = fetchMock.mock.calls[0];
    expect(init?.credentials).toBe("include");
    expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
  });

  it("preserves the server's user-facing error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "请选择一个可写入的文件夹。" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(api("/projects/create", { method: "POST" })).rejects.toEqual(
      expect.objectContaining<ApiError>({
        name: "ApiError",
        status: 400,
        message: "请选择一个可写入的文件夹。",
      }),
    );
  });

  it("parses fragmented server-sent events without losing the terminal frame", async () => {
    const encoder = new TextEncoder();
    const chunks = [
      "event: advisor.delta\ndata: {\"delta\":\"前半\"}\n",
      "\nevent: advisor.completed\ndata: {\"message\":\"完整回答\"}\n\n",
    ];
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(body, { status: 200 }));
    const events: Array<[string, Record<string, unknown>]> = [];

    await streamApi("/advisor/ask/stream", { method: "POST" }, (event, payload) => {
      events.push([event, payload]);
    });

    expect(events).toEqual([
      ["advisor.delta", { delta: "前半" }],
      ["advisor.completed", { message: "完整回答" }],
    ]);
  });

  it("encodes project paths and omits empty query values", () => {
    expect(query({ project_root: "C:\\作品\\潮汐 之后", route: "", page: 2 })).toBe(
      "project_root=C%3A%5C%E4%BD%9C%E5%93%81%5C%E6%BD%AE%E6%B1%90+%E4%B9%8B%E5%90%8E&page=2",
    );
  });

  it("uses the injected desktop API base and keeps bearer auth for later streams", async () => {
    window.__LES_API_BASE = "http://127.0.0.1:43123";
    window.__LES_API_TOKEN = "test-desktop-token";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } }),
    );

    await bootstrapDesktopSession();
    await api("/application/bootstrap");
    await authorizedFetch("/application/diagnostics/export", { method: "POST" });

    expect(String(fetchMock.mock.calls[0][0])).toBe("http://127.0.0.1:43123/desktop/session");
    expect(new Headers(fetchMock.mock.calls[1][1]?.headers).get("Authorization")).toBe("Bearer test-desktop-token");
    expect(String(fetchMock.mock.calls[2][0])).toBe("http://127.0.0.1:43123/application/diagnostics/export");
    expect(new Headers(fetchMock.mock.calls[2][1]?.headers).get("Authorization")).toBe("Bearer test-desktop-token");
    delete window.__LES_API_BASE;
    delete window.__LES_API_TOKEN;
  });
});
