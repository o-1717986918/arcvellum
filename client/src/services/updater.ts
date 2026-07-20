import { DesktopBridge } from "./desktopBridge";

export interface UpdateCheckResult {
  supported: boolean;
  available: boolean;
  currentVersion: string;
  version: string;
  date: string;
  body: string;
  handle?: unknown;
}

export async function checkForUpdate(): Promise<UpdateCheckResult> {
  if (!DesktopBridge.isDesktop) {
    return { supported: false, available: false, currentVersion: "", version: "", date: "", body: "" };
  }
  const { check } = await import("@tauri-apps/plugin-updater");
  const update = await check();
  if (!update) {
    return { supported: true, available: false, currentVersion: "", version: "", date: "", body: "" };
  }
  return {
    supported: true,
    available: true,
    currentVersion: update.currentVersion,
    version: update.version,
    date: update.date || "",
    body: update.body || "",
    handle: update,
  };
}

export async function installUpdate(
  result: UpdateCheckResult,
  onProgress: (downloaded: number, total: number) => void,
): Promise<void> {
  if (!result.handle) throw new Error("没有可以安装的更新。 ");
  const update = result.handle as {
    downloadAndInstall: (callback: (event: { event: string; data?: { contentLength?: number; chunkLength?: number } }) => void) => Promise<void>;
  };
  let total = 0;
  let downloaded = 0;
  await update.downloadAndInstall((event) => {
    if (event.event === "Started") total = Number(event.data?.contentLength || 0);
    if (event.event === "Progress") downloaded += Number(event.data?.chunkLength || 0);
    onProgress(downloaded, total);
  });
}

export async function restartApplication(): Promise<void> {
  if (!DesktopBridge.isDesktop) {
    window.location.reload();
    return;
  }
  const { relaunch } = await import("@tauri-apps/plugin-process");
  await relaunch();
}
