import { describe, expect, it, vi } from "vitest";
import type { ApiTransport } from "@/services/api";
import { createProjectAgentClient } from "./projectAgentClient";

describe("projectAgentClient", () => {
  it("resumes durable events from the last SSE cursor", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(response("id: 3\nevent: project_agent.event\ndata: {\"event\":\"text.delta\",\"text\":\"先看\"}\n\n"))
      .mockResolvedValueOnce(response("id: 4\nevent: stream.terminal\ndata: {\"status\":\"complete\"}\n\n"));
    const transport = fakeTransport(fetch);
    const client = createProjectAgentClient(transport);
    const events: string[] = [];

    await client.observeJob("job-1", new AbortController().signal, (item) => events.push(`${item.cursor}:${item.event}`));

    expect(events).toEqual(["3:project_agent.event", "4:stream.terminal"]);
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      "/project-agent/jobs/job-1/events?after=3",
      expect.objectContaining({ headers: { "Last-Event-ID": "3" } }),
    );
  });
});

function response(body: string): Response {
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}
function fakeTransport(fetch: ReturnType<typeof vi.fn>): ApiTransport {
  return {
    request: vi.fn(),
    authorizedFetch: fetch,
    stream: vi.fn(),
    connect: vi.fn(),
    query: (values) => new URLSearchParams(
      Object.entries(values).filter(([, value]) => value !== undefined).map(([key, value]) => [key, String(value)]),
    ).toString(),
  } as ApiTransport;
}
