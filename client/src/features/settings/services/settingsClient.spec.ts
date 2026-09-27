import { describe, expect, it, vi } from "vitest";
import type { ApiTransport } from "@/services/api";
import { createSettingsClient } from "./settingsClient";

describe("settings prompt client", () => {
  it("routes versioned layer edits and previews through the feature client", async () => {
    const request = vi.fn().mockResolvedValue({ ok: true });
    const transport = { request, authorizedFetch: vi.fn(), connect: vi.fn() } as unknown as ApiTransport;
    const client = createSettingsClient(transport);
    await client.savePromptLayer("scene.creator.identity", { scope: "project", project_root: "C:\\work", text: "新的主创使命" });
    await client.activatePromptVersion("scene.creator.identity", { scope: "project", project_root: "C:\\work", version: 1 });
    await client.resetPromptLayer("scene.creator.identity", { scope: "project", project_root: "C:\\work" });
    await client.previewPromptLayers(["scene.protocol", "scene.creator.identity"], "C:\\work");
    expect(request).toHaveBeenNthCalledWith(1, "/prompts/layers/scene.creator.identity", expect.objectContaining({ method: "PUT" }));
    expect(request).toHaveBeenNthCalledWith(2, "/prompts/layers/scene.creator.identity/activate", expect.objectContaining({ method: "POST" }));
    expect(request).toHaveBeenNthCalledWith(3, "/prompts/layers/scene.creator.identity/reset", expect.objectContaining({ method: "POST" }));
    expect(request).toHaveBeenNthCalledWith(4, "/prompts/preview", expect.objectContaining({ method: "POST" }));
  });
});
