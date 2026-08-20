import { describe, expect, it, vi } from "vitest";
import { createFeatureClientHarness } from "./featureClientHarness";
import {
  advisorSessionFixture,
  dashboardFixture,
  projectSummaryFixture,
  qualityProfileFixture,
  spatialProjectionFixture,
} from "./literaryFixtures";

const PROJECT_ROOT = projectSummaryFixture().path;

describe("feature clients over MockFeatureTransport", () => {
  it("keeps workflow requests and workspace events inside the workflow client", async () => {
    const { transport, clients } = createFeatureClientHarness();
    const dashboardPath = `/workflow/dashboard?${transport.query({ project_root: PROJECT_ROOT })}`;
    const streamPath = `/project/workspace/stream?${transport.query({ project_root: PROJECT_ROOT, interval_seconds: 2 })}`;
    transport.respond("GET", dashboardPath, dashboardFixture());

    expect((await clients.workflow.dashboard(PROJECT_ROOT)).current_task?.task_id).toBe("scene-0001-compose");
    const received = vi.fn();
    const connection = clients.workflow.observeWorkspace(PROJECT_ROOT, received);
    expect(transport.emit(streamPath, "workspace.heartbeat", {})).toBe(1);
    expect(received).not.toHaveBeenCalled();
    transport.emit(streamPath, "workspace.snapshot", { revision: "workspace-r2" });
    expect(received).toHaveBeenCalledWith({ revision: "workspace-r2" });
    connection.close();
    expect(transport.emit(streamPath, "workspace.snapshot", { revision: "workspace-r3" })).toBe(0);
  });

  it("serializes project creation through the projects client", async () => {
    const { transport, clients } = createFeatureClientHarness();
    transport.respond("POST", "/projects/create", { ok: true, project: projectSummaryFixture() });

    await clients.projects.create({ title: "潮汐之后", target_length: 30000 });

    expect(transport.lastCall("request")).toMatchObject({
      method: "POST",
      path: "/projects/create",
      body: { title: "潮汐之后", target_length: 30000 },
    });
  });

  it("uses the authorized fetch boundary for delivery downloads", async () => {
    const { transport, clients } = createFeatureClientHarness();
    const path = `/project/delivery/download?${transport.query({ project_root: PROJECT_ROOT, path: "release/book.docx" })}`;
    transport.respond("GET", path, new Response("document-bytes", { status: 200 }));

    const response = await clients.delivery.download(PROJECT_ROOT, "release/book.docx");

    expect(await response.text()).toBe("document-bytes");
    expect(transport.lastCall("fetch")?.path).toBe(path);
  });

  it("keeps settings offline and persists explicit role model selection", async () => {
    const { transport, clients } = createFeatureClientHarness();
    transport.respond("PUT", "/model-connections/opencode/model", { selected_model: "deepseek/deepseek-chat" });

    await expect(clients.settings.bootstrapDesktopSession()).resolves.toBeUndefined();
    await clients.settings.selectModel("deepseek/deepseek-chat", "worker");

    expect(transport.lastCall("request")?.body).toEqual({ model: "deepseek/deepseek-chat", role: "worker" });
  });

  it("sends the complete quality profile through the quality boundary", async () => {
    const { transport, clients } = createFeatureClientHarness();
    const profile = qualityProfileFixture();
    transport.respond("PUT", "/project/creative-quality", { profile });

    expect((await clients.quality.saveProfile(PROJECT_ROOT, profile)).profile.digest).toBe("quality-fixture-v1");
    expect(transport.lastCall("request")?.body).toEqual({ project_root: PROJECT_ROOT, profile });
  });

  it("filters Orrery projection and patch events without a browser connection", async () => {
    const { transport, clients } = createFeatureClientHarness();
    const view = { projectRoot: PROJECT_ROOT, level: "book", focus: "", grammar: "spine" };
    const path = `/narrative/stream/v3?${transport.query({ project_root: PROJECT_ROOT, level: "book", focus: "", grammar: "spine" })}&interval_seconds=2`;
    const projection = spatialProjectionFixture();
    const onProjection = vi.fn();
    const onPatch = vi.fn();

    clients.orrery.observeSpatialProjection(view, onProjection, onPatch);
    transport.emit(path, "narrative.heartbeat", {});
    transport.emit(path, "narrative.v3.projection", projection as unknown as Record<string, unknown>);
    transport.emit(path, "narrative.v3.patch", { target_revision: "fixture-p2" });

    expect(onProjection).toHaveBeenCalledWith(projection);
    expect(onPatch).toHaveBeenCalledWith({ target_revision: "fixture-p2" });
  });

  it("loads advisor surface and consumes a deterministic streamed answer", async () => {
    const { transport, clients } = createFeatureClientHarness();
    const personasPath = `/advisor/personas?${transport.query({ project_root: PROJECT_ROOT })}`;
    const inboxPath = `/advisor/inbox?${transport.query({ project_root: PROJECT_ROOT })}`;
    const session = advisorSessionFixture();
    const askPath = `/advisor/sessions/${session.session_id}/ask/stream`;
    transport
      .respond("GET", personasPath, { selected_persona: "chief-editor", items: [{ persona_id: "chief-editor", name: "严谨总编" }] })
      .respond("GET", inboxPath, { items: [], unread_count: 0 })
      .streamWith(askPath, [
        { event: "advisor.delta", data: { text: "先看人物动机。" } },
        { event: "advisor.result", data: { answer: { message: "先看人物动机。", evidence: [], uncertainties: [], suggested_actions: [] } } },
      ]);

    expect((await clients.advisor.surface(PROJECT_ROOT)).personas.selected_persona).toBe("chief-editor");
    const events: string[] = [];
    await clients.advisor.ask(session.session_id, "下一步呢？", {}, new AbortController().signal, (event) => events.push(event));
    expect(events).toEqual(["advisor.delta", "advisor.result"]);
    expect(transport.lastCall("stream")?.body).toMatchObject({ question: "下一步呢？", timeout: 240 });
  });

  it("fails loudly when a feature reaches an unregistered transport route", async () => {
    const { clients } = createFeatureClientHarness();
    await expect(clients.projects.list()).rejects.toThrow("Unregistered mock request: GET /projects");
  });
});
