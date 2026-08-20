export type WorkspaceView =
  | "projects" | "overview" | "reader" | "archive" | "archaeology"
  | "style" | "quality" | "strategy" | "observatory" | "delivery"
  | "settings" | "help" | "details" | "legal";

export type WorkspaceCommand =
  | { type: "navigate"; view: WorkspaceView }
  | { type: "record-direction"; message: string }
  | { type: "run-route"; route: string; runtime: string }
  | { type: "start-autopilot"; runtime: string }
  | { type: "pause-autopilot"; reason: string }
  | { type: "resume-autopilot" };

export interface WorkspaceCommandResult {
  ok: boolean;
  message: string;
  data?: Record<string, unknown>;
}

export type WorkspaceCommandHandler = (command: WorkspaceCommand) => Promise<WorkspaceCommandResult>;

export class WorkspaceCommandBus {
  private handler: WorkspaceCommandHandler | null = null;

  install(handler: WorkspaceCommandHandler): () => void {
    if (this.handler) throw new Error("Workspace command handler is already installed.");
    this.handler = handler;
    return () => { if (this.handler === handler) this.handler = null; };
  }

  async dispatch(command: WorkspaceCommand): Promise<WorkspaceCommandResult> {
    if (!this.handler) return { ok: false, message: "工作区控制台尚未就绪。" };
    return this.handler(command);
  }
}

export const workspaceCommandBus = new WorkspaceCommandBus();
