import { describe, expect, it, vi } from "vitest";
import { createSettingsClient } from "./settingsClient";

describe("tone preference transport contract", () => {
  it("loads and saves a strict enabled payload through its feature client", async () => {
    const request = vi.fn().mockResolvedValue({ ok: true, preferences: { enabled: true } });
    const client = createSettingsClient({ request, authorizedFetch: vi.fn(), connect: vi.fn(), stream: vi.fn(), query: () => "" });
    await client.toneExperimentPreferences();
    await client.saveToneExperimentPreferences(true);
    expect(request.mock.calls).toEqual([
      ["/experiments/less-ai-tone"],
      ["/experiments/less-ai-tone", { method: "PUT", body: '{"enabled":true}' }],
    ]);
  });
});
