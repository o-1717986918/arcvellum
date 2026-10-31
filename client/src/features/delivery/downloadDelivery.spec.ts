import { afterEach, describe, expect, it, vi } from "vitest";
import { downloadDelivery } from "./downloadDelivery";
import { deliveryClient } from "./services/deliveryClient";
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });
describe("authenticated delivery downloads", () => {
  it("downloads through the feature client and keeps the URL alive for the handler", async () => {
    vi.useFakeTimers();
    const download = vi.spyOn(deliveryClient, "download").mockResolvedValue(new Response("manuscript", { status: 200 }));
    const create = vi.fn(() => "blob:manuscript"), revoke = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: create });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revoke });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      expect(this.download).toBe("作品.docx");
      expect(this.isConnected).toBe(true);
    });
    await downloadDelivery("work", "delivery/book.docx", "作品.docx");
    expect(download).toHaveBeenCalledWith("work", "delivery/book.docx");
    expect(click).toHaveBeenCalledOnce();
    expect(revoke).not.toHaveBeenCalled();
    vi.advanceTimersByTime(30_000);
    expect(revoke).toHaveBeenCalledWith("blob:manuscript");
  });
  it("does not download a failed HTTP response as if it were a manuscript", async () => {
    vi.spyOn(deliveryClient, "download").mockResolvedValue(new Response("unauthorized", { status: 401 }));
    await expect(downloadDelivery("work", "book.docx")).rejects.toThrow("401");
  });
});
