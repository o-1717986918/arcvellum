function apiPrefix(): string {
  return window.__LES_API_BASE || (import.meta.env.DEV ? "/api" : "");
}

function authorizedHeaders(source?: HeadersInit): Headers {
  const headers = new Headers(source || {});
  if (window.__LES_API_TOKEN) headers.set("Authorization", `Bearer ${window.__LES_API_TOKEN}`);
  return headers;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function bootstrapDesktopSession(): Promise<void> {
  const token = window.__LES_API_TOKEN;
  if (!token) return;
  const deadline = Date.now() + 45_000;
  let lastError: unknown = null;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${apiPrefix()}/desktop/session`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) return;
      lastError = new ApiError("客户端身份验证失败，请重新启动 ArcVellum。", response.status);
      if (response.status === 401) break;
    } catch (cause) {
      lastError = cause;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 180));
  }
  throw lastError instanceof Error ? lastError : new ApiError("本地创作服务没有按时启动。", 0);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await authorizedFetch(path, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload?.detail === "string" ? payload.detail : `请求失败（${response.status}）`;
    throw new ApiError(detail, response.status);
  }
  return payload as T;
}

export async function authorizedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = authorizedHeaders(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return fetch(`${apiPrefix()}${path}`, { ...init, headers, credentials: "include" });
}

export async function streamApi(
  path: string,
  init: RequestInit,
  onEvent: (event: string, data: Record<string, unknown>) => void,
): Promise<void> {
  const response = await authorizedFetch(path, init);
  if (!response.ok || !response.body) {
    const payload = await response.json().catch(() => ({}));
    throw new ApiError(typeof payload?.detail === "string" ? payload.detail : "顾问连接没有成功。", response.status);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    for (const frame of frames) {
      if (!frame.trim() || frame.startsWith(":")) continue;
      let event = "message";
      const data: string[] = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
      }
      if (!data.length) continue;
      const payload = JSON.parse(data.join("\n")) as Record<string, unknown>;
      onEvent(event, payload);
    }
    if (done) break;
  }
}

export interface EventStreamConnection {
  close(): void;
}

export function connectEventStream(
  path: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  onError?: (cause: unknown) => void,
): EventStreamConnection {
  let active = true;
  let controller: AbortController | null = null;

  const run = async () => {
    while (active) {
      controller = new AbortController();
      try {
        await streamApi(path, { method: "GET", signal: controller.signal }, onEvent);
      } catch (cause) {
        if (active && !(cause instanceof DOMException && cause.name === "AbortError")) onError?.(cause);
      }
      if (active) await new Promise((resolve) => window.setTimeout(resolve, 750));
    }
  };
  void run();

  return {
    close() {
      active = false;
      controller?.abort();
    },
  };
}

export function query(values: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  return params.toString();
}
