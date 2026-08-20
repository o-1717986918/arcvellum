import { describe, expect, it, vi } from "vitest";
import { createWorkspaceCommandHandler, type WorkspaceCommandDependencies } from "./workspaceCommandHandler";
import { WorkspaceCommandBus } from "./workspaceCommands";

function dependencies(): WorkspaceCommandDependencies {
  return {
    projectRoot: () => "C:/ArcVellum/Works/demo",
    navigate: vi.fn(async () => undefined),
    recordDirection: vi.fn(async () => undefined),
    runRoute: vi.fn(async () => ({ job_id: "job-1" })),
    startAutopilot: vi.fn(async () => ({ run: { run_id: "run-1" } })),
    autopilotStatus: vi.fn(async () => ({ run: { run_id: "run-1", status: "paused" } })),
    pauseAutopilot: vi.fn(async () => undefined),
    resumeAutopilot: vi.fn(async () => undefined),
    refresh: vi.fn(async () => undefined),
  };
}

describe("WorkspaceCommandBus", () => {
  it("rejects commands before the application composition root is installed", async () => {
    expect(await new WorkspaceCommandBus().dispatch({ type: "navigate", view: "overview" })).toEqual({
      ok: false,
      message: "工作区控制台尚未就绪。",
    });
  });

  it("normalizes unknown routes without exposing raw endpoints", async () => {
    const deps = dependencies();
    const bus = new WorkspaceCommandBus();
    bus.install(createWorkspaceCommandHandler(deps));

    const result = await bus.dispatch({ type: "run-route", route: "../../shell", runtime: "pi-worker" });

    expect(result.ok).toBe(true);
    expect(deps.runRoute).toHaveBeenCalledWith("C:/ArcVellum/Works/demo", "auto", "pi-worker");
    expect(deps.refresh).toHaveBeenCalledOnce();
  });

  it("resumes only a resumable formal run", async () => {
    const deps = dependencies();
    const bus = new WorkspaceCommandBus();
    bus.install(createWorkspaceCommandHandler(deps));

    expect((await bus.dispatch({ type: "resume-autopilot" })).ok).toBe(true);
    expect(deps.resumeAutopilot).toHaveBeenCalledWith("run-1");
  });
});
