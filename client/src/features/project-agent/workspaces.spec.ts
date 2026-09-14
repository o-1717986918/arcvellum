import { describe, expect, it } from "vitest";
import { projectAgentWorkspaces } from "./workspaces";

describe("projectAgentWorkspaces", () => {
  it("keeps project and application workspaces inside the Agent desktop", () => {
    expect(projectAgentWorkspaces.all().map((item) => item.id)).toEqual([
      "projects",
      "reader",
      "live",
      "archive",
      "style",
      "quality",
      "strategy",
      "observatory",
      "archaeology",
      "delivery",
      "settings",
      "help",
      "details",
      "legal",
    ]);
  });

  it("separates project-bound tools from application workspaces", () => {
    expect(projectAgentWorkspaces.forScope("project")).toHaveLength(9);
    expect(projectAgentWorkspaces.forScope("application").map((item) => item.id)).toEqual([
      "projects",
      "settings",
      "help",
      "details",
      "legal",
    ]);
    expect(projectAgentWorkspaces.get("reader")?.requiresProject).toBe(true);
    expect(projectAgentWorkspaces.get("settings")?.requiresProject).toBe(false);
  });

  it("rejects unknown workspace names", () => {
    expect(projectAgentWorkspaces.has("reader")).toBe(true);
    expect(projectAgentWorkspaces.get("reader")?.title).toBe("正文长卷");
    expect(projectAgentWorkspaces.has("debug-console")).toBe(false);
  });
});
