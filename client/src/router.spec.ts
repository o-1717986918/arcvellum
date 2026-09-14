import { describe, expect, it } from "vitest";
import { router } from "./router";

describe("legacy project viewing routes", () => {
  it.each([
    ["/reader", "reader"],
    ["/archive", "archive"],
    ["/style", "style"],
    ["/quality", "quality"],
    ["/strategy", "strategy"],
    ["/observatory", "live"],
    ["/delivery", "delivery"],
  ])("redirects %s into the Agent child workspace", async (path, workspace) => {
    await router.push(path);
    expect(router.currentRoute.value.name).toBe("project-agent");
    expect(router.currentRoute.value.query.workspace).toBe(workspace);
  });
});
