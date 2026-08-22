import { describe, expect, it } from "vitest";
import { creativeWorkspaceRegistry } from "./workspaceRegistry";

describe("creativeWorkspaceRegistry", () => {
  it("registers every migrated literary workspace as fullscreen-capable", () => {
    const workspaces = creativeWorkspaceRegistry.all();
    expect(workspaces.map((item) => item.workspaceId)).toEqual([
      "archive", "style", "quality", "strategy", "observatory", "archaeology",
    ]);
    expect(workspaces.every((item) => item.supportsFullscreen)).toBe(true);
  });

  it("resolves workspaces from literary node kinds", () => {
    expect(creativeWorkspaceRegistry.forNode("character").map((item) => item.workspaceId)).toContain("archive");
    expect(creativeWorkspaceRegistry.forNode("review").map((item) => item.workspaceId)).toContain("quality");
    expect(creativeWorkspaceRegistry.forNode("style").map((item) => item.workspaceId)).toContain("style");
  });
});
