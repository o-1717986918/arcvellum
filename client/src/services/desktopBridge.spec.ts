import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const open = vi.fn();

vi.mock("@tauri-apps/plugin-dialog", () => ({ open }));

import { DesktopBridge } from "./desktopBridge";

describe("DesktopBridge", () => {
  beforeEach(() => {
    window.__TAURI_INTERNALS__ = {};
    open.mockReset();
  });

  afterEach(() => {
    delete window.__TAURI_INTERNALS__;
  });

  it("returns the directory selected by the native dialog", async () => {
    open.mockResolvedValue("C:\\Works");

    await expect(DesktopBridge.selectDirectory("C:\\Default")).resolves.toEqual({
      supported: true,
      path: "C:\\Works",
    });
    expect(open).toHaveBeenCalledWith({ directory: true, multiple: false, defaultPath: "C:\\Default" });
  });

  it("preserves cancellation as an empty selection", async () => {
    open.mockResolvedValue(null);

    await expect(DesktopBridge.selectDirectory()).resolves.toEqual({ supported: true, path: null });
  });

  it("turns native dialog failures into an actionable error", async () => {
    open.mockRejectedValue(new Error("dialog.open not allowed"));

    await expect(DesktopBridge.selectDirectory()).rejects.toThrow("请重试或手动填写路径");
  });
});
