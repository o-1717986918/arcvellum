export interface DirectorySelection {
  supported: boolean;
  path: string | null;
}

export const DesktopBridge = {
  get isDesktop(): boolean {
    return Boolean(window.__TAURI_INTERNALS__);
  },

  async selectDirectory(defaultPath = ""): Promise<DirectorySelection> {
    if (!this.isDesktop) return { supported: false, path: null };
    const { open } = await import("@tauri-apps/plugin-dialog");
    const result = await open({ directory: true, multiple: false, defaultPath: defaultPath || undefined });
    return { supported: true, path: typeof result === "string" ? result : null };
  },
};
