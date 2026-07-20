export interface DirectorySelection {
  supported: boolean;
  path: string | null;
}

function directoryError(cause: unknown): Error {
  const detail = cause instanceof Error ? cause.message : String(cause || "");
  const suffix = detail ? ` (${detail})` : "";
  return new Error(`系统目录选择器没有成功打开，请重试或手动填写路径。${suffix}`);
}

export const DesktopBridge = {
  get isDesktop(): boolean {
    return Boolean(window.__TAURI_INTERNALS__);
  },

  async selectDirectory(defaultPath = ""): Promise<DirectorySelection> {
    if (!this.isDesktop) return { supported: false, path: null };
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const result = await open({ directory: true, multiple: false, defaultPath: defaultPath || undefined });
      return { supported: true, path: typeof result === "string" ? result : null };
    } catch (cause) {
      throw directoryError(cause);
    }
  },
};
