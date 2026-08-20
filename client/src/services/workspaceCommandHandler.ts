import type { WorkspaceCommand, WorkspaceCommandHandler, WorkspaceCommandResult, WorkspaceView } from "./workspaceCommands";

export interface WorkspaceCommandDependencies {
  projectRoot(): string;
  navigate(view: WorkspaceView): Promise<void>;
  recordDirection(projectRoot: string, message: string): Promise<unknown>;
  runRoute(projectRoot: string, route: string, runtime: string): Promise<Record<string, unknown>>;
  startAutopilot(projectRoot: string, runtime: string): Promise<Record<string, unknown>>;
  autopilotStatus(projectRoot: string): Promise<{ run?: { run_id: string; status: string } | null }>;
  pauseAutopilot(runId: string, reason: string): Promise<unknown>;
  resumeAutopilot(runId: string): Promise<unknown>;
  refresh(): Promise<void>;
}

const ROUTES = new Set([
  "auto", "scene-development", "longform-planning", "style-engineering",
  "character-and-world-assets", "review-and-audit", "export-and-release",
]);

export function createWorkspaceCommandHandler(deps: WorkspaceCommandDependencies): WorkspaceCommandHandler {
  return async (command) => {
    if (command.type === "navigate") {
      await deps.navigate(command.view);
      return ok("界面已打开。");
    }
    const root = deps.projectRoot().trim();
    if (!root) return { ok: false, message: "请先建立或打开一部作品。" };
    if (command.type === "record-direction") {
      const message = command.message.trim();
      if (!message) return { ok: false, message: "创作方向不能为空。" };
      await deps.recordDirection(root, message);
      await deps.refresh();
      return ok("这条想法已经交给创作流程。");
    }
    if (command.type === "run-route") {
      const route = ROUTES.has(command.route) ? command.route : "auto";
      const data = await deps.runRoute(root, route, command.runtime);
      await deps.refresh();
      return ok("下一项创作任务已经启动。", data);
    }
    if (command.type === "start-autopilot") {
      const data = await deps.startAutopilot(root, command.runtime);
      await deps.refresh();
      return ok("连续创作已经开始。", data);
    }
    const state = await deps.autopilotStatus(root);
    const run = state.run;
    if (command.type === "pause-autopilot") {
      if (!run?.run_id || run.status !== "running") return { ok: false, message: "当前没有正在运行的连续创作任务。" };
      await deps.pauseAutopilot(run.run_id, command.reason);
      await deps.refresh();
      return ok("连续创作已经暂停。");
    }
    if (!run?.run_id || !["paused", "blocked", "failed"].includes(run.status)) {
      return { ok: false, message: "当前没有可以恢复的连续创作任务。" };
    }
    await deps.resumeAutopilot(run.run_id);
    await deps.refresh();
    return ok("连续创作已经继续。");
  };
}

function ok(message: string, data?: Record<string, unknown>): WorkspaceCommandResult {
  return { ok: true, message, ...(data ? { data } : {}) };
}
