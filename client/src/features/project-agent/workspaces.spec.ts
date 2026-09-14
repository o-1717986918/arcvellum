import { describe, expect, it } from "vitest";
import { projectAgentWorkspaces } from "./workspaces";

describe("projectAgentWorkspaces", () => {
  it("keeps every legacy viewing capability inside the Agent desktop", () => {
    expect(projectAgentWorkspaces.all().map((item) => item.id)).toEqual([
      "reader",
      "live",
      "archive",
      "style",
      "quality",
      "strategy",
      "observatory",
      "archaeology",
      "delivery",
    ]);
  });

  it("rejects unknown workspace names", () => {
    expect(projectAgentWorkspaces.has("reader")).toBe(true);
    expect(projectAgentWorkspaces.get("reader")?.title).toBe("正文长卷");
    expect(projectAgentWorkspaces.has("debug-console")).toBe(false);
  });
});
