import type { ApiTransport, EventStreamConnection } from "@/services/api";

export interface MockTransportCall {
  kind: "request" | "fetch" | "stream" | "connect";
  method: string;
  path: string;
  init?: RequestInit;
  body: unknown;
}

type PathMatcher = string | RegExp | ((path: string) => boolean);
type MockResponder = unknown | ((call: MockTransportCall) => unknown | Promise<unknown>);
type StreamFrame = { event: string; data: Record<string, unknown> };

interface RegisteredRoute {
  method: string;
  matcher: PathMatcher;
  responder: MockResponder;
}

interface Subscription {
  path: string;
  onEvent: (event: string, data: Record<string, unknown>) => void;
  onError?: (cause: unknown) => void;
  active: boolean;
}

export class MockFeatureTransport implements ApiTransport {
  readonly calls: MockTransportCall[] = [];
  private readonly routes: RegisteredRoute[] = [];
  private readonly streamFrames = new Map<string, StreamFrame[]>();
  private readonly subscriptions: Subscription[] = [];

  respond(method: string, matcher: PathMatcher, responder: MockResponder): this {
    this.routes.push({ method: method.toUpperCase(), matcher, responder });
    return this;
  }

  streamWith(path: string, frames: StreamFrame[]): this {
    this.streamFrames.set(path, frames);
    return this;
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const call = this.record("request", path, init);
    return await this.resolve(call) as T;
  }

  async authorizedFetch(path: string, init: RequestInit = {}): Promise<Response> {
    const call = this.record("fetch", path, init);
    const value = await this.resolve(call);
    return value instanceof Response
      ? value
      : new Response(typeof value === "string" ? value : JSON.stringify(value), { status: 200 });
  }

  async stream(
    path: string,
    init: RequestInit,
    onEvent: (event: string, data: Record<string, unknown>) => void,
  ): Promise<void> {
    this.record("stream", path, init);
    const frames = this.streamFrames.get(path);
    if (!frames) throw new Error(`Unregistered mock stream: ${methodOf(init)} ${path}`);
    for (const frame of frames) {
      if (init.signal?.aborted) throw new DOMException("aborted", "AbortError");
      onEvent(frame.event, structuredClone(frame.data));
    }
  }

  connect(
    path: string,
    onEvent: (event: string, data: Record<string, unknown>) => void,
    onError?: (cause: unknown) => void,
  ): EventStreamConnection {
    this.record("connect", path, { method: "GET" });
    const subscription = { path, onEvent, onError, active: true };
    this.subscriptions.push(subscription);
    return { close: () => { subscription.active = false; } };
  }

  emit(path: string, event: string, data: Record<string, unknown>): number {
    let delivered = 0;
    for (const subscription of this.subscriptions) {
      if (!subscription.active || subscription.path !== path) continue;
      subscription.onEvent(event, structuredClone(data));
      delivered += 1;
    }
    return delivered;
  }

  fail(path: string, cause: unknown): number {
    let delivered = 0;
    for (const subscription of this.subscriptions) {
      if (!subscription.active || subscription.path !== path) continue;
      subscription.onError?.(cause);
      delivered += 1;
    }
    return delivered;
  }

  query(values: Record<string, string | number | undefined>): string {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(values)) {
      if (value !== undefined && value !== "") params.set(key, String(value));
    }
    return params.toString();
  }

  lastCall(kind?: MockTransportCall["kind"]): MockTransportCall | undefined {
    return [...this.calls].reverse().find((call) => !kind || call.kind === kind);
  }

  private record(kind: MockTransportCall["kind"], path: string, init: RequestInit): MockTransportCall {
    const call = { kind, method: methodOf(init), path, init, body: parseBody(init.body) };
    this.calls.push(call);
    return call;
  }

  private async resolve(call: MockTransportCall): Promise<unknown> {
    const route = this.routes.find((candidate) => candidate.method === call.method && matches(candidate.matcher, call.path));
    if (!route) throw new Error(`Unregistered mock request: ${call.method} ${call.path}`);
    const value = typeof route.responder === "function" ? await route.responder(call) : route.responder;
    return structuredCloneUnlessResponse(value);
  }
}

function methodOf(init: RequestInit): string {
  return String(init.method || "GET").toUpperCase();
}

function parseBody(body: BodyInit | null | undefined): unknown {
  if (typeof body !== "string") return body ?? null;
  try {
    return JSON.parse(body);
  } catch {
    return body;
  }
}

function matches(matcher: PathMatcher, path: string): boolean {
  if (typeof matcher === "string") return matcher === path;
  if (matcher instanceof RegExp) {
    matcher.lastIndex = 0;
    return matcher.test(path);
  }
  return matcher(path);
}

function structuredCloneUnlessResponse<T>(value: T): T {
  return value instanceof Response ? value : structuredClone(value);
}
